"""FAO Irrigation & Drainage Paper 33 — seasonal yield response factors (Ky).

Ky > 1 → yield drops more than proportionally with ET deficit (more drought-sensitive).
Ky < 1 → more tolerant. Values from Doorenbos & Kassam (1979), as summarized in
FAO-56 Table 24 / FAO Paper 66 recapitulation.

Source: https://www.fao.org/4/x0490e/x0490e0e.htm

Keys match exact SMSR crop category ids in `catalog.py`.
Crops without a FAO-33 row stay as None in FAO_KY; ASSUMED_KY holds team orientation
values used only for sensitivity weights — never labelled as FAO in the report.
"""

from __future__ import annotations

# Seasonal Ky by SMSR crop id. None = no FAO-33 row → see ASSUMED_KY / SMSR.
FAO_KY: dict[str, float | None] = {
    "zboza_ozime": 1.05,            # winter wheat
    "zboza_jare": 1.15,             # spring wheat
    "kukurydza_ziarno": 1.25,      # maize
    "kukurydza_kiszonka": 1.25,    # maize (same Ky)
    "rzepak": None,                 # oilseed rape not in FAO-33
    "ziemniak": 1.1,                # potato
    "burak": 1.0,                   # sugar beet
    "chmiel": None,                 # hop not in FAO-33
    "tyton": None,                  # tobacco not in FAO-33
    "warzywa": 1.1,                 # onion / pepper band
    "krzewy": None,                 # no bush-fruit Ky in FAO-33
    "drzewa": None,                 # no apple Ky in FAO-33
    "truskawki": None,              # no strawberry Ky in FAO-33
    "straczkowe": 1.15,             # peas / beans
    "brak": None,                   # no crop — not an FAO-33 row
}

# Orientation Ky when FAO-33 has no row (sensitivity weight only; labelled „przyjęte”).
ASSUMED_KY: dict[str, float] = {
    "krzewy": 1.15,       # shallow roots → drought-sensitive
    "drzewa": 1.1,        # analog to pepper/onion band
    "truskawki": 1.15,    # shallow roots
    "rzepak": 1.1,        # flowering / autumn emergence sensitive (SMSR still primary)
    "chmiel": 1.05,
    "tyton": 1.1,
}

FAO_KY_NOTE: dict[str, str] = {
    "zboza_ozime": "FAO-33 Ky = 1,05 (pszenica ozima)",
    "zboza_jare": "FAO-33 Ky = 1,15 (pszenica jara)",
    "kukurydza_ziarno": "FAO-33 Ky = 1,25 (kukurydza)",
    "kukurydza_kiszonka": "FAO-33 Ky = 1,25 (kukurydza)",
    "rzepak": "brak Ky dla rzepaku w FAO-33 – przyjęto 1,1 (wrażliwość też z progu SMSR / IUNG)",
    "ziemniak": "FAO-33 Ky = 1,1 (ziemniak)",
    "burak": "FAO-33 Ky = 1,0 (burak cukrowy)",
    "chmiel": "brak Ky dla chmielu w FAO-33 – przyjęto 1,05 (wrażliwość też z progu SMSR / IUNG)",
    "tyton": "brak Ky dla tytoniu w FAO-33 – przyjęto 1,1 (wrażliwość też z progu SMSR / IUNG)",
    "warzywa": "FAO-33 Ky ≈ 1,1 (cebula / papryka; typowe warzywa gruntowe)",
    "krzewy": "brak Ky dla krzewów owocowych w FAO-33 – przyjęto 1,15",
    "drzewa": "brak Ky dla jabłoni w FAO-33 – przyjęto 1,1 (analog)",
    "truskawki": "brak Ky dla truskawki w FAO-33 – przyjęto 1,15 (płytki system korzeniowy)",
    "straczkowe": "FAO-33 Ky = 1,15 (groch / fasola)",
    "brak": "brak uprawy – nie stosuje się FAO Ky",
}

FAO_SOURCE_URL = "https://www.fao.org/4/x0490e/x0490e0e.htm"
FAO_SOURCE_NAME = "FAO Irrigation & Drainage Paper 33 (Ky)"

# Map Ky → engine weight 0–1. Linear stretch of the FAO-33 span used by our crops
# [0.85, 1.25] → [0.25, 1.00]. Winter wheat (1.05) → medium; ≥1.10 → high (≥0.65).
_KY_LO, _KY_HI = 0.85, 1.25
_SENS_LO, _SENS_HI = 0.25, 1.00
_DEFAULT_SENS = 0.55  # when neither FAO nor assumed Ky — SMSR comparison still applies


def ky_to_sensitivity(ky: float | None) -> float:
    if ky is None:
        return _DEFAULT_SENS
    t = (ky - _KY_LO) / (_KY_HI - _KY_LO)
    return round(max(_SENS_LO, min(_SENS_HI, _SENS_LO + t * (_SENS_HI - _SENS_LO))), 2)


def fao_ky(crop_id: str) -> float | None:
    """Ky strictly from FAO-33, or None."""
    return FAO_KY.get(crop_id)


def effective_ky(crop_id: str) -> float | None:
    """Ky used for sensitivity: FAO-33 if present, else assumed orientation value."""
    ky = FAO_KY.get(crop_id)
    if ky is not None:
        return ky
    return ASSUMED_KY.get(crop_id)


def ky_is_from_fao(crop_id: str) -> bool:
    return FAO_KY.get(crop_id) is not None


def fao_note(crop_id: str) -> str:
    return FAO_KY_NOTE.get(crop_id, "brak wpisu FAO-33")
