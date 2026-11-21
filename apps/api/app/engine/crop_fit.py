"""Which crops cope best with the water and soil of THIS plot — deterministic ranking.

Score = 100 minus explicit penalties (each with a farmer-language reason and Evidence refs):
  water  – drought sensitivity × (how dry the summers are here + how little water the soil
           holds within the crop's root zone); deep roots get a small bonus,
  soil   – crop's soil needs vs soil quality (EGiB soil class, else SoilGrids texture / AWC),
  slope  – row crops on a slope (runoff + erosion),
  wet    – waterlogging-intolerant crops on heavy soil next to water,
  land   – ploughing a registered permanent grassland (TUZ protection).
This is a fit to water conditions, not economic advice: prices, rotation, pH, machinery and
subsidies are explicitly out of scope (said in `notConsidered`).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.crops.fit_profiles import FIT_PROFILES, FitProfile, Level
from app.engine.facts import Facts, fmt
from app.schemas.evidence import Confidence, CropFit, CropFitItem

# --- thresholds (documented in docs/verify.md) ---
KBW_SUMMER_WET = -100.0     # summer water balance (VI–VIII mean) at or above → not dry at all
KBW_SUMMER_DRY = -250.0     # at or below → as dry as it gets in Poland
ROOT_WATER_OK_MM = 100.0    # water held within the root zone at or above → no storage penalty
ROOT_WATER_MIN_MM = 20.0    # at or below → full storage penalty
AWC_DEPTH_M = 1.0           # SoilGrids AWC is given per 1 m of soil — deeper roots get no more mm from it
WATER_PENALTY_MAX = 55      # × crop sensitivity × (0.6 dry summers + 0.4 little water in root zone)
DRY_WEIGHT = 0.6
DEEP_ROOT_M = 1.2
DEEP_ROOT_BONUS = 5
DEEP_ROOT_MAX_SENSITIVITY = 0.6  # water-hungry crops (oats, maize…) gain little from deep roots in a drought
GOOD_SOIL_UNDERUSE = 6      # undemanding crop on a very good soil: works, but wastes the soil
SAND_POOR = 65.0
AWC_POOR = 100.0
AWC_GOOD = 150.0
SAND_GOOD_MAX = 45.0
SLOPE_STEEP = 6.0
SLOPE_MODERATE = 3.0
CLAY_HEAVY = 35.0
CLAY_VERY_HEAVY = 45.0
WATER_NEAR_M = 100.0
TUZ_PENALTY = 30
FIT_GOOD = 75
FIT_MEDIUM = 55

SOIL_PENALTY: dict[tuple[Level, str], int] = {
    ("high", "poor"): 30, ("high", "medium"): 12, ("medium", "poor"): 15,
}
SLOPE_PENALTY: dict[Level, tuple[int, int]] = {  # (steep, moderate)
    "high": (20, 10), "medium": (6, 0), "low": (0, 0),
}
WET_PENALTY: dict[Level, int] = {"low": 18, "medium": 6, "high": 0}

GRASS_LAND = {"meadow", "pasture"}
# The KOWR "Podstawy naukowe" material requires showing the uncertainty of results — say it plainly.
UNCERTAINTY = (
    "Ocena orientacyjna. Dane o działce są prawdziwe (gleba, ewidencja gruntów, pogoda z 10 lat, spadek "
    "terenu), ale wymagania upraw to wartości z literatury (FAO-56, FAO-33, grupy upraw IUNG-PIB), "
    "a punktacja to jawna heurystyka — nie była sprawdzana na plonach z tej okolicy."
)
NOT_CONSIDERED = (
    UNCERTAINTY + " Nie uwzględniamy cen, opłacalności, płodozmianu, odczynu gleby (pH), odmian, maszyn "
    "ani dopłat — to ocena dopasowania do wody i gleby, nie porada ekonomiczna."
)

_CLASS_RE = re.compile(r"(IV|VI|V|I{1,3})(A|B|Z)?$")
_CLASS_LEVEL = {"I": "good", "II": "good", "IIIA": "good", "III": "medium", "IIIB": "medium",
                "IVA": "medium", "IV": "medium", "IVB": "poor", "V": "poor", "VI": "poor", "VIZ": "poor"}
_LEVEL_RANK = {"good": 0, "medium": 1, "poor": 2}


def _clamp(x: float) -> float:
    return max(0.0, min(1.0, x))


@dataclass
class Site:
    soil_level: str | None = None  # good / medium / poor
    soil_desc: str = ""
    soil_refs: list[str] = field(default_factory=list)
    soil_from_egib: bool = False
    dryness: float | None = None  # 0 = wet summers, 1 = very dry
    dry_refs: list[str] = field(default_factory=list)
    wet: bool = False
    wet_desc: str = ""


def _egib_soil_level(classes: list[str]) -> str | None:
    levels = []
    for c in classes:
        m = _CLASS_RE.search(c.strip().upper())
        if m and (lvl := _CLASS_LEVEL.get(m.group(1) + (m.group(2) or ""))):
            levels.append(lvl)
    if not levels:
        return None
    levels.sort(key=_LEVEL_RANK.__getitem__)
    return levels[len(levels) // 2]  # median class of the parcel


def site_from_facts(f: Facts) -> Site:
    s = Site()
    egib = _egib_soil_level(f.land_soil_classes)
    if egib:
        s.soil_level, s.soil_from_egib = egib, True
        s.soil_desc = "klasa gleby " + ", ".join(f.land_soil_classes)
        s.soil_refs = ["ev_land_use"]
    elif f.sand is not None or f.awc is not None:
        poor = (f.sand is not None and f.sand >= SAND_POOR) or (f.awc is not None and f.awc < AWC_POOR)
        good = f.awc is not None and f.awc >= AWC_GOOD and (f.sand is None or f.sand < SAND_GOOD_MAX)
        s.soil_level = "poor" if poor else "good" if good else "medium"
        parts = []
        if f.sand is not None:
            parts.append(f"{fmt(f.sand, 0)}% piasku")
            s.soil_refs.append("ev_soil_sand")
        if f.awc is not None:
            parts.append(f"zatrzyma ok. {fmt(f.awc, 0)} mm wody")
            s.soil_refs.append("ev_soil_awc")
        s.soil_desc = ", ".join(parts)

    parts_dry: list[float] = []
    if f.kbw_summer_mean is not None:
        parts_dry.append(_clamp((KBW_SUMMER_WET - f.kbw_summer_mean) / (KBW_SUMMER_WET - KBW_SUMMER_DRY)))
        s.dry_refs.append("ev_kbw_summer")
    if f.dry_summers:
        n, total = f.dry_summers
        parts_dry.append(n / total)
        s.dry_refs.append("ev_dry_summers")
    if parts_dry:
        s.dryness = sum(parts_dry) / len(parts_dry)

    near = f.water_dist is not None and f.water_dist <= WATER_NEAR_M
    if f.clay is not None and (f.clay >= CLAY_VERY_HEAVY or (f.clay >= CLAY_HEAVY and near)):
        s.wet = True
        s.wet_desc = f"gleba jest ciężka (ił {fmt(f.clay, 0)}%)" + (" i blisko jest woda" if near else "")
    return s


def _score(p: FitProfile, f: Facts, site: Site) -> CropFitItem:
    pros: list[str] = []
    cons: list[str] = []
    refs: list[str] = []
    score = 100

    # water: sensitivity × (dry summers + little water in the root zone)
    dry = site.dryness if site.dryness is not None else 0.5
    root = min(p["rootDepthM"], AWC_DEPTH_M)
    root_water = f.awc * root if f.awc is not None else None
    low_store = (_clamp((ROOT_WATER_OK_MM - root_water) / (ROOT_WATER_OK_MM - ROOT_WATER_MIN_MM))
                 if root_water is not None else 0.5)
    pen = round(WATER_PENALTY_MAX * p["sensitivity"] * (DRY_WEIGHT * dry + (1 - DRY_WEIGHT) * low_store))
    score -= pen
    if pen >= 15:
        if root_water is not None:
            cons.append(f"Mało wody dla korzeni: sięgają ok. {fmt(p['rootDepthM'])} m, a gleba zatrzyma w tej "
                        f"warstwie ok. {fmt(root_water, 0)} mm. Uprawa jest wrażliwa na suszę.")
            refs.append("ev_soil_awc")
        else:
            cons.append("Uprawa jest wrażliwa na suszę, a lata bywają tu suche.")
        refs += site.dry_refs
    elif p["sensitivity"] <= 0.4 and dry >= 0.4:
        pros.append("Dobrze znosi suche lata.")
        refs += site.dry_refs
    if (p["rootDepthM"] >= DEEP_ROOT_M and p["sensitivity"] <= DEEP_ROOT_MAX_SENSITIVITY
            and (low_store >= 0.3 or dry >= 0.5)):
        score += DEEP_ROOT_BONUS
        pros.append(f"Głębokie korzenie (do ok. {fmt(p['rootDepthM'])} m) sięgają po wodę niżej niż większość upraw.")

    # soil quality vs what the crop needs
    if site.soil_level:
        pen = SOIL_PENALTY.get((p["soilNeed"], site.soil_level), 0)
        score -= pen
        if pen:
            refs += site.soil_refs
            if p["soilNeed"] == "high" and site.soil_level == "poor":
                cons.append(f"Potrzebuje dobrej gleby, a tu jest słaba ({site.soil_desc}).")
            elif p["soilNeed"] == "high":
                cons.append(f"Najlepiej plonuje na lepszej glebie niż tutaj ({site.soil_desc}).")
            else:
                cons.append(f"Na tak słabej glebie ({site.soil_desc}) plony będą niepewne.")
        elif p["soilNeed"] == "low" and site.soil_level == "poor":
            pros.append("Radzi sobie na słabej, lekkiej glebie.")
            refs += site.soil_refs
        elif p["soilNeed"] == "low" and site.soil_level == "good":
            score -= GOOD_SOIL_UNDERUSE
            cons.append(f"Urośnie, ale na tak dobrej glebie ({site.soil_desc}) lepiej wykorzystają ją "
                        "bardziej wymagające uprawy.")
            refs += site.soil_refs
        elif p["soilNeed"] == "high" and site.soil_level == "good":
            pros.append(f"Ma tu dobrą glebę, jakiej potrzebuje ({site.soil_desc}).")
            refs += site.soil_refs

    # slope: bare soil between rows → runoff and erosion
    if f.slope is not None and f.slope >= SLOPE_MODERATE:
        steep, moderate = SLOPE_PENALTY[p["erosionRisk"]]
        pen = steep if f.slope >= SLOPE_STEEP else moderate
        score -= pen
        if pen and p["erosionRisk"] == "high":
            cons.append(f"Na spadku {fmt(f.slope)}% uprawa rzędowa odsłania glebę — deszcz spływa i zabiera ziemię.")
            refs.append("ev_slope")
        elif pen:
            cons.append(f"Na spadku {fmt(f.slope)}% część deszczu spłynie z pola.")
            refs.append("ev_slope")
        elif p["erosionRisk"] == "low":
            pros.append(f"Okrywa glebę przez większość roku — na spadku {fmt(f.slope)}% chroni przed spływem.")
            refs.append("ev_slope")

    # waterlogging
    if site.wet:
        pen = WET_PENALTY[p["wetTolerance"]]
        score -= pen
        wet_refs = ["ev_soil_clay"] + (["ev_water"] if "woda" in site.wet_desc else [])
        if pen >= 10:
            cons.append(f"Nie znosi zastoisk wody, a {site.wet_desc} — wiosną woda może stać na polu.")
            refs += wet_refs
        elif p["wetTolerance"] == "high":
            pros.append("Znosi okresowe podmoknięcie gleby.")
            refs += wet_refs

    # registered land use
    if f.land_category in GRASS_LAND and f.land_label:
        if p["id"] == "laka":
            pros.append(f"Zgodne z ewidencją gruntów ({f.land_label}).")
        else:
            score -= TUZ_PENALTY
            cons.append(f"W ewidencji gruntów to {f.land_label} — zaoranie trwałego użytku zielonego może być "
                        "zabronione (ochrona TUZ).")
        refs.append("ev_land_use")
    elif f.land_category == "orchard" and f.land_label and p["group"] in ("sad", "jagodowe"):
        pros.append(f"Zgodne z ewidencją gruntów ({f.land_label}).")
        refs.append("ev_land_use")

    score = max(0, min(100, score))
    fit = "good" if score >= FIT_GOOD else "medium" if score >= FIT_MEDIUM else "poor"
    return CropFitItem(id=p["id"], name=p["namePl"], groupId=p["group"], score0to100=score, fit=fit,
                       pros=pros, cons=cons, evidenceRefs=list(dict.fromkeys(refs)))


def rank_crop_fit(f: Facts, selected_group: str | None = None) -> CropFit | None:
    """None on non-agricultural land (built-up, forest, water…) — no crop advice there."""
    if f.land_agri is False:
        return None
    site = site_from_facts(f)
    # ties: the more drought-resilient crop first (then id, so the order is always the same)
    scored = sorted(((_score(p, f, site), p) for p in FIT_PROFILES),
                    key=lambda ip: (-ip[0].score0to100, ip[1]["sensitivity"], ip[1]["id"]))
    items = [i for i, _ in scored]

    # Crop choice is a long-term decision: only multi-year conditions, never the current season
    # (KOWR material: current drought ≠ multi-year susceptibility).
    basis = []
    if f.awc is not None:
        basis.append("ile wody gleba zatrzymuje w zasięgu korzeni (SoilGrids, z uwzględnieniem próchnicy)")
    if site.dryness is not None:
        basis.append("jak suche są tu lata (letni bilans wodny z 10 lat, nie tylko ten sezon)")
    if site.soil_level:
        basis.append("jakość gleby (" + ("klasa z ewidencji gruntów" if site.soil_from_egib else "skład gleby z SoilGrids") + ")")
    if f.slope is not None:
        basis.append("spadek terenu")
    if f.clay is not None:
        basis.append("ryzyko zastoisk wody (ił w glebie, bliskość rowów i cieków)")
    if f.land_category:
        basis.append("rodzaj użytku w ewidencji gruntów")

    conf: Confidence = "medium" if f.awc is not None and site.dryness is not None else "low"
    return CropFit(ranking=items, selectedGroupId=selected_group, confidence=conf, basis=basis,
                   notConsidered=NOT_CONSIDERED)
