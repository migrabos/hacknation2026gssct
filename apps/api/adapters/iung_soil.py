"""IUNG-PIB soil drought-susceptibility category (kategoria podatności gleb na suszę, I–IV).

Source: IUNG-PIB System Monitoringu Suszy Rolniczej (SMSR), WMS layer
`Susza:katgl_landuse2024` – the map the official SMSR uses to pick the KBW threshold
for each crop (https://susza.iung.pulawy.pl/mapa-kategorii/). Categories come from the
soil-agricultural map (mapa glebowo-rolnicza) and usable water (WOD) to 1.5 m:
    I  < 127.5 mm  bardzo podatna   (piaski luźne, słabo gliniaste)
    II 127.5–169.9 podatna           (piaski gliniaste)
    III 170–202.5  średnio podatna   (gliny lekkie, pyły)
    IV > 202.5 mm  mało podatna      (gliny średnie i ciężkie, iły)
Non-agricultural / organic soils have separate codes (no SMSR threshold).

The layer is a raster without WCS, so – like the EDO adapter – we request one small
PNG over the plot bbox (EPSG:2180, ~10 m pixels) and read each pixel's class from the
exact colours of the layer's own legend (GetLegendGraphic). Only pixels whose centre
lies inside the parcel count. Nothing is guessed: unknown colours are skipped.
"""

from __future__ import annotations

import io
from collections import Counter
from typing import Any

import httpx
import numpy as np
import shapely
from PIL import Image
from shapely.geometry.base import BaseGeometry

from .base import PartialResult, run_adapter

IUNG_WMS = "https://sgeo.iung.pl/geoserver/Susza/wms"
LAYER = "Susza:katgl_landuse2024"
SOURCE_NAME = "IUNG-PIB SMSR – mapa kategorii podatności gleb na suszę"
PIXEL_M = 10.0
MAX_PX = 256
COLOR_TOLERANCE = 6  # the PNG carries the legend colours exactly; small slack only
HTTP_TIMEOUT = httpx.Timeout(12.0, connect=5.0)

# Legend of Susza:katgl_landuse2024 (GetLegendGraphic, checked 2026-11-22): code → RGB.
LEGEND: dict[int, tuple[int, int, int]] = {
    1: (255, 255, 84),
    2: (255, 157, 0),
    3: (253, 66, 0),
    4: (128, 64, 0),
    5: (100, 205, 110),   # gleby organiczne i pochodzenia organicznego
    11: (38, 115, 0),     # lasy, zadrzewienia
    12: (115, 178, 255),  # wody
    13: (130, 130, 130),  # tereny zabudowane
    14: (204, 204, 204),  # tereny komunikacyjne, nieużytki
    19: (17, 17, 17),     # tereny niesklasyfikowane
}
CODE_LABEL_PL = {
    1: "kategoria I – gleba bardzo podatna na suszę",
    2: "kategoria II – gleba podatna na suszę",
    3: "kategoria III – gleba średnio podatna na suszę",
    4: "kategoria IV – gleba mało podatna na suszę",
    5: "gleba organiczna (torf, mursz)",
    11: "las lub zadrzewienie",
    12: "woda",
    13: "teren zabudowany",
    14: "teren komunikacyjny lub nieużytek",
    19: "teren niesklasyfikowany",
}


def classify_pixels(rgba: np.ndarray, inside: np.ndarray) -> Counter:
    """Count legend codes among pixels inside the plot (transparent/unknown colours skipped)."""
    out: Counter = Counter()
    px = rgba[inside]
    for r, g, b, a in px:
        if a < 128:
            continue
        for code, (cr, cg, cb) in LEGEND.items():
            if abs(int(r) - cr) <= COLOR_TOLERANCE and abs(int(g) - cg) <= COLOR_TOLERANCE \
                    and abs(int(b) - cb) <= COLOR_TOLERANCE:
                out[code] += 1
                break
    return out


def summarize(counts: Counter) -> dict[str, Any]:
    """Dominant SMSR soil category (1–4) on the agricultural part of the plot + shares of all codes."""
    total = sum(counts.values())
    shares = {str(k): round(100.0 * v / total, 1) for k, v in sorted(counts.items())} if total else {}
    agri = {k: v for k, v in counts.items() if 1 <= k <= 4}
    n_agri = sum(agri.values())
    category = max(agri, key=lambda k: (agri[k], -k)) if agri else None  # tie → lighter (more cautious)
    dominant = max(counts, key=lambda k: counts[k]) if counts else None
    return {
        "category": category,
        "category_share_pct": round(100.0 * agri[category] / n_agri, 1) if category else None,
        "agri_share_pct": round(100.0 * n_agri / total, 1) if total else None,
        "dominant_code": dominant,
        "dominant_label": CODE_LABEL_PL.get(dominant) if dominant is not None else None,
        "shares_pct": shares,
        "pixels": total,
        "pixel_m": PIXEL_M,
    }


async def fetch_iung_soil_category(plot_id: str, poly_2180: BaseGeometry) -> dict[str, Any]:
    minx, miny, maxx, maxy = poly_2180.bounds
    w = max(1, min(MAX_PX, int(round((maxx - minx) / PIXEL_M))))
    h = max(1, min(MAX_PX, int(round((maxy - miny) / PIXEL_M))))

    async def fetch() -> dict[str, Any] | PartialResult:
        params = {
            "SERVICE": "WMS", "VERSION": "1.1.1", "REQUEST": "GetMap", "LAYERS": LAYER, "STYLES": "",
            "SRS": "EPSG:2180", "BBOX": f"{minx},{miny},{maxx},{maxy}", "WIDTH": w, "HEIGHT": h,
            "FORMAT": "image/png", "TRANSPARENT": "TRUE",
        }
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT, follow_redirects=True) as c:
            r = await c.get(IUNG_WMS, params=params)
        if r.status_code != 200 or not r.headers.get("content-type", "").startswith("image/"):
            raise RuntimeError(f"IUNG WMS HTTP {r.status_code}: {r.text[:120]}")
        if len(r.content) > 2_000_000:
            raise RuntimeError("IUNG WMS: odpowiedź zbyt duża")
        rgba = np.asarray(Image.open(io.BytesIO(r.content)).convert("RGBA"))
        # Pixel centres (row 0 = north).
        xs = minx + (np.arange(w) + 0.5) * (maxx - minx) / w
        ys = maxy - (np.arange(h) + 0.5) * (maxy - miny) / h
        gx, gy = np.meshgrid(xs, ys)
        inside = shapely.contains_xy(poly_2180, gx, gy)
        if not inside.any():  # tiny parcel: use the pixel at its representative point
            p = poly_2180.representative_point()
            i = min(h - 1, max(0, int((maxy - p.y) / (maxy - miny or 1) * h)))
            j = min(w - 1, max(0, int((p.x - minx) / (maxx - minx or 1) * w)))
            inside = np.zeros((h, w), dtype=bool)
            inside[i, j] = True
        values = summarize(classify_pixels(rgba, inside))
        if values["pixels"] == 0:
            return PartialResult({}, ["Mapa kategorii gleb IUNG nie ma danych dla tej działki."], definitive=True)
        if values["category"] is None:
            return PartialResult(values, [
                f"Na mapie IUNG działka to {values['dominant_label']} – brak kategorii gleby rolniczej I–IV."
            ], definitive=True)
        return values

    return await run_adapter(
        SOURCE_NAME, f"{IUNG_WMS}?SERVICE=WMS&REQUEST=GetMap&LAYERS={LAYER}",
        {"plotId": plot_id, "bbox": [round(minx), round(miny), round(maxx), round(maxy)], "v": 1},
        fetch, timeout_sec=12.0, cache_ttl_sec=None,  # soil categories are static
    )


if __name__ == "__main__":
    import asyncio
    import json
    import sys

    from shapely.geometry import box

    async def _main() -> None:
        # Farmland near Inowrocław (EPSG:2180 box, ~600 × 600 m).
        poly = box(*(float(v) for v in sys.argv[1:5])) if len(sys.argv) == 5 else box(
            449000, 562000, 449600, 562600)
        r = await fetch_iung_soil_category("TEST", poly)
        print(json.dumps(r, ensure_ascii=False, indent=1))

    asyncio.run(_main())
