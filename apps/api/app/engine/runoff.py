"""How much rain runs off this plot? – SCS Curve Number method (USDA NRCS).

Q = (P − Ia)² / (P − Ia + S) for P > Ia, with S = 25400 / CN − 254 (mm) and Ia = 0.2·S
(USDA NRCS, National Engineering Handbook Part 630, ch. 10; TR-55, 1986), applied to every
day with rain in the last 10 years (daily rain from Open-Meteo / ERA5).

CN from TR-55 tables 2-2b/2-2c (hydrologic condition "good", straight rows) by crop cover and
hydrologic soil group. The soil group follows the texture rules of NEH 630 ch. 7 applied to the
SoilGrids topsoil (no restrictive layer assumed):
    A: clay < 10 % and sand > 90 %   B: clay ≤ 20 %   C: clay ≤ 40 %   D: clay > 40 %

Orientation only: no snowmelt (frozen days are excluded upstream), no antecedent-moisture
adjustment, the whole plot is assumed to drain to one place. The "storm" used for the pond is
the 5th-largest daily runoff in 10 years – on average reached once every ~2 years
(partial-duration series, return period ≈ N_years / rank).
"""

from __future__ import annotations

from dataclasses import dataclass

from app.engine.facts import Facts

# TR-55 (1986) runoff curve numbers, hydrologic condition "good".
CN_TABLE: dict[str, dict[str, int]] = {
    "row_crops": {"A": 67, "B": 78, "C": 85, "D": 89},    # 2-2b row crops, straight row, good
    "small_grain": {"A": 63, "B": 75, "C": 83, "D": 87},  # 2-2b small grain, straight row, good
    "fallow": {"A": 77, "B": 86, "C": 91, "D": 94},       # 2-2b fallow, bare soil
    "meadow": {"A": 30, "B": 58, "C": 71, "D": 78},       # 2-2c meadow (mown, not grazed)
    "pasture": {"A": 39, "B": 61, "C": 74, "D": 80},      # 2-2c pasture, good
    "orchard": {"A": 32, "B": 58, "C": 72, "D": 79},      # 2-2c woods–grass combination, good
}
COVER_PL = {
    "row_crops": "uprawa rzędowa", "small_grain": "zboża i rośliny gęstego siewu", "fallow": "goła gleba",
    "meadow": "łąka", "pasture": "pastwisko", "orchard": "sad lub plantacja z trawą",
}
CROP_COVER = {
    "zboza_ozime": "small_grain", "zboza_jare": "small_grain", "rzepak": "small_grain",
    "straczkowe": "small_grain",
    "kukurydza_ziarno": "row_crops", "kukurydza_kiszonka": "row_crops", "ziemniak": "row_crops",
    "burak": "row_crops", "warzywa": "row_crops", "tyton": "row_crops", "chmiel": "row_crops",
    "truskawki": "row_crops",
    "drzewa": "orchard", "krzewy": "orchard",
    "brak": "fallow",
}
LAND_COVER = {"meadow": "meadow", "pasture": "pasture", "orchard": "orchard"}

STORM_RANK = 5          # 5th largest in 10 years ≈ once every 2 years
POND_DEPTH_M = 1.5
MIN_RUNOFF_YEAR_MM = 1.0  # below: practically no runoff → nothing to show


@dataclass(frozen=True)
class RunoffEstimate:
    cn: int
    hsg: str
    cover: str
    cover_pl: str
    precip_year_mm: float
    runoff_year_mm: float
    volume_year_m3: int
    storm_rain_mm: float | None
    storm_runoff_mm: float | None
    pond_m3: int | None
    pond_area_m2: int | None


def hydrologic_group(sand: float | None, clay: float | None) -> str | None:
    if sand is None or clay is None:
        return None
    if clay < 10 and sand > 90:
        return "A"
    if clay <= 20:
        return "B"
    if clay <= 40:
        return "C"
    return "D"


def scs_runoff_mm(p: float, cn: int) -> float:
    s = 25400.0 / cn - 254.0
    ia = 0.2 * s
    return (p - ia) ** 2 / (p - ia + s) if p > ia else 0.0


def _round_m3(x: float) -> int:
    return int(round(x, -1)) if x >= 100 else int(round(x))


def estimate_runoff(f: Facts) -> RunoffEstimate | None:
    hsg = hydrologic_group(f.sand, f.clay)
    if hsg is None or not f.area_ha or not f.rain_years or f.precip_year is None:
        return None
    cover = LAND_COVER.get(f.land_category or "") or CROP_COVER.get(f.crop_id or "", "row_crops")
    cn = CN_TABLE[cover][hsg]
    events = sorted((scs_runoff_mm(p, cn) for p in f.rain_days), reverse=True)
    q_year = sum(events) / f.rain_years
    if q_year < MIN_RUNOFF_YEAR_MM:
        return None
    m3_per_mm = f.area_ha * 10.0  # 1 mm over 1 ha = 10 m³
    storm_q = events[STORM_RANK - 1] if len(events) >= STORM_RANK and events[STORM_RANK - 1] > 0 else None
    storm_p = None
    if storm_q is not None:
        rains = sorted(f.rain_days, reverse=True)
        storm_p = rains[STORM_RANK - 1]  # Q is monotonic in P → same rank
    pond = _round_m3(storm_q * m3_per_mm) if storm_q is not None else None
    return RunoffEstimate(
        cn=cn, hsg=hsg, cover=cover, cover_pl=COVER_PL[cover],
        precip_year_mm=f.precip_year, runoff_year_mm=round(q_year, 1),
        volume_year_m3=_round_m3(q_year * m3_per_mm),
        storm_rain_mm=storm_p, storm_runoff_mm=round(storm_q, 1) if storm_q is not None else None,
        pond_m3=pond if pond else None,
        pond_area_m2=int(round(pond / POND_DEPTH_M)) if pond else None,
    )
