"""Satellite adapter: Sentinel-2 L2A NDVI / NDMI for the plot, no API keys.

1. STAC search on AWS Earth Search v1 (sentinel-2-l2a), 21-day window ending on
   the analysis date, newest first.
2. For each scene: windowed COG read (HTTP range requests) of ONLY the plot's
   pixels – never whole tiles. SCL is read first; if the plot is too cloudy the
   scene is rejected before the spectral bands are downloaded.
3. Pixel-level masking with SCL + the plot polygon, then NDVI and NDMI means.

Radiometry: reflectance = DN × scale + offset; see `_scale_offset` for how the
ESA processing-baseline 04.00 change (Jan 2022, BOA_ADD_OFFSET) is handled.

Only fetches and averages. Whether an NDVI value is "low" depends on the crop and
its growth stage – that interpretation belongs to the engine.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import math
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta
from typing import Any

import httpx
import numpy as np
import rasterio
import shapely
from pyproj import Transformer
from rasterio.enums import Resampling
from rasterio.features import geometry_mask
from rasterio.windows import Window, from_bounds
from rasterio.windows import bounds as window_bounds
from rasterio.windows import transform as window_transform
from shapely.geometry import box, mapping, shape

from .base import PartialResult, run_adapter
from .dates import shift_years, today_pl

STAC_URL = "https://earth-search.aws.element84.com/v1/search"
COLLECTION = "sentinel-2-l2a"
WINDOW_DAYS = 21
MAX_SCENE_CLOUD = 45        # whole-tile cloud cover filter in STAC
MAX_PLOT_UNUSABLE_PCT = 35  # reject scene if more of the plot than this is unusable
STAC_LIMIT = 10             # each acquisition often appears twice (overlapping MGRS tiles)
RECENT_DAYS = 7

# Sentinel-2 Scene Classification Layer
SCL_CLOUD = (0, 3, 8, 9, 10)  # no data, cloud shadow, cloud medium/high, cirrus
SCL_UNUSABLE = SCL_CLOUD + (1, 11)  # + saturated/defective, snow – unusable for indices
SCL_WATER = (6,)

# Pixel-share thresholds (plain arithmetic on the plot's pixels, documented in docs/verify.md)
BARE_NDVI = 0.2        # below: bare soil / stubble without green cover
VEG_NDVI = 0.3         # above: green vegetation present
WEAK_ZONE_DELTA = 0.15  # pixel NDVI this far below the plot median = visibly weaker part of the field
DRY_NDMI = 0.0         # vegetated pixel with NDMI below 0 = canopy holds little water

HISTORY_YEARS = 5
HISTORY_TIMEOUT_SEC = 20.0  # per year; runs in the background (see app/adapters/live.py)
_HISTORY_POOL = ThreadPoolExecutor(max_workers=4, thread_name_prefix="s2-history")

GDAL_ENV = {
    "GDAL_DISABLE_READDIR_ON_OPEN": "EMPTY_DIR",
    "CPL_VSIL_CURL_ALLOWED_EXTENSIONS": ".tif",
    "GDAL_HTTP_MULTIRANGE": "YES",
    "GDAL_HTTP_MERGE_CONSECUTIVE_RANGES": "YES",
    "GDAL_HTTP_TIMEOUT": "10",
    "GDAL_HTTP_MAX_RETRY": "2",
    "VSI_CACHE": "TRUE",
    "AWS_NO_SIGN_REQUEST": "YES",
}


# --------------------------------------------------------------------------- helpers


def _today() -> date:
    return today_pl()


def _parse_date(value: date | str) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value).strip()[:10])


def _scale_offset(item: dict[str, Any], key: str) -> tuple[float, float]:
    """Reflectance = DN × scale (offset deliberately 0).

    ESA baseline ≥ 04.00 (from 25 Jan 2022) defines BOA_ADD_OFFSET = −1000 DN, and
    Earth Search advertises `raster:bands.offset = -0.1` on those items. Verified on
    real pixels, however, the COGs in `sentinel-cogs` do NOT contain the +1000:
    baseline 04.00/05.00/05.09 scenes over PL fields (both values of
    `earthsearch:boa_offset_applied`) have red DN p5 ≈ 190–440, impossible with +1000
    inside. Applying the advertised offset made red negative -> NDVI ≡ 1.0.
    `_offset_suspected` + the negative-reflectance guard catch it if that ever changes.
    """
    band = (item["assets"][key].get("raster:bands") or [{}])[0]
    return float(band.get("scale", 0.0001)), 0.0


def _offset_suspected(item: dict[str, Any], red_raw: np.ndarray, valid: np.ndarray) -> bool:
    """True if DN look like they still carry +1000 (no plot pixel darker than 1000)."""
    props = item["properties"]
    try:
        baseline = float(props.get("s2:processing_baseline", "0"))
    except ValueError:
        baseline = 0.0
    return baseline >= 4.0 and bool(valid.any()) and int(red_raw[valid].min()) >= 1000


async def _search(client: httpx.AsyncClient, bbox: list[float], d: date) -> list[dict[str, Any]]:
    start = d - timedelta(days=WINDOW_DAYS)
    payload = {
        "collections": [COLLECTION],
        "bbox": bbox,
        "datetime": f"{start.isoformat()}T00:00:00Z/{d.isoformat()}T23:59:59Z",
        "query": {"eo:cloud_cover": {"lt": MAX_SCENE_CLOUD}},
        "sortby": [{"field": "properties.datetime", "direction": "desc"}],
        "limit": STAC_LIMIT,
    }
    r = await client.post(STAC_URL, json=payload)
    r.raise_for_status()
    feats = r.json().get("features", [])
    return sorted(feats, key=lambda f: f["properties"]["datetime"], reverse=True)


# --------------------------------------------------------------------------- raster reads (blocking -> threads)


def _grid(red_href: str, geom_4326) -> dict[str, Any]:
    """10 m pixel grid (window, transform, plot mask) in the raster CRS."""
    with rasterio.Env(**GDAL_ENV), rasterio.open(red_href) as ds:
        to_crs = Transformer.from_crs("EPSG:4326", ds.crs, always_xy=True)
        g = shapely.transform(geom_4326, to_crs.transform, interleaved=False)
        w = from_bounds(*g.bounds, transform=ds.transform)
        col0, row0 = math.floor(w.col_off), math.floor(w.row_off)
        col1, row1 = math.ceil(w.col_off + w.width), math.ceil(w.row_off + w.height)
        win = Window(col0, row0, max(1, col1 - col0), max(1, row1 - row0))
        tr = window_transform(win, ds.transform)
        shape_ = (int(win.height), int(win.width))
        mask = geometry_mask([mapping(g)], out_shape=shape_, transform=tr, invert=True)
        if not mask.any():  # tiny/thin plot: take every touched pixel
            mask = geometry_mask([mapping(g)], out_shape=shape_, transform=tr, invert=True, all_touched=True)
        return {"bounds": window_bounds(win, ds.transform), "shape": shape_, "mask": mask}


def _read(href: str, grid: dict[str, Any]) -> np.ndarray:
    """Read only the plot window, resampled (nearest) onto the 10 m grid."""
    with rasterio.Env(**GDAL_ENV), rasterio.open(href) as ds:
        win = from_bounds(*grid["bounds"], transform=ds.transform)
        return ds.read(
            1, window=win, out_shape=grid["shape"], resampling=Resampling.nearest,
            boundless=True, fill_value=0,
        )


async def _process_scene(item: dict[str, Any], geom_4326, d: date,
                         pool: ThreadPoolExecutor | None = None) -> dict[str, Any]:
    """Returns {'ok': True, values...} or {'ok': False, 'reason': ...}."""
    assets = item["assets"]
    loop = asyncio.get_running_loop()

    def run(fn, *args):  # blocking GDAL read in `pool` (None = default executor)
        return loop.run_in_executor(pool, fn, *args)

    grid = await run(_grid, assets["red"]["href"], geom_4326)
    plot = grid["mask"]
    n_plot = int(plot.sum())

    scl = await run(_read, assets["scl"]["href"], grid)
    cloud = plot & np.isin(scl, SCL_CLOUD)
    unusable = plot & np.isin(scl, SCL_UNUSABLE)
    cloud_pct = 100.0 * cloud.sum() / n_plot
    unusable_pct = 100.0 * unusable.sum() / n_plot
    scene_date = item["properties"]["datetime"][:10]
    if unusable_pct > MAX_PLOT_UNUSABLE_PCT:
        return {"ok": False, "reason": f"{scene_date} ({item['id']}): {unusable_pct:.0f}% działki "
                                       "zakryte chmurami/cieniem/śniegiem lub poza kaflem"}

    red_raw, nir_raw, swir_raw = await asyncio.gather(
        *(run(_read, assets[k]["href"], grid) for k in ("red", "nir", "swir16"))
    )

    def refl(raw: np.ndarray, key: str) -> np.ndarray:
        scale, offset = _scale_offset(item, key)
        return raw.astype("float64") * scale + offset

    red, nir, swir = refl(red_raw, "red"), refl(nir_raw, "nir"), refl(swir_raw, "swir16")
    valid = plot & ~unusable & (red_raw > 0) & (nir_raw > 0) & (swir_raw > 0)
    valid &= (nir + red) > 0
    valid &= (nir + swir) > 0
    n_valid = int(valid.sum())
    if n_valid == 0:
        return {"ok": False, "reason": f"{scene_date}: brak poprawnych pikseli na działce"}

    # Physical sanity guard: surface reflectance must be ≥ 0. Many negatives mean the
    # radiometric scaling is wrong for this scene -> reject rather than report nonsense.
    neg = (red[valid] < 0) | (nir[valid] < 0) | (swir[valid] < 0)
    if neg.mean() > 0.05:
        return {"ok": False, "reason": f"{scene_date}: niespójna radiometria sceny "
                                       f"({100 * neg.mean():.0f}% pikseli z ujemnym odbiciem)"}

    notes: list[str] = []
    if _offset_suspected(item, red_raw, valid):
        notes.append("Możliwy nieusunięty offset radiometryczny (baseline ≥ 04.00) – NDVI może być zaniżony.")

    ndvi = np.clip((nir[valid] - red[valid]) / (nir[valid] + red[valid]), -1, 1)
    ndmi = np.clip((nir[valid] - swir[valid]) / (nir[valid] + swir[valid]), -1, 1)
    water = np.isin(scl[valid], SCL_WATER)
    ndvi_median = float(np.median(ndvi))
    vegetated = ndvi >= VEG_NDVI
    sd = date.fromisoformat(scene_date)

    def pct(m: np.ndarray, of: int = n_valid) -> float:
        return round(100.0 * float(m.sum()) / of, 1) if of else 0.0

    return {
        "notes": notes,
        "ok": True,
        "ndvi_mean": round(float(ndvi.mean()), 3),
        "ndvi_std": round(float(ndvi.std()), 3),  # in-field variability
        "ndvi_median": round(ndvi_median, 3),
        "ndvi_p10": round(float(np.percentile(ndvi, 10)), 3),
        "ndvi_p90": round(float(np.percentile(ndvi, 90)), 3),
        "ndmi_mean": round(float(ndmi.mean()), 3),
        # Simple pixel shares (no ML): thresholds documented in docs/verify.md.
        "bare_soil_pct": pct((ndvi < BARE_NDVI) & ~water),
        "water_pct": pct(water),
        "weak_zone_pct": pct(ndvi < ndvi_median - WEAK_ZONE_DELTA) if ndvi_median >= VEG_NDVI else 0.0,
        "ndmi_dry_pct": pct(vegetated & (ndmi < DRY_NDMI), int(vegetated.sum())) if vegetated.any() else None,
        "scene_date": scene_date,
        "scene_id": item["id"],
        "days_before_analysis": (d - sd).days,
        "plot_cloud_pct": round(cloud_pct, 1),
        "valid_pixels": n_valid,
        "plot_pixels": n_plot,
        "resolution_m": 10,
    }


# --------------------------------------------------------------------------- public API


async def fetch_sentinel(
    bbox: list[float], analysis_date: date | str, geometry: dict[str, Any] | None = None,
    *, timeout_sec: float = 20.0, pool: ThreadPoolExecutor | None = None,
) -> dict[str, Any]:
    """NDVI/NDMI from the newest clear Sentinel-2 scene ≤ analysis_date. Never raises."""
    try:
        bb = [round(float(v), 4) for v in bbox]
        d = _parse_date(analysis_date)
        geom = shape(geometry) if geometry else box(*bbox)
        geom_digest = hashlib.sha256(json.dumps(mapping(geom), sort_keys=True).encode()).hexdigest()[:16]
        bad = None
    except Exception as exc:
        bb, d, geom, geom_digest = [0.0] * 4, _today(), None, ""
        bad = f"Niepoprawne dane wejściowe dla Sentinel-2: {exc}"

    recent = (_today() - d).days <= RECENT_DAYS
    # Archive is complete for dates > 30 days old: "no clear scene" is then a stable,
    # cacheable answer (re-checking would re-download every cloudy scene again).
    archive_stable = (_today() - d).days > 30

    async def fetch() -> dict[str, Any] | PartialResult:
        if bad:
            return PartialResult({}, [bad])
        if d > _today():
            return PartialResult({}, [f"Data analizy {d} jest z przyszłości."])

        async with httpx.AsyncClient(timeout=httpx.Timeout(10.0, connect=5.0)) as client:
            items = await _search(client, bb, d)
        if not items:
            return PartialResult({}, [f"Brak zdjęć Sentinel-2 z zachmurzeniem < {MAX_SCENE_CLOUD}% "
                                      f"w ciągu {WINDOW_DAYS} dni przed {d}."], definitive=archive_stable)

        # The same acquisition is often published as 2 overlapping MGRS tiles. Prefer the
        # tile whose data footprint fully contains the plot; once an acquisition is
        # rejected for clouds, don't re-read it from the neighbouring tile.
        def acq(it: dict[str, Any]) -> str:
            return it["properties"]["datetime"][:16]

        def covers(it: dict[str, Any]) -> bool:
            try:
                return shape(it["geometry"]).contains(geom)
            except Exception:
                return False

        has_full = {acq(it) for it in items if covers(it)}
        rejected: list[str] = []
        cloudy: set[str] = set()
        for item in items:
            if acq(item) in cloudy or (acq(item) in has_full and not covers(item)):
                continue
            try:
                res = await _process_scene(item, geom, d, pool)
            except Exception as exc:  # one broken COG must not kill the rest
                rejected.append(f"{item['id']}: błąd odczytu ({type(exc).__name__})")
                continue
            if res.pop("ok"):
                res["scenes_rejected"] = rejected
                return res
            rejected.append(res["reason"])
            if acq(item) in has_full:
                cloudy.add(acq(item))

        read_failed = any("błąd odczytu" in r for r in rejected)  # transient -> don't cache
        return PartialResult({}, [f"Brak czystego zdjęcia działki w ciągu {WINDOW_DAYS} dni przed {d} "
                                  f"(sprawdzono {len(items)} scen)."] + rejected,
                             definitive=archive_stable and not read_failed)

    return await run_adapter(
        "Sentinel-2 L2A (Copernicus, AWS Earth Search)",
        STAC_URL,
        {"bbox": bb, "analysis_date": d.isoformat(), "geom": geom_digest, "v": 4},
        fetch,
        timeout_sec=timeout_sec,
        cache_ttl_sec=3600 if recent else None,
    )


async def fetch_sentinel_history(
    bbox: list[float], analysis_date: date | str, geometry: dict[str, Any] | None = None,
    years: int = HISTORY_YEARS,
) -> dict[str, Any]:
    """Same 21-day window in each of the previous `years` years -> per-year NDVI/NDMI + medians.

    Gives the engine a "what is normal for THIS plot at THIS time of year" baseline, so a
    single NDVI/NDMI value can be read as an anomaly instead of an absolute number.
    Each year is one `fetch_sentinel` call (cached forever: the archive no longer changes).
    Never raises; returns the usual adapter response shape.
    """
    try:
        d = _parse_date(analysis_date)
    except Exception:
        d = _today()
    targets = [shift_years(d, -k) for k in range(1, years + 1)]
    # Own small thread pool + shorter timeout: the history must never starve the current
    # scene (it shares the default executor with every other adapter). Years that finish
    # are cached for good, so a cut-short run fills in on the next request.
    resps = await asyncio.gather(*(fetch_sentinel(bbox, t, geometry, timeout_sec=HISTORY_TIMEOUT_SEC,
                                                  pool=_HISTORY_POOL) for t in targets))

    per_year: list[dict[str, Any]] = []
    errors: list[str] = []
    for t, r in zip(targets, resps):
        v = r.get("values") or {}
        if v.get("ndvi_mean") is None:
            errors.append(f"{t.year}: " + ((r.get("errors") or ["brak czystego zdjęcia"])[0]))
            continue
        per_year.append({"year": t.year, "scene_date": v.get("scene_date"),
                         "ndvi_mean": v.get("ndvi_mean"), "ndmi_mean": v.get("ndmi_mean"),
                         "bare_soil_pct": v.get("bare_soil_pct")})

    def med(key: str) -> float | None:
        vals = [y[key] for y in per_year if y.get(key) is not None]
        return round(float(np.median(vals)), 3) if vals else None

    values: dict[str, Any] = {}
    if per_year:
        values = {"years": per_year, "n_years": len(per_year), "years_requested": years,
                  "ndvi_median": med("ndvi_mean"), "ndmi_median": med("ndmi_mean"),
                  "window_days": WINDOW_DAYS}
    if not values:
        errors = errors or ["Brak zdjęć z poprzednich lat."]
    srcs = [s for r in resps for s in (r.get("sources") or [])][:1]
    from_cache = bool(resps) and all(r.get("fromCache") for r in resps)
    coverage = "none" if not values else ("partial" if errors else "full")
    return {"values": values, "sources": srcs, "fetchedAt": max((r.get("fetchedAt") or "" for r in resps), default=""),
            "coverage": coverage, "errors": errors, "fromCache": from_cache}


# --------------------------------------------------------------------------- live test

if __name__ == "__main__":
    import time

    async def _main() -> None:
        bbox = [18.245, 53.045, 18.255, 53.055]
        for day in ("2023-07-15", "2026-07-15", "2019-07-15", "2026-11-21"):
            for attempt in (1, 2):
                t0 = time.perf_counter()
                r = await fetch_sentinel(bbox, day)
                v = r["values"]
                print(f"{day} call {attempt}: {time.perf_counter() - t0:5.2f}s fromCache={r['fromCache']} "
                      f"coverage={r['coverage']}"
                      + (f"  NDVI={v['ndvi_mean']} (sd {v['ndvi_std']}) NDMI={v['ndmi_mean']} "
                         f"scene={v['scene_date']} (-{v['days_before_analysis']}d) cloud={v['plot_cloud_pct']}% "
                         f"px={v['valid_pixels']}/{v['plot_pixels']} rejected={len(v['scenes_rejected'])}" if v else "")
                      + (f"\n    errors={r['errors']}" if r["errors"] else ""))

    asyncio.run(_main())
