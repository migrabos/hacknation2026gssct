"""Soil adapter: ISRIC SoilGrids 2.0 texture + organic carbon -> available water capacity.

Fetches sand / clay / silt / SOC for the 5 standard SoilGrids layers down to 1 m
(SoilGrids has no "0-30cm" layer – querying it returns an empty result), then:

* topsoil 0–30 cm texture/SOC = thickness-weighted mean of 0-5, 5-15, 15-30 cm,
* AWC 0–100 cm = Σ (field capacity − wilting point) × layer thickness, with field
  capacity (θ33 kPa) and wilting point (θ1500 kPa) from the published pedotransfer
  functions of Saxton & Rawls (2006), Soil Sci. Soc. Am. J. 70:1569–1578.

Why not SoilGrids' own wv0033/wv1500 layers: on test plots they gave 180–210 mm/m
even for ~72% sand soils, which is implausible (sandy soils hold ~60–110 mm/m).

SoilGrids resolution is 250 m and it is a modelled (ML) product, not a field survey.
Data come from the WCS service (fast); the REST API (slow, fair-use ~5 req/min) is
only a fallback. Results are cached forever (soil doesn't change).
"""

from __future__ import annotations

import asyncio
from typing import Any

import httpx
from pyproj import Transformer
from rasterio.io import MemoryFile

from .base import PartialResult, run_adapter

# Primary: SoilGrids WCS (MapServer) – 20 tiny GetCoverage calls in parallel, ~2–4 s.
# Fallback: REST point API – same data, but measured 9–33 s per call (ISRIC "beta").
WCS_URL = "https://maps.isric.org/mapserv"
WCS_HALF_M = 375.0  # 750 m window = 3×3 pixels of 250 m around the point
_TO_IGH = Transformer.from_crs(  # SoilGrids native CRS: Interrupted Goode Homolosine
    "EPSG:4326", "+proj=igh +lat_0=0 +lon_0=0 +datum=WGS84 +units=m +no_defs", always_xy=True
)
WCS_CONCURRENCY = 10  # be polite to ISRIC
SOILGRIDS_URL = "https://rest.isric.org/soilgrids/v2.0/properties/query"
PROPERTIES = ("sand", "clay", "silt", "soc")
# (label, thickness in cm) – SoilGrids standard depth intervals
LAYERS = (("0-5cm", 5), ("5-15cm", 10), ("15-30cm", 15), ("30-60cm", 30), ("60-100cm", 40))
TOPSOIL = ("0-5cm", "5-15cm", "15-30cm")

# SoilGrids "mapped units" -> percent
TO_PCT = {"sand": 10.0, "clay": 10.0, "silt": 10.0, "soc": 100.0}  # g/kg, g/kg, g/kg, dg/kg

OM_PER_SOC = 1.724  # van Bemmelen factor: organic matter ≈ 1.724 × organic carbon
SR_MAX_OM = 8.0     # Saxton & Rawls equations are calibrated for OM ≤ 8 %

HTTP_TIMEOUT = httpx.Timeout(20.0, connect=5.0)


# --------------------------------------------------------------------------- science


def saxton_rawls(sand_pct: float, clay_pct: float, om_pct: float) -> tuple[float, float]:
    """Return (θ33 field capacity, θ1500 wilting point) in m³/m³ – Saxton & Rawls 2006, eq. 1–2."""
    s, c, om = sand_pct / 100.0, clay_pct / 100.0, min(om_pct, SR_MAX_OM)

    t1500 = -0.024 * s + 0.487 * c + 0.006 * om + 0.005 * s * om - 0.013 * c * om + 0.068 * s * c + 0.031
    wp = t1500 + (0.14 * t1500 - 0.02)

    t33 = -0.251 * s + 0.195 * c + 0.011 * om + 0.006 * s * om - 0.027 * c * om + 0.452 * s * c + 0.299
    fc = t33 + (1.283 * t33**2 - 0.374 * t33 - 0.015)
    return fc, wp


def retention_class(awc_mm: float | None) -> str | None:
    if awc_mm is None:
        return None
    if awc_mm < 110.0:
        return "low"     # gleba lekka / piaszczysta – szybko wysycha
    if awc_mm <= 155.0:
        return "medium"  # gleba średnia
    return "high"        # gleba ciężka / pylasta – dobrze magazynuje wodę


def compute_soil(raw: dict[str, dict[str, float | None]]) -> tuple[dict[str, Any], list[str]]:
    """raw[property][depth_label] = value in percent (None = no pixel). Pure function."""
    errors: list[str] = []

    if any(raw.get(p, {}).get(d) is None for p in PROPERTIES for d in TOPSOIL):
        return {}, ["Brak danych glebowych SoilGrids dla tego miejsca "
                    "(np. teren zabudowany, woda lub las poza maską gleb)."]

    thick = dict(LAYERS)
    tw = sum(thick[d] for d in TOPSOIL)

    def top(p: str) -> float:
        return sum(raw[p][d] * thick[d] for d in TOPSOIL) / tw

    sand, clay, silt, soc = (top(p) for p in PROPERTIES)

    layers: list[dict[str, Any]] = []
    awc, depth_cm, om_capped = 0.0, 0, False
    for label, cm in LAYERS:
        s, c, oc = raw["sand"].get(label), raw["clay"].get(label), raw["soc"].get(label)
        if None in (s, c, oc):
            break  # no extrapolation below the last layer with data
        om = oc * OM_PER_SOC
        om_capped |= om > SR_MAX_OM
        fc, wp = saxton_rawls(s, c, om)
        layer_awc = max(0.0, fc - wp) * cm * 10  # m³/m³ × cm × 10 = mm
        awc += layer_awc
        depth_cm += cm
        layers.append({
            "depth": label, "sand_pct": round(s, 1), "clay_pct": round(c, 1), "soc_pct": round(oc, 2),
            "field_capacity": round(fc, 3), "wilting_point": round(wp, 3), "awc_mm": round(layer_awc, 1),
        })

    if depth_cm < 100:
        errors.append(f"Dane glebowe tylko do głębokości {depth_cm} cm – pojemność wodna "
                      "policzona dla płytszego profilu (zaniżona).")
    capped = [l["depth"] for l in layers if l["soc_pct"] * OM_PER_SOC > SR_MAX_OM]
    errors_note = (
        f"Materia organiczna w warstwie {', '.join(capped)} powyżej 8 % (SoilGrids często ją zawyża "
        "w cienkiej warstwie powierzchniowej) – do wzoru przyjęto 8 %." if om_capped else None
    )

    awc_mm = round(awc, 1)
    values = {
        "sand_pct": round(sand, 1),
        "clay_pct": round(clay, 1),
        "silt_pct": round(silt, 1),
        "soc_pct": round(soc, 2),
        "awc_mm": awc_mm,
        "awc_depth_cm": depth_cm,
        "retention_class": retention_class(awc_mm),
        "method": "Saxton & Rawls (2006) PTF na danych SoilGrids 2.0, profil 0–100 cm",
        "resolution_m": 250,
        "layers": layers,  # transparency: lets anyone recompute AWC by hand
        "notes": [errors_note] if errors_note else [],
    }
    return values, errors


# --------------------------------------------------------------------------- fetchers


async def _wcs_value(client: httpx.AsyncClient, sem: asyncio.Semaphore, prop: str, depth: str, x: float, y: float) -> tuple[float | None, bool]:
    """One property/depth from the SoilGrids WCS: (value in mapped units, neighbour_used)."""
    params = [
        ("map", f"/map/{prop}.map"), ("SERVICE", "WCS"), ("VERSION", "2.0.1"), ("REQUEST", "GetCoverage"),
        ("COVERAGEID", f"{prop}_{depth}_mean"), ("FORMAT", "image/tiff"),
        ("SUBSET", f"X({x - WCS_HALF_M:.1f},{x + WCS_HALF_M:.1f})"),
        ("SUBSET", f"Y({y - WCS_HALF_M:.1f},{y + WCS_HALF_M:.1f})"),
    ]
    async with sem:
        r = await client.get(WCS_URL, params=params)
    r.raise_for_status()
    if not r.headers.get("content-type", "").startswith("image/"):
        raise ValueError(f"WCS: {r.text[:120]}")
    with MemoryFile(r.content) as mem, mem.open() as ds:
        a = ds.read(1).astype("float64")
        row, col = ds.index(x, y)
    row, col = min(max(row, 0), a.shape[0] - 1), min(max(col, 0), a.shape[1] - 1)
    v = a[row, col]
    if v > 0:  # SoilGrids WCS encodes "no data" (built-up, water) as 0
        return float(v), False
    valid = a[a > 0]
    return (float(valid.mean()), True) if valid.size else (None, False)


async def _fetch_wcs(client: httpx.AsyncClient, lat: float, lng: float) -> tuple[dict[str, dict[str, float | None]], bool]:
    x, y = _TO_IGH.transform(lng, lat)
    keys = [(p, d) for p in PROPERTIES for d, _ in LAYERS]
    sem = asyncio.Semaphore(WCS_CONCURRENCY)  # per call: no cross-event-loop binding
    res = await asyncio.gather(*(_wcs_value(client, sem, p, d, x, y) for p, d in keys))
    raw: dict[str, dict[str, float | None]] = {p: {} for p in PROPERTIES}
    for (p, d), (v, _) in zip(keys, res):
        raw[p][d] = None if v is None else v / TO_PCT[p]
    return raw, any(n for _, n in res)


async def _fetch_rest(client: httpx.AsyncClient, url: str) -> dict[str, dict[str, float | None]]:
    r = await client.get(url)
    r.raise_for_status()
    raw: dict[str, dict[str, float | None]] = {p: {} for p in PROPERTIES}
    for layer in r.json().get("properties", {}).get("layers", []):
        name = layer.get("name")
        if name not in raw:
            continue
        for dep in layer.get("depths", []):
            v = dep.get("values", {}).get("mean")
            raw[name][dep.get("label")] = None if v is None else v / TO_PCT[name]
    return raw


# --------------------------------------------------------------------------- adapter


async def fetch_soil(centroid: list[float]) -> dict[str, Any]:
    """Soil texture + AWC at plot centroid [lat, lng]. Never raises."""
    try:
        lat, lng = round(float(centroid[0]), 4), round(float(centroid[1]), 4)
        bad = None
    except Exception as exc:
        lat = lng = 0.0
        bad = f"Niepoprawne współrzędne dla danych glebowych: {exc}"

    params = [("lon", lng), ("lat", lat)]
    params += [("property", p) for p in PROPERTIES]
    params += [("depth", d) for d, _ in LAYERS]
    params += [("value", "mean")]
    rest_url = str(httpx.URL(SOILGRIDS_URL, params=params))

    async def fetch() -> dict[str, Any] | PartialResult:
        if bad:
            return PartialResult({}, [bad])
        notes: list[str] = []
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
            try:
                raw, neighbour_used = await _fetch_wcs(client, lat, lng)
                service = "WCS (maps.isric.org)"
                if neighbour_used:
                    notes.append("Dla części warstw brak piksela SoilGrids dokładnie w punkcie (np. zabudowa, "
                                 "droga) – przyjęto średnią z sąsiednich pikseli 250 m (do ~375 m).")
            except Exception as exc:  # WCS down -> slower REST API
                raw = await _fetch_rest(client, rest_url)
                service = "REST API (rest.isric.org)"
                notes.append(f"Usługa WCS niedostępna ({type(exc).__name__}) – użyto REST API SoilGrids.")

        values, errors = compute_soil(raw)
        if values:
            values["service"] = service
            values["notes"] = notes + values.get("notes", [])
        return PartialResult(values, errors) if errors else values

    return await run_adapter(
        "ISRIC SoilGrids 2.0",
        WCS_URL,
        {"lat": lat, "lng": lng, "v": 3},
        fetch,
        cache_ttl_sec=None,  # soil doesn't change – cache forever
    )


# --------------------------------------------------------------------------- live test

if __name__ == "__main__":
    import asyncio
    import time

    async def _main() -> None:
        for point in ([53.05, 18.25], [52.35, 17.15], [51.15, 22.85]):
            for attempt in (1, 2):
                t0 = time.perf_counter()
                r = await fetch_soil(point)
                dt = time.perf_counter() - t0
                v = r["values"]
                print(f"{point} call {attempt}: {dt:5.2f}s fromCache={r['fromCache']} coverage={r['coverage']}"
                      + (f"  sand={v['sand_pct']}% clay={v['clay_pct']}% silt={v['silt_pct']}% soc={v['soc_pct']}%"
                         f"  AWC={v['awc_mm']} mm/{v['awc_depth_cm']} cm  -> {v['retention_class']}" if v else "")
                      + (f"  errors={r['errors']}" if r["errors"] else "")
                      + (f"  notes={v.get('notes')}" if v and v.get("notes") else ""))

    asyncio.run(_main())
