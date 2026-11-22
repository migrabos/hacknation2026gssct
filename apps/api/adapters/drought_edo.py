"""Drought background: EDO Combined Drought Indicator (CDI) class at the plot.

Source: European Drought Observatory (Copernicus Emergency Management Service),
WMS layer `cdiad` – "Combined Drought Indicator (CDI) v4.1", dekadal (10-day) maps.

Why GetMap and not GetFeatureInfo: the EDO WMS advertises `cdiad` as
queryable="0" and answers GetFeatureInfo with "Invalid request type". We therefore
request a tiny PNG around the point and read the class from the pixel colour, using
the exact colours of the official layer legend (GetLegendGraphic):
    (240,228, 66) Watch · (230,159,0) Warning · (220,5,12) Alert · transparent = no class.

Context layer only (short timeout, fail-soft). It describes the *region*, not the
plot, and the latest dekad is published with a ~2–3 week delay.
"""

from __future__ import annotations

import io
from datetime import date, datetime, timedelta
from typing import Any

import httpx
from PIL import Image

from .base import PartialResult, run_adapter
from .dates import today_pl

EDO_WMS = "https://drought.emergency.copernicus.eu/api/wms"
LAYER = "cdiad"
HALF_DEG = 0.05          # bbox ±0.05° around the point
SIZE = 101               # 101×101 px -> centre pixel (50, 50)
NEIGHBOURHOOD_PX = 10    # ±10 px ≈ ±0.01° … context "around the plot"
MAX_DEKADS_BACK = 4      # publication lag: step back up to ~40 days
COLOR_TOLERANCE = 40

CDI_COLORS = {  # from the official cdiad legend (Watch / Warning / Alert)
    1: (240, 228, 66),   # Watch
    2: (230, 159, 0),    # Warning
    3: (220, 5, 12),     # Alert
}
# Recovery classes from CDI v4 are not scored; unknown colours → missing, not "no drought".
CDI_LABELS = {
    1: "Obserwacja (Watch) – niedobór opadów",
    2: "Ostrzeżenie (Warning) – niedobór wilgoci w glebie",
    3: "Alarm (Alert) – susza widoczna w kondycji roślin",
}
CDI_NODATA = -1  # transparent pixel / no published drought class at the point


# --------------------------------------------------------------------------- dekads


def dekad_start(d: date) -> date:
    return d.replace(day=21 if d.day >= 21 else 11 if d.day >= 11 else 1)


def previous_dekad(ds: date) -> date:
    if ds.day == 21:
        return ds.replace(day=11)
    if ds.day == 11:
        return ds.replace(day=1)
    return (ds - timedelta(days=1)).replace(day=21)


def _parse_date(value: date | str) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value).strip()[:10])


# --------------------------------------------------------------------------- pixels


def _classify(px: tuple[int, int, int, int]) -> int | None:
    """Return CDI class 1–3, CDI_NODATA for transparent, or None for unknown colour."""
    r, g, b, a = px
    if a < 128:
        return CDI_NODATA
    best, best_d = None, float("inf")
    for cls, (cr, cg, cb) in CDI_COLORS.items():
        dist = ((r - cr) ** 2 + (g - cg) ** 2 + (b - cb) ** 2) ** 0.5
        if dist < best_d:
            best, best_d = cls, dist
    return best if best_d <= COLOR_TOLERANCE else None


def read_cdi_png(png: bytes) -> dict[str, Any]:
    im = Image.open(io.BytesIO(png)).convert("RGBA")
    w, h = im.size
    cx, cy = w // 2, h // 2
    centre = _classify(im.getpixel((cx, cy)))
    if centre is None:
        raise ValueError(f"Nieznany kolor piksela EDO: {im.getpixel((cx, cy))}")
    if centre == CDI_NODATA:
        # Transparent ≠ „brak suszy”: EDO simply has no drought class published here.
        raise ValueError("EDO: przezroczysty piksel w punkcie działki (brak klasy CDI)")
    around = [
        _classify(im.getpixel((x, y)))
        for x in range(max(0, cx - NEIGHBOURHOOD_PX), min(w, cx + NEIGHBOURHOOD_PX + 1))
        for y in range(max(0, cy - NEIGHBOURHOOD_PX), min(h, cy + NEIGHBOURHOOD_PX + 1))
    ]
    known = [c for c in around if c is not None and c != CDI_NODATA]
    return {
        "cdi_class": centre,
        "cdi_area_max_class": max(known) if known else centre,
        "cdi_area_share_pct": {  # share of the surrounding window in each class
            str(c): round(100.0 * known.count(c) / len(known), 1) for c in sorted(set(known))
        } if known else {},
    }


# --------------------------------------------------------------------------- adapter


async def fetch_drought_context(centroid: list[float], analysis_date: date | str) -> dict[str, Any]:
    """EDO CDI class for the dekad of `analysis_date` (or the latest published before it)."""
    try:
        lat, lng = round(float(centroid[0]), 3), round(float(centroid[1]), 3)
        d = _parse_date(analysis_date)
        bad = None
    except Exception as exc:
        lat = lng = 0.0
        d = today_pl()
        bad = f"Niepoprawne dane wejściowe dla EDO: {exc}"

    today = today_pl()
    base = {
        "SERVICE": "WMS", "VERSION": "1.1.1", "REQUEST": "GetMap", "LAYERS": LAYER, "STYLES": "",
        "SRS": "EPSG:4326", "FORMAT": "image/png", "TRANSPARENT": "true",
        "WIDTH": SIZE, "HEIGHT": SIZE,
        "BBOX": f"{lng - HALF_DEG:.4f},{lat - HALF_DEG:.4f},{lng + HALF_DEG:.4f},{lat + HALF_DEG:.4f}",
    }

    async def fetch() -> dict[str, Any] | PartialResult:
        if bad:
            return PartialResult({}, [bad])
        if d > today:
            return PartialResult({}, [f"Data analizy {d} jest z przyszłości."])

        tried: list[str] = []
        ds = dekad_start(d)
        async with httpx.AsyncClient(timeout=httpx.Timeout(4.0, connect=3.0)) as client:
            for _ in range(MAX_DEKADS_BACK):
                r = await client.get(EDO_WMS, params={**base, "TIME": ds.isoformat()})
                ctype = r.headers.get("content-type", "")
                if r.status_code == 200 and ctype.startswith("image/"):
                    try:
                        values = read_cdi_png(r.content)
                    except ValueError as exc:
                        # Transparent / unknown colour = missing data, not "no drought".
                        tried.append(f"{ds} ({exc})")
                        ds = previous_dekad(ds)
                        continue
                    values.update({
                        "cdi_label": CDI_LABELS[values["cdi_class"]],
                        "dekad_start": ds.isoformat(),
                        "dekad_lag_days": (d - ds).days,
                        "layer": "EDO CDI v4.1 (cdiad)",
                        "notes": [
                            "Wskaźnik regionalny (siatka EDO), nie pomiar na działce.",
                            "EDO publikuje tylko klasy suszy (1–3); brak koloru = brak danych, nie „brak suszy”.",
                        ],
                    })
                    if ds != dekad_start(d):
                        values["notes"].append(
                            f"Mapa dla dekady {dekad_start(d)} nie jest jeszcze opublikowana – użyto {ds}."
                        )
                    return values
                tried.append(f"{ds} (HTTP {r.status_code})")
                ds = previous_dekad(ds)

        return PartialResult({}, ["Brak opublikowanej mapy CDI EDO dla dat: " + ", ".join(tried)])

    recent = (today - d).days <= 45  # newer dekads may still get published
    return await run_adapter(
        "EDO Combined Drought Indicator (Copernicus EMS)",
        EDO_WMS,
        {"lat": lat, "lng": lng, "dekad": dekad_start(d).isoformat(), "v": 2},
        fetch,
        timeout_sec=10.0,
        cache_ttl_sec=86_400 if recent else None,
    )


# --------------------------------------------------------------------------- live test

if __name__ == "__main__":
    import asyncio
    import time

    async def _main() -> None:
        for day in ("2019-07-15", "2026-07-15", "2026-11-21"):
            for attempt in (1, 2):
                t0 = time.perf_counter()
                r = await fetch_drought_context([53.05, 18.25], day)
                v = r["values"]
                print(f"{day} call {attempt}: {time.perf_counter() - t0:5.2f}s fromCache={r['fromCache']} "
                      f"coverage={r['coverage']} "
                      + (f"CDI={v['cdi_class']} ({v['cdi_label']}) dekad={v['dekad_start']} "
                         f"area_max={v['cdi_area_max_class']} share={v['cdi_area_share_pct']}" if v else str(r["errors"])))

    asyncio.run(_main())
