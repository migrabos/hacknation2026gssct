"""Expected NDVI bands by SMSR crop × calendar month (orientation, not variety-level).

Used so satellite interpretation respects the crop and season (contest §3.2.1a).
Bands are rough canopy density for Polish field conditions; missing month = off-season /
not interpretable for that crop.
"""

from __future__ import annotations

# (low, high) NDVI for a typical healthy stand in that month. Below low → weak canopy
# for this crop/month; above high → dense (OK for moisture reading).
NDVI_EXPECT: dict[str, dict[int, tuple[float, float]]] = {
    "zboza_ozime": {
        3: (0.25, 0.55), 4: (0.40, 0.70), 5: (0.55, 0.85), 6: (0.50, 0.80), 7: (0.25, 0.55),
    },
    "zboza_jare": {
        4: (0.20, 0.45), 5: (0.40, 0.70), 6: (0.55, 0.85), 7: (0.35, 0.70),
    },
    "kukurydza_ziarno": {
        5: (0.15, 0.40), 6: (0.35, 0.65), 7: (0.55, 0.85), 8: (0.50, 0.80), 9: (0.30, 0.60),
    },
    "kukurydza_kiszonka": {
        5: (0.15, 0.40), 6: (0.35, 0.65), 7: (0.55, 0.85), 8: (0.50, 0.80), 9: (0.30, 0.60),
    },
    "rzepak": {
        3: (0.35, 0.65), 4: (0.45, 0.75), 5: (0.40, 0.70), 6: (0.25, 0.50),
        9: (0.20, 0.45), 10: (0.25, 0.50),
    },
    "ziemniak": {
        5: (0.20, 0.45), 6: (0.45, 0.75), 7: (0.55, 0.85), 8: (0.40, 0.70), 9: (0.20, 0.45),
    },
    "burak": {
        5: (0.20, 0.45), 6: (0.40, 0.70), 7: (0.55, 0.85), 8: (0.55, 0.85), 9: (0.40, 0.70),
    },
    "chmiel": {
        5: (0.25, 0.50), 6: (0.45, 0.75), 7: (0.55, 0.85), 8: (0.50, 0.80), 9: (0.30, 0.60),
    },
    "tyton": {
        5: (0.20, 0.45), 6: (0.40, 0.70), 7: (0.50, 0.80), 8: (0.45, 0.75),
    },
    "warzywa": {
        4: (0.20, 0.50), 5: (0.35, 0.70), 6: (0.45, 0.80), 7: (0.45, 0.80),
        8: (0.40, 0.75), 9: (0.25, 0.55),
    },
    "krzewy": {
        4: (0.30, 0.60), 5: (0.45, 0.75), 6: (0.50, 0.80), 7: (0.50, 0.80), 8: (0.40, 0.70),
    },
    "drzewa": {
        4: (0.35, 0.65), 5: (0.50, 0.80), 6: (0.55, 0.85), 7: (0.55, 0.85),
        8: (0.50, 0.80), 9: (0.40, 0.70),
    },
    "truskawki": {
        4: (0.25, 0.55), 5: (0.40, 0.70), 6: (0.45, 0.75), 7: (0.35, 0.65), 8: (0.25, 0.55),
    },
    "straczkowe": {
        5: (0.25, 0.50), 6: (0.45, 0.75), 7: (0.50, 0.80), 8: (0.30, 0.60),
    },
}


def expected_ndvi(crop_id: str | None, month: int | None) -> tuple[float, float] | None:
    """Return (low, high) NDVI for crop×month, or None when not interpretable."""
    if not crop_id or month is None:
        return None
    band = NDVI_EXPECT.get(crop_id)
    if not band:
        return None
    return band.get(month)
