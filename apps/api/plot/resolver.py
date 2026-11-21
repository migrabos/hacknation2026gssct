"""Plot (działka ewidencyjna) resolver + terrain slope + nearby water.

Pipeline for one plot:
    ULDK GUGiK (id or map click)  -> geometry, area, admin names     [required]
    GUGiK NMT (fallback Open-Meteo Elevation) -> slope + runoff risk  [fail-soft]
    OpenStreetMap water features  -> distance to river/ditch/water    [fail-soft]
        (Overpass mirrors raced in parallel with OpenFreeMap z14 vector tiles)

Terrain and hydro run concurrently. Nothing here interprets drought – we only fetch
and compute simple, verifiable numbers (heights, distances, area). Missing inputs are
reported in `missingData`; nothing is ever invented.

Coordinate conventions (important, easy to get wrong):
    * GeoJSON / shapely / bbox:   (lng, lat)
    * `centroid()` output:        [lat, lng]
    * ULDK `xy` param:            "lng,lat,4326"
    * EPSG:2180 with always_xy:   (easting, northing)
    * GUGiK NMT point list:       "northing easting"  (geodetic x/y order!)
"""

from __future__ import annotations

import asyncio
import gzip
import json
import math
import re
import unicodedata
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable

import time

import httpx
import shapely
from pyproj import Transformer
from shapely import wkt as shapely_wkt
from shapely.geometry import LineString, Point, Polygon, mapping, shape
from shapely.geometry.base import BaseGeometry

from adapters.base import PartialResult, run_adapter, utc_now_iso
from adapters.land_use import classify_land_use

# --------------------------------------------------------------------------- config

ULDK_URL = "https://uldk.gugik.gov.pl/service.php"
ULDK_FIELDS = "id,geom_wkt,voivodeship,county,commune,region,parcel"

NMT_URL = "https://services.gugik.gov.pl/nmt/"
OM_ELEVATION_URL = "https://api.open-meteo.com/v1/elevation"

# Public Overpass instances (https://wiki.openstreetmap.org/wiki/Overpass_API#Public_Overpass_API_instances).
# All live ones are queried *in parallel*; the first valid answer wins, the rest are cancelled.
OVERPASS_URLS = (
    "https://overpass-api.de/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
)
# Second, independent channel to the same OSM data: OpenMapTiles-schema vector tiles
# (layers `waterway`: river/stream/canal/drain/ditch, `water`: polygons). No key needed.
OFM_TILEJSON_URL = "https://tiles.openfreemap.org/planet"
OFM_ZOOM = 14  # max zoom of the tileset; all waterway classes present here
OVERPASS_PREFERRED_SEC = 5.0  # give Overpass a head start before accepting the tile answer
HYDRO_RADIUS_M = 500.0
HYDRO_TIMEOUT_SEC = 15.0  # whole hydro step (mirrors raced in parallel)
OVERPASS_COOLDOWN_SEC = 60.0  # after a failure, deprioritise the endpoint for a while
WATERWAY_TYPES = ("river", "stream", "ditch", "drain", "canal")

DAY = 86_400
ULDK_CACHE_TTL = 30 * DAY  # cadastre changes rarely
HYDRO_CACHE_TTL = 7 * DAY
# elevation never changes on our timescale -> cache forever (None)

USER_AGENT = "Retencja-HackNation2026/0.1 (prototype; water-retention DSS)"
HTTP_TIMEOUT = httpx.Timeout(15.0, connect=5.0)

_TO_2180 = Transformer.from_crs("EPSG:4326", "EPSG:2180", always_xy=True)
_TO_4326 = Transformer.from_crs("EPSG:2180", "EPSG:4326", always_xy=True)

# TERYT parcel ID: WWPPGG_R.OOOO.<nr> (nr may contain "/", "." and "AR_<n>." map-sheet prefix)
_PLOT_ID_RE = re.compile(r"^\d{6}_\d\.\d{4}\.[0-9A-Za-z_.\-/]{1,40}$")


# --------------------------------------------------------------------------- errors


class PlotError(Exception):
    """Base class – message is user-facing Polish text."""


class PlotNotFound(PlotError):
    pass


class PlotServiceUnavailable(PlotError):
    pass


class InvalidPlotInput(PlotError):
    pass


# --------------------------------------------------------------------------- shared helpers


def _as_shape(geom: dict[str, Any] | BaseGeometry) -> BaseGeometry:
    return geom if isinstance(geom, BaseGeometry) else shape(geom)


def to_2180(geom: dict[str, Any] | BaseGeometry) -> BaseGeometry:
    """WGS84 (lng/lat) geometry -> EPSG:2180 metres."""
    return shapely.transform(_as_shape(geom), _TO_2180.transform, interleaved=False)


def centroid(geom: dict[str, Any] | BaseGeometry) -> list[float]:
    """Return [lat, lng] of a point guaranteed to lie inside the plot.

    Uses the geometric centroid; for concave (L/U-shaped) plots where the centroid
    falls outside, falls back to shapely's representative point. Use this point for
    meteo / soil queries.
    """
    g = _as_shape(geom)
    c = g.centroid
    if not g.contains(c):
        c = g.representative_point()
    return [round(c.y, 6), round(c.x, 6)]


def bbox_from_geometry(geom: dict[str, Any] | BaseGeometry) -> list[float]:
    """Return [min_lng, min_lat, max_lng, max_lat]."""
    minx, miny, maxx, maxy = _as_shape(geom).bounds
    return [round(minx, 7), round(miny, 7), round(maxx, 7), round(maxy, 7)]


def area_ha(geom: dict[str, Any] | BaseGeometry) -> float:
    return round(to_2180(geom).area / 10_000, 4)


def _url(base: str, params: dict[str, Any]) -> str:
    return str(httpx.URL(base, params=params))


# ULDK sometimes answers with a garbage blob announced as several GB instead of a result.
# Never read more than this; a real reply (one parcel WKT / a list of obręby) is far smaller.
ULDK_MAX_BYTES = 3_000_000


async def _get_text_limited(client: httpx.AsyncClient, url: str, max_bytes: int = ULDK_MAX_BYTES) -> str:
    async with client.stream("GET", url) as r:
        r.raise_for_status()
        declared = int(r.headers.get("content-length") or 0)
        if declared > max_bytes:
            raise ValueError(f"ULDK zwróciło nieprawidłową odpowiedź ({declared // 1_000_000} MB) – spróbuj ponownie.")
        buf = bytearray()
        async for chunk in r.aiter_bytes():
            buf.extend(chunk)
            if len(buf) > max_bytes:
                raise ValueError("ULDK zwróciło nieprawidłową (zbyt dużą) odpowiedź – spróbuj ponownie.")
        return buf.decode(r.encoding or "utf-8", errors="replace")


# --------------------------------------------------------------------------- ULDK


def _parse_uldk(text: str) -> dict[str, Any]:
    """Parse ULDK text reply. Raises PlotNotFound on non-zero status."""
    lines = [ln.strip() for ln in text.strip().splitlines() if ln.strip()]
    status = lines[0].split()[0] if lines else ""
    if status != "0" or len(lines) < 2:
        detail = lines[0] if lines else "pusta odpowiedź"
        raise PlotNotFound(f"Nie znaleziono działki ewidencyjnej (ULDK: {detail}).")

    parts = lines[1].split("|")
    if len(parts) < 7:
        raise ValueError(f"Nieoczekiwany format odpowiedzi ULDK: {lines[1][:120]}")
    plot_id, geom_wkt, voiv, county, commune, region, parcel = (p.strip() for p in parts[:7])
    if ";" in geom_wkt:  # strip "SRID=4326;"
        geom_wkt = geom_wkt.split(";", 1)[1]

    geom = shapely_wkt.loads(geom_wkt)
    if not geom.is_valid:
        geom = geom.buffer(0)
    return {
        "plotId": plot_id,
        "geometry": mapping(geom),
        "voivodeship": voiv or None,
        "county": county or None,
        "commune": commune or None,
        "region": region or None,
        "parcelNumber": parcel or None,
    }


async def _fetch_uldk(
    client: httpx.AsyncClient, params: dict[str, str], cache_key: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Returns (parsed values, run_adapter response). Raises PlotError subclasses."""
    full_params = {**params, "result": ULDK_FIELDS, "srid": "4326"}
    url = _url(ULDK_URL, full_params)
    not_found: list[PlotNotFound] = []

    async def fetch() -> dict[str, Any]:
        text = await _get_text_limited(client, url)
        try:
            return _parse_uldk(text)
        except PlotNotFound as exc:
            not_found.append(exc)  # surfaced after run_adapter (which never raises)
            raise

    res = await run_adapter("ULDK GUGiK", url, cache_key, fetch, cache_ttl_sec=ULDK_CACHE_TTL)
    if not_found:
        raise not_found[0]
    if res["coverage"] != "full":
        raise PlotServiceUnavailable(
            "Usługa ULDK GUGiK (granice działek) jest chwilowo niedostępna: "
            + "; ".join(res["errors"])
        )
    return res["values"], res


# --------------------------------------------------------------------------- terrain


def _sample_points_2180(poly: BaseGeometry, grid: int = 5) -> list[Point]:
    """Points inside the plot: interior point, 4 extreme vertices, interior grid.

    Sampling is ~5 m inside the boundary so border ditches / roads don't skew slope.
    """
    inner = poly.buffer(-5.0)
    if inner.is_empty or inner.area < 0.2 * poly.area:
        inner = poly

    pts: list[Point] = [inner.representative_point()]

    coords = [c for g in getattr(inner, "geoms", [inner]) for c in g.exterior.coords]
    if coords:
        for key, pick in ((0, min), (0, max), (1, min), (1, max)):
            pts.append(Point(pick(coords, key=lambda c: c[key])))

    minx, miny, maxx, maxy = inner.bounds
    for i in range(grid):
        for j in range(grid):
            p = Point(minx + (i + 0.5) * (maxx - minx) / grid, miny + (j + 0.5) * (maxy - miny) / grid)
            if inner.contains(p):
                pts.append(p)

    seen: set[tuple[int, int]] = set()
    unique: list[Point] = []
    for p in pts:
        k = (round(p.x), round(p.y))
        if k not in seen:
            seen.add(k)
            unique.append(p)
    return unique


def _runoff_class(slope_pct: float | None) -> str:
    if slope_pct is None:
        return "unknown"
    if slope_pct < 1.5:
        return "low"
    if slope_pct <= 3.5:
        return "medium"
    return "high"


def _slope_from_heights(pts: list[Point], heights: list[float]) -> dict[str, Any]:
    valid = [(p, h) for p, h in zip(pts, heights) if h is not None and math.isfinite(h)]
    if len(valid) < 2:
        return {"slopePct": None, "runoffRisk": "unknown"}
    (p_lo, h_lo), (p_hi, h_hi) = min(valid, key=lambda t: t[1]), max(valid, key=lambda t: t[1])
    dist_m = p_lo.distance(p_hi)
    slope = None if dist_m == 0 else round((h_hi - h_lo) / dist_m * 100, 2)
    return {
        "slopePct": slope,
        "runoffRisk": _runoff_class(slope),
        "elevationMinM": round(h_lo, 1),
        "elevationMaxM": round(h_hi, 1),
        "deltaHM": round(h_hi - h_lo, 2),
        "distanceM": round(dist_m, 1),
        "pointsSampled": len(valid),
    }


async def _terrain(client: httpx.AsyncClient, plot_id: str, poly_2180: BaseGeometry) -> dict[str, Any]:
    pts = _sample_points_2180(poly_2180)
    key = {"plotId": plot_id, "points": [(round(p.x), round(p.y)) for p in pts]}

    # 1) GUGiK NMT – national LIDAR DEM (~1 m grid), point list in "northing easting".
    nmt_list = ",".join(f"{p.y:.1f} {p.x:.1f}" for p in pts)
    nmt_url = _url(NMT_URL, {"request": "GetHByPointList", "list": nmt_list})

    async def fetch_nmt() -> dict[str, Any]:
        r = await client.get(nmt_url)
        r.raise_for_status()
        heights = []
        for triple in r.text.strip().split(","):
            fields = triple.split()
            if len(fields) != 3:
                raise ValueError(f"Nieoczekiwana odpowiedź NMT: {r.text[:120]}")
            heights.append(float(fields[2]))
        if len(heights) != len(pts):
            raise ValueError("NMT zwrócił inną liczbę punktów niż zapytano.")
        return {**_slope_from_heights(pts, heights), "resolutionM": 1, "dem": "GUGiK NMT"}

    res = await run_adapter("GUGiK NMT (numeryczny model terenu)", nmt_url, key, fetch_nmt)
    errors = list(res["errors"])
    if res["coverage"] == "full":
        return {"values": res["values"], "sources": res["sources"], "errors": errors}

    # 2) Fallback: Open-Meteo Elevation (Copernicus DEM GLO-90, ~90 m) – coarse.
    lnglat = [_TO_4326.transform(p.x, p.y) for p in pts]
    om_params = {
        "latitude": ",".join(f"{lat:.6f}" for _, lat in lnglat),
        "longitude": ",".join(f"{lng:.6f}" for lng, _ in lnglat),
    }
    om_url = _url(OM_ELEVATION_URL, om_params)

    async def fetch_om() -> dict[str, Any]:
        r = await client.get(om_url)
        r.raise_for_status()
        heights = [float(h) if h is not None else math.nan for h in r.json()["elevation"]]
        return {**_slope_from_heights(pts, heights), "resolutionM": 90, "dem": "Copernicus GLO-90"}

    res = await run_adapter("Open-Meteo Elevation API", om_url, key, fetch_om)
    errors += res["errors"]
    if res["coverage"] == "full":
        return {"values": res["values"], "sources": res["sources"], "errors": errors}
    return {"values": None, "sources": [], "errors": errors}


# --------------------------------------------------------------------------- hydro


def _expanded_bbox_4326(poly_2180: BaseGeometry, margin_m: float) -> tuple[float, float, float, float]:
    minx, miny, maxx, maxy = poly_2180.bounds
    corners = [
        _TO_4326.transform(x, y)
        for x in (minx - margin_m, maxx + margin_m)
        for y in (miny - margin_m, maxy + margin_m)
    ]
    lngs, lats = [c[0] for c in corners], [c[1] for c in corners]
    return min(lats), min(lngs), max(lats), max(lngs)  # Overpass order: S, W, N, E


def _overpass_query(s: float, w: float, n: float, e: float) -> str:
    bb = f"({s:.6f},{w:.6f},{n:.6f},{e:.6f})"
    types = "|".join(WATERWAY_TYPES)
    return (
        "[out:json][timeout:9];"
        f'(way["waterway"~"^({types})$"]{bb};'
        f'way["natural"="water"]{bb};'
        f'relation["natural"="water"]{bb};);'
        "out geom;"
    )


def _water_geoms_2180(elements: Iterable[dict[str, Any]]) -> list[tuple[str, BaseGeometry]]:
    """Overpass `out geom` elements -> [(type, geometry in EPSG:2180)]."""
    out: list[tuple[str, BaseGeometry]] = []

    def line(nodes: list[dict[str, Any]] | None) -> list[tuple[float, float]]:
        return [_TO_2180.transform(nd["lon"], nd["lat"]) for nd in (nodes or []) if nd]

    for el in elements:
        tags = el.get("tags", {})
        kind = tags.get("waterway") or "water"  # natural=water -> "water"
        parts = [line(el.get("geometry"))] if el["type"] == "way" else [
            line(m.get("geometry")) for m in el.get("members", [])
        ]
        for coords in parts:
            if len(coords) < 2:
                continue
            g: BaseGeometry = LineString(coords)
            if kind == "water" and len(coords) >= 4 and coords[0] == coords[-1]:
                poly = Polygon(coords)
                g = poly if poly.is_valid else g
            out.append((kind, g))
    return out


def classify_water(poly_2180: BaseGeometry, elements: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Min distance plot boundary -> nearest water feature, bucketed."""
    nearest: tuple[float, str] | None = None
    for kind, g in _water_geoms_2180(elements):
        d = poly_2180.distance(g)  # 0 if touching / crossing the plot
        if d <= HYDRO_RADIUS_M and (nearest is None or d < nearest[0]):
            nearest = (d, kind)

    if nearest is None:
        return {"nearbyWater": False, "distanceClass": "none", "missing": None,
                "nearestDistanceM": None, "nearestType": None}
    d, kind = nearest
    cls = "adjacent" if d <= 30 else "near" if d <= 250 else "far"
    return {"nearbyWater": True, "distanceClass": cls, "missing": None,
            "nearestDistanceM": round(d, 1), "nearestType": kind}


HYDRO_MISSING = {
    "nearbyWater": None,
    "distanceClass": None,
    "missing": "brak danych hydro",
    "nearestDistanceM": None,
    "nearestType": None,
}


_overpass_dead_until: dict[str, float] = {}  # per-process circuit breaker
_ofm_tile_template: str | None = None  # cached `tiles[0]` from the tilejson


def _tile_range(s: float, w: float, n: float, e: float, z: int) -> list[tuple[int, int]]:
    def xy(lat: float, lng: float) -> tuple[int, int]:
        k = 2 ** z
        x = int((lng + 180.0) / 360.0 * k)
        y = int((1.0 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2.0 * k)
        return x, y

    x0, y0 = xy(n, w)
    x1, y1 = xy(s, e)
    return [(x, y) for x in range(x0, x1 + 1) for y in range(y0, y1 + 1)]


def _mvt_to_elements(tile: bytes, z: int, x: int, y: int) -> list[dict[str, Any]]:
    """Decode one MVT tile into Overpass-like elements (way + geometry nodes)."""
    import mapbox_vector_tile  # lazy: only needed on this path

    if tile[:2] == b"\x1f\x8b":
        tile = gzip.decompress(tile)
    layers = mapbox_vector_tile.decode(tile, default_options={"y_coord_down": True})
    k = 2 ** z
    out: list[dict[str, Any]] = []

    def to_ll(px: float, py: float, extent: int) -> dict[str, float]:
        fx, fy = (x + px / extent) / k, (y + py / extent) / k
        lat = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * fy))))
        return {"lon": fx * 360.0 - 180.0, "lat": lat}

    def rings(geom: dict[str, Any]) -> list[list[list[float]]]:
        t, c = geom["type"], geom["coordinates"]
        if t == "LineString":
            return [c]
        if t in ("MultiLineString", "Polygon"):
            return list(c)
        if t == "MultiPolygon":
            return [r for poly in c for r in poly]
        return []

    for layer, kind_of in (("waterway", lambda p: p.get("class")), ("water", lambda p: "water")):
        lyr = layers.get(layer)
        if not lyr:
            continue
        extent = lyr.get("extent", 4096)
        for f in lyr.get("features", []):
            kind = kind_of(f.get("properties", {}))
            if layer == "waterway" and kind not in WATERWAY_TYPES:
                continue
            tags = {"waterway": kind} if layer == "waterway" else {"natural": "water"}
            for ring in rings(f["geometry"]):
                out.append({"type": "way", "tags": tags,
                            "geometry": [to_ll(px, py, extent) for px, py in ring]})
    return out


async def _ofm_elements(client: httpx.AsyncClient, s: float, w: float, n: float, e: float) -> list[dict[str, Any]]:
    global _ofm_tile_template
    if _ofm_tile_template is None:
        r = await client.get(OFM_TILEJSON_URL, timeout=httpx.Timeout(6.0, connect=3.0))
        r.raise_for_status()
        _ofm_tile_template = r.json()["tiles"][0]
    tiles = _tile_range(s, w, n, e, OFM_ZOOM)
    if len(tiles) > 9:
        raise ValueError("obszar zbyt duży dla kafli OSM")

    async def one(x: int, y: int) -> list[dict[str, Any]]:
        url = _ofm_tile_template.format(z=OFM_ZOOM, x=x, y=y)  # type: ignore[union-attr]
        r = await client.get(url, timeout=httpx.Timeout(8.0, connect=3.0))
        if r.status_code == 204 or not r.content:
            return []  # empty tile
        r.raise_for_status()
        return _mvt_to_elements(r.content, OFM_ZOOM, x, y)

    parts = await asyncio.gather(*(one(x, y) for x, y in tiles))
    return [el for p in parts for el in p]


async def _hydro(client: httpx.AsyncClient, plot_id: str, poly_2180: BaseGeometry) -> dict[str, Any]:
    s, w, n, e = _expanded_bbox_4326(poly_2180, HYDRO_RADIUS_M)
    query = _overpass_query(s, w, n, e)
    key = {"plotId": plot_id, "bbox": [round(v, 5) for v in (s, w, n, e)], "radiusM": HYDRO_RADIUS_M}
    used_url: list[str] = []

    async def ask(url: str) -> tuple[str, dict[str, Any]]:
        try:
            r = await client.post(url, data={"data": query}, timeout=per_try)
            r.raise_for_status()
            body = r.json()
            remark = body.get("remark", "")
            if "error" in remark.lower() or "timed out" in remark.lower():
                raise ValueError(f"Overpass: {remark[:120]}")
            return url, body
        except Exception:
            _overpass_dead_until[url] = time.monotonic() + OVERPASS_COOLDOWN_SEC
            raise

    per_try = httpx.Timeout(HYDRO_TIMEOUT_SEC - 1.0, connect=4.0)

    async def tiles() -> tuple[str, dict[str, Any]]:
        try:
            return OFM_TILEJSON_URL, {"elements": await _ofm_elements(client, s, w, n, e)}
        except Exception:
            global _ofm_tile_template
            _ofm_tile_template = None  # tileset version may have rotated
            raise

    async def fetch() -> dict[str, Any] | PartialResult:
        now = time.monotonic()
        live = [u for u in OVERPASS_URLS if _overpass_dead_until.get(u, 0.0) <= now]
        # all in cooldown -> still try everything rather than give up without asking
        overpass = [asyncio.create_task(ask(u)) for u in (live or OVERPASS_URLS)]
        tile_task = asyncio.create_task(tiles())
        tasks = [*overpass, tile_task]
        last_exc: BaseException | None = None
        tile_answer: tuple[str, dict[str, Any]] | None = None

        def done(answer: tuple[str, dict[str, Any]]) -> dict[str, Any]:
            used_url.append(answer[0])
            return classify_water(poly_2180, answer[1].get("elements", []))

        try:
            deadline = time.monotonic() + OVERPASS_PREFERRED_SEC
            pending = set(tasks)
            while pending:
                wait = None if tile_answer is None else max(0.0, deadline - time.monotonic())
                finished, pending = await asyncio.wait(pending, timeout=wait,
                                                       return_when=asyncio.FIRST_COMPLETED)
                if not finished:  # Overpass head start used up -> take the tiles
                    break
                for fut in finished:
                    exc = fut.exception()
                    if exc is not None:
                        last_exc = exc
                    elif fut is tile_task:
                        tile_answer = fut.result()
                    else:
                        return done(fut.result())  # Overpass answered: preferred
                if tile_answer is not None and not (pending - {tile_task}):
                    break  # every Overpass mirror failed
            if tile_answer is not None:
                return done(tile_answer)
        finally:
            for t in tasks:
                t.cancel()
        assert last_exc is not None
        raise last_exc

    res = await run_adapter(
        "OpenStreetMap (Overpass API)", OVERPASS_URLS[0], key, fetch,
        timeout_sec=HYDRO_TIMEOUT_SEC, cache_ttl_sec=HYDRO_CACHE_TTL,
    )
    if res["coverage"] != "full":
        return {"values": dict(HYDRO_MISSING), "sources": [], "errors": res["errors"]}
    sources = res["sources"]
    if used_url and used_url[0] == OFM_TILEJSON_URL:
        sources = [{**src, "name": "OpenStreetMap (kafle OpenFreeMap)", "url": "https://openfreemap.org"}
                   for src in sources]
    elif used_url and used_url[0] != OVERPASS_URLS[0]:
        sources = [{**src, "url": used_url[0]} for src in sources]
    return {"values": res["values"], "sources": sources, "errors": []}


# --------------------------------------------------------------------------- public API


LIMITATIONS = [
    "Granice działki pochodzą z ULDK GUGiK (EGiB) – stan na dzień pobrania, bez weryfikacji w terenie.",
    "Spadek terenu to różnica wysokości między najwyższym i najniższym z kilkunastu punktów "
    "próbkowanych w obrębie działki – wskaźnik orientacyjny, nie pełna analiza spływu.",
    "Rodzaj użytku (pole, łąka, pastwisko, las…) pochodzi wyłącznie z ewidencji gruntów EGiB (usługa KIEG "
    "GUGiK). Gdy starostwo nie publikuje użytków, raport podaje „brak danych” – niczego nie zgadujemy.",
    "Cieki, rowy i zbiorniki pochodzą z OpenStreetMap – rowy melioracyjne mogą być niekompletnie "
    "zmapowane, więc „brak wody w pobliżu” nie wyklucza istnienia rowu.",
]


def _base_plot(uldk_values: dict[str, Any], uldk_res: dict[str, Any]) -> dict[str, Any]:
    """Plot identity + geometry only (fast: one ULDK call). terrain/hydro are None."""
    geom = shape(uldk_values["geometry"])
    return {
        "plotId": uldk_values["plotId"],
        "geometry": uldk_values["geometry"],
        "centroid": centroid(geom),
        "areaHa": area_ha(geom),
        "bbox": bbox_from_geometry(geom),
        "voivodeship": uldk_values.get("voivodeship"),
        "county": uldk_values.get("county"),
        "commune": uldk_values.get("commune"),
        "region": uldk_values.get("region"),
        "parcelNumber": uldk_values.get("parcelNumber"),
        "terrain": None,
        "hydro": None,
        "landUse": None,
        "sources": list(uldk_res["sources"]),
        "missingData": [],
        "limitations": LIMITATIONS,
        "fetchedAt": utc_now_iso(),
    }


async def add_plot_context(plot: dict[str, Any], client: httpx.AsyncClient | None = None) -> dict[str, Any]:
    """Fill `terrain` (GUGiK NMT slope), `hydro` (OSM water distance) and `landUse`
    (EGiB register only, see adapters/land_use.py). Never raises.

    Run this *concurrently* with the meteo/soil/satellite adapters in /analyze:
        plot = await resolve_plot(pid, with_context=False)
        plot, meteo, soil, sat, edo = await asyncio.gather(add_plot_context(plot), fetch_meteo(...), ...)
    so a slow/unreachable Overpass does not add to the critical path.
    """
    own = client is None
    client = client or _client()
    try:
        poly_2180 = to_2180(shape(plot["geometry"]))
        terrain_r, hydro_r, (land_use, lu_sources, lu_errors) = await asyncio.gather(
            _terrain(client, plot["plotId"], poly_2180),
            _hydro(client, plot["plotId"], poly_2180),
            classify_land_use(plot["plotId"], poly_2180, client),
        )
    finally:
        if own:
            await client.aclose()

    missing: list[str] = []
    if terrain_r["values"] is None:
        terrain = {"slopePct": None, "runoffRisk": "unknown"}
        missing.append("Ukształtowanie terenu (spadek): brak danych wysokościowych – "
                       + "; ".join(terrain_r["errors"]))
    else:
        terrain = terrain_r["values"]
        if terrain.get("slopePct") is None:
            missing.append("Ukształtowanie terenu: nie udało się wyznaczyć spadku (za mało punktów).")
        if terrain.get("resolutionM", 0) >= 90:
            missing.append("Spadek policzony z modelu terenu o niskiej rozdzielczości (~90 m) – "
                           "główne źródło NMT GUGiK było niedostępne; wynik przybliżony.")
    hydro = hydro_r["values"]
    if hydro.get("missing"):
        missing.append("Cieki i rowy w pobliżu: brak danych hydro – " + "; ".join(hydro_r["errors"]))

    limitations = list(plot.get("limitations") or [])
    if land_use.get("category") is None:
        missing.append("Użytkowanie terenu: " + "; ".join(land_use["notes"] or lu_errors))
    elif land_use.get("isAgricultural") is False:
        limitations.insert(0, f"UWAGA: w ewidencji gruntów (EGiB) działka to: {land_use['labelPl']} – nie pole "
                              "uprawne, łąka, pastwisko ani sad. Zalecenia rolnicze w tym raporcie mogą nie mieć "
                              "zastosowania.")

    return {
        **plot,
        "terrain": terrain,
        "hydro": hydro,
        "landUse": land_use,
        "sources": plot["sources"] + terrain_r["sources"] + hydro_r["sources"] + lu_sources,
        "missingData": plot.get("missingData", []) + missing,
        "limitations": limitations,
        "fetchedAt": utc_now_iso(),
    }


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(timeout=HTTP_TIMEOUT, headers={"User-Agent": USER_AGENT}, follow_redirects=True)


async def resolve_plot(plot_id: str, with_context: bool = True) -> dict[str, Any]:
    """Resolve by full cadastral ID, e.g. '040308_5.0004.17220'.

    with_context=False returns right after ULDK (terrain/hydro = None); call
    `add_plot_context()` in parallel with other adapters to fill them.
    """
    plot_id = (plot_id or "").strip()
    if not _PLOT_ID_RE.match(plot_id):
        raise InvalidPlotInput(
            "Niepoprawny identyfikator działki. Podaj pełny identyfikator, np. 040308_5.0004.17220."
        )
    async with _client() as client:
        values, res = await _fetch_uldk(client, {"request": "GetParcelById", "id": plot_id}, {"id": plot_id})
        plot = _base_plot(values, res)
        return await add_plot_context(plot, client) if with_context else plot


_REGION_ID_RE = re.compile(r"^\d{6}_\d\.\d{4}$")
_PARCEL_NR_RE = re.compile(r"^[0-9A-Za-z_.\-/]{1,40}$")
REGION_LIMIT = 200


def _parse_regions(text: str) -> list[dict[str, Any]]:
    """ULDK GetRegionByNameOrId reply -> list of obręby. '-1 brak wyników' -> []."""
    lines = [ln.strip() for ln in text.strip().splitlines() if ln.strip()]
    if not lines or lines[0].split()[0] != "0":
        return []
    out: list[dict[str, Any]] = []
    for ln in lines[1:]:
        parts = [p.strip() for p in ln.split("|")]
        if len(parts) < 6:
            continue
        rid, commune, county, voiv, region, extent = parts[:6]
        bbox = None
        try:
            nums = [float(v) for v in extent.split(",")]
            if len(nums) == 4:
                bbox = [round(v, 6) for v in nums]  # [min_lng, min_lat, max_lng, max_lat]
        except ValueError:
            pass
        out.append({
            "regionId": rid,
            "region": region or None,
            "commune": commune or None,
            "county": county or None,
            "voivodeship": voiv or None,
            "bbox": bbox,
        })
    out.sort(key=lambda r: (r["voivodeship"] or "", r["county"] or "", r["commune"] or ""))
    return out[:REGION_LIMIT]


# --------------------------------------------------------------------------- village (obręb) search

OBREBY_INDEX_PATH = Path(__file__).parent / "data" / "obreby.json.gz"
REGION_SEARCH_LIMIT = 50
_PL_FOLD = str.maketrans("ąćęłńóśźżĄĆĘŁŃÓŚŹŻ", "acelnoszzACELNOSZZ")


def fold(text: str) -> str:
    """Case- and diacritic-insensitive key: 'Żółwin-Kolonia' -> 'zolwin kolonia'."""
    t = unicodedata.normalize("NFKD", (text or "").translate(_PL_FOLD))
    t = "".join(c for c in t if not unicodedata.combining(c)).lower()
    return " ".join(re.sub(r"[^0-9a-z]+", " ", t).split())


@lru_cache(maxsize=1)
def _obreby_index() -> dict[str, Any] | None:
    """Offline list of all named obręby (PRG, see build_obreby_index.py). None if missing."""
    try:
        with gzip.open(OBREBY_INDEX_PATH, "rt", encoding="utf-8") as f:
            idx = json.load(f)
    except (OSError, ValueError):
        return None
    communes: dict[str, str] = idx["communes"]
    by6: dict[str, str] = {}
    for code, name in sorted(communes.items()):
        by6.setdefault(code[:6], name)
    rows = []
    for rid, name in idx["regions"]:
        commune = communes.get(rid[:6] + rid[7]) or by6.get(rid[:6])
        county = idx["counties"].get(rid[:4])
        voiv = idx["voivodeships"].get(rid[:2])
        rows.append({
            "regionId": rid,
            "region": name,
            "commune": commune,
            "county": county,
            "voivodeship": voiv,
            "_name": fold(name),
            "_where": fold(" ".join(filter(None, [commune, county, voiv]))),
        })
    return {"rows": rows, "fetchedAt": idx.get("fetchedAt"), "source": idx.get("source")}


def _public(row: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in row.items() if not k.startswith("_")} | {"bbox": None}


async def search_regions(query: str) -> dict[str, Any]:
    """Village (obręb) search – diacritic-insensitive, prefix-matching.

    `query` may carry a commune/county after a comma: "Zalesie, Ryki".
    Returns {"regions": [...<=50], "total": n}. bbox is filled later by `region_details`.
    Falls back to ULDK exact-name search when the offline index is missing.
    """
    name_part, _, where_part = (query or "").partition(",")
    name, where = fold(name_part), fold(where_part)
    if len(name) < 2 or len(query) > 120:
        raise InvalidPlotInput("Wpisz co najmniej 2 litery nazwy miejscowości.")

    idx = _obreby_index()
    if idx is None:
        found = await _search_regions_uldk(name_part)
        return {"regions": found[:REGION_SEARCH_LIMIT], "total": len(found)}

    where_words = where.split()
    hits: list[tuple[int, dict[str, Any]]] = []
    for row in idx["rows"]:
        n = row["_name"]
        if n == name:
            rank = 0
        elif n.startswith(name):
            rank = 1
        elif len(name) >= 3 and f" {name}" in f" {n}":
            rank = 2  # a later word, e.g. "wies" -> "Stara Wieś"
        else:
            continue
        if where_words and not all(f" {w}" in f" {row['_where']}" for w in where_words):
            continue
        hits.append((rank, row))
    hits.sort(key=lambda h: (h[0], h[1]["_name"], h[1]["voivodeship"] or "", h[1]["county"] or "", h[1]["commune"] or ""))
    return {"regions": [_public(r) for _, r in hits[:REGION_SEARCH_LIMIT]], "total": len(hits)}


async def region_details(region_id: str) -> dict[str, Any]:
    """One obręb with its bbox (live from ULDK) – used to zoom the map to the chosen village."""
    region_id = (region_id or "").strip()
    if not _REGION_ID_RE.match(region_id):
        raise InvalidPlotInput("Niepoprawny identyfikator obrębu.")
    found = await _search_regions_uldk(region_id)
    if not found:
        raise PlotNotFound("Nie znaleziono takiej miejscowości (obrębu) w ULDK.")
    out = found[0]
    idx = _obreby_index()
    if idx is not None:  # nicer casing / names from the index when ULDK returns UPPERCASE
        row = next((r for r in idx["rows"] if r["regionId"] == region_id), None)
        if row:
            out = {**out, **{k: v for k, v in _public(row).items() if v and k != "bbox"}}
    return out


async def _search_regions_uldk(name: str) -> list[dict[str, Any]]:
    """Find cadastral precincts (obręby ≈ villages) by exact name, case-insensitive.

    ULDK matches the full name only (no prefix search). Returns [] when nothing matches.
    """
    name = " ".join((name or "").split())
    if len(name) < 2 or len(name) > 80:
        raise InvalidPlotInput("Wpisz nazwę miejscowości (obrębu), np. Krzewina.")
    params = {
        "request": "GetRegionByNameOrId",
        "id": name,
        "result": "id,commune,county,voivodeship,region,geom_extent",
        "srid": "4326",
    }
    url = _url(ULDK_URL, params)

    async with _client() as client:
        async def fetch() -> dict[str, Any]:
            return {"regions": _parse_regions(await _get_text_limited(client, url))}

        res = await run_adapter(
            "ULDK GUGiK", url, {"region": name.lower()}, fetch, cache_ttl_sec=ULDK_CACHE_TTL
        )
    if res["coverage"] != "full":
        raise PlotServiceUnavailable(
            "Usługa ULDK GUGiK (wyszukiwanie miejscowości) jest chwilowo niedostępna: "
            + "; ".join(res["errors"])
        )
    return res["values"]["regions"]


async def region_extent(region_id: str) -> list[float] | None:
    """Bounding box [min_lng, min_lat, max_lng, max_lat] of one obręb from ULDK, or None.

    Only used to zoom the map after the farmer picks a village; failing is harmless.
    """
    region_id = (region_id or "").strip()
    if not _REGION_ID_RE.match(region_id):
        raise InvalidPlotInput("Niepoprawny identyfikator obrębu.")
    params = {
        "request": "GetRegionByNameOrId",
        "id": region_id,
        "result": "id,commune,county,voivodeship,region,geom_extent",
        "srid": "4326",
    }
    url = _url(ULDK_URL, params)
    async with _client() as client:
        async def fetch() -> dict[str, Any]:
            regions = _parse_regions(await _get_text_limited(client, url))
            hit = next((r for r in regions if r["regionId"] == region_id and r["bbox"]), None)
            if hit is None:
                raise ValueError("ULDK nie podało zasięgu obrębu.")
            return {"bbox": hit["bbox"]}

        res = await run_adapter("ULDK GUGiK", url, {"region_extent": region_id}, fetch, timeout_sec=10)
    return res["values"].get("bbox") if res["coverage"] == "full" else None


async def resolve_region_parcel(region_id: str, parcel_nr: str, with_context: bool = True) -> dict[str, Any]:
    """Resolve 'obręb + numer działki' (e.g. 022503_5.0003 + 134) to a plot."""
    region_id = (region_id or "").strip()
    parcel_nr = (parcel_nr or "").strip().replace(" ", "")
    if not _REGION_ID_RE.match(region_id):
        raise InvalidPlotInput("Niepoprawny identyfikator obrębu. Wybierz miejscowość z listy.")
    if not _PARCEL_NR_RE.match(parcel_nr):
        raise InvalidPlotInput("Niepoprawny numer działki. Wpisz np. 134 albo 134/2.")
    try:
        return await resolve_plot(f"{region_id}.{parcel_nr}", with_context=with_context)
    except PlotNotFound as exc:
        raise PlotNotFound(
            f"W tej miejscowości nie znaleziono działki nr {parcel_nr}. Sprawdź numer na wypisie "
            "z rejestru gruntów albo kliknij działkę na mapie."
        ) from exc


async def resolve_point(lat: float, lng: float, with_context: bool = True) -> dict[str, Any]:
    """Resolve the plot containing a map click (WGS84). See `resolve_plot` for with_context."""
    if not (48.9 <= lat <= 55.0 and 14.0 <= lng <= 24.2):
        raise InvalidPlotInput("Wskazany punkt leży poza obszarem Polski.")
    xy = f"{lng:.7f},{lat:.7f},4326"  # ULDK: lng,lat order!
    async with _client() as client:
        values, res = await _fetch_uldk(
            client, {"request": "GetParcelByXY", "xy": xy}, {"lat": round(lat, 6), "lng": round(lng, 6)}
        )
        plot = _base_plot(values, res)
        return await add_plot_context(plot, client) if with_context else plot


# --------------------------------------------------------------------------- smoke test

if __name__ == "__main__":
    import time

    TEST_POINTS = {
        "kujawsko-pomorskie": (53.05, 18.25),
        "wielkopolskie": (52.35, 17.15),
        "lubelskie": (51.15, 22.85),
    }

    def _summary(p: dict[str, Any]) -> str:
        t, h = p["terrain"], p["hydro"]
        return (
            f"  plotId={p['plotId']}  {p['voivodeship']} / {p['commune']} / obręb {p['region']} / nr {p['parcelNumber']}\n"
            f"  centroid={p['centroid']}  areaHa={p['areaHa']}  bbox={p['bbox']}\n"
            f"  terrain: slope={t.get('slopePct')}%  risk={t.get('runoffRisk')}  "
            f"h={t.get('elevationMinM')}–{t.get('elevationMaxM')} m  pts={t.get('pointsSampled')}  dem={t.get('dem')}\n"
            f"  hydro:   {h}\n"
            f"  sources: {[s['name'] for s in p['sources']]}\n"
            f"  missing: {p['missingData']}"
        )

    async def _main() -> None:
        for label, (lat, lng) in TEST_POINTS.items():
            print(f"\n=== {label} ({lat}, {lng})")
            t0 = time.perf_counter()
            try:
                p = await resolve_point(lat, lng)
            except PlotError as exc:
                print("  ERROR:", exc)
                continue
            print(f"  by-point {time.perf_counter() - t0:.2f}s")
            print(_summary(p))

            t0 = time.perf_counter()
            p2 = await resolve_plot(p["plotId"])
            print(f"  by-id    {time.perf_counter() - t0:.2f}s  same geometry: {p2['geometry'] == p['geometry']}")

        print("\n=== not-found check")
        try:
            await resolve_plot("999999_9.9999.1")
        except PlotNotFound as exc:
            print("  OK PlotNotFound:", exc)

    asyncio.run(_main())
