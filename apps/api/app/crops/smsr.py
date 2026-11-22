"""IUNG SMSR / MRiRW critical climatic water balance (KBW) thresholds.

Legal source: Rozporządzenie Ministra Rolnictwa i Rozwoju Wsi z dnia 11 kwietnia 2019 r.
(Dz.U. 2019 poz. 739). Tables: https://susza.iung.pulawy.pl/progi/

A 6-dekad (≈60-day) KBW below the crop×soil×period threshold corresponds on average
to a ~20% yield loss (IUNG yield models). We compare Open-Meteo P−ET0 over the last
60 days to the matching window — same definition of KBW, honest note that SMSR uses
fixed calendar windows and Penman ET while we use Open-Meteo ET0.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Literal

SoilCat = Literal[1, 2, 3, 4]
SoilCatSource = Literal["iung_map", "awc"]

SMSR_SOURCE_URL = "https://susza.iung.pulawy.pl/progi/"
SMSR_SOURCE_NAME = "IUNG SMSR – progi KBW (MRiRW 2019)"
SMSR_REGULATION = "Dz.U. 2019 poz. 739"

# 14 fixed 6-dekad monitoring windows (start, end) — day-of-year style month/day.
PERIODS: list[tuple[str, tuple[int, int], tuple[int, int]]] = [
    ("21.III–20.V", (3, 21), (5, 20)),
    ("1.IV–31.V", (4, 1), (5, 31)),
    ("11.IV–10.VI", (4, 11), (6, 10)),
    ("21.IV–20.VI", (4, 21), (6, 20)),
    ("1.V–30.VI", (5, 1), (6, 30)),
    ("11.V–10.VII", (5, 11), (7, 10)),
    ("21.V–20.VII", (5, 21), (7, 20)),
    ("1.VI–31.VII", (6, 1), (7, 31)),
    ("11.VI–10.VIII", (6, 11), (8, 10)),
    ("21.VI–20.VIII", (6, 21), (8, 20)),
    ("1.VII–31.VIII", (7, 1), (8, 31)),
    ("11.VII–10.IX", (7, 11), (9, 10)),
    ("21.VII–20.IX", (7, 21), (9, 20)),
    ("1.VIII–30.IX", (8, 1), (9, 30)),
]

# Thresholds[mm]: soil cat 1–4 → list of 14 values (None = "x" / "-" = not applicable).
# Keys = exact SMSR crop category ids (same as catalog). Source: susza.iung.pulawy.pl/progi/
_THRESHOLDS: dict[str, dict[int, list[float | None]]] = {
    "zboza_ozime": {
        1: [-129, -132, -137, -145, -154, -165, -180, -199, -220, None, None, None, None, None],
        2: [-150, -153, -158, -166, -175, -186, -201, -220, -241, None, None, None, None, None],
        3: [-188, -191, -196, -204, -213, -224, -239, -258, -279, None, None, None, None, None],
        4: [-215, -218, -223, -231, -240, -251, -266, -285, -306, None, None, None, None, None],
    },
    "zboza_jare": {
        1: [-125, -127, -130, -135, -142, -153, -169, -186, -207, None, None, None, None, None],
        2: [-144, -146, -149, -154, -161, -172, -188, -205, -226, None, None, None, None, None],
        3: [-174, -176, -179, -184, -191, -202, -218, -235, -256, None, None, None, None, None],
        4: [-194, -196, -199, -204, -211, -222, -238, -255, -276, None, None, None, None, None],
    },
    "kukurydza_ziarno": {
        1: [None, None, None, -168, -161, -156, -153, -152, -153, -154, -156, -158, -161, -164],
        2: [None, None, None, -200, -193, -188, -185, -184, -185, -186, -188, -190, -193, -196],
        3: [None, None, None, -236, -229, -224, -221, -220, -221, -222, -224, -226, -229, -232],
        4: [None, None, None, -271, -264, -259, -256, -255, -256, -257, -259, -261, -264, -267],
    },
    "kukurydza_kiszonka": {
        1: [None, None, None, -168, -161, -156, -153, -152, -152, -152, -153, -155, -157, -160],
        2: [None, None, None, -200, -193, -188, -185, -184, -184, -184, -185, -187, -189, -192],
        3: [None, None, None, -236, -229, -224, -221, -220, -220, -220, -221, -223, -225, -228],
        4: [None, None, None, -271, -264, -259, -256, -255, -255, -255, -256, -258, -260, -263],
    },
    "rzepak": {
        1: [-207, -187, -170, -155, -142, -132, None, None, None, None, None, None, -138, -138],
        2: [-232, -211, -193, -177, -165, -155, None, None, None, None, None, None, -158, -158],
        3: [-275, -254, -236, -220, -208, -198, None, None, None, None, None, None, -205, -205],
        4: [-297, -276, -258, -242, -230, -220, None, None, None, None, None, None, -230, -230],
    },
    "ziemniak": {
        1: [None, None, -238, -232, -226, -219, -210, -200, -189, -178, -168, -157, -147, None],
        2: [None, None, -257, -251, -245, -238, -229, -219, -208, -197, -187, -176, -166, None],
        3: [None, None, -286, -280, -274, -267, -258, -248, -237, -226, -216, -205, -195, None],
        4: [None, None, -306, -300, -294, -287, -278, -268, -257, -246, -236, -225, -215, None],
    },
    "burak": {
        # Soil I not indicated for sugar beet in the regulation.
        1: [None] * 14,
        2: [-250, -248, -245, -241, -237, -232, -226, -220, -212, -202, -192, -182, -169, -155],
        3: [-277, -275, -272, -268, -264, -259, -253, -247, -239, -229, -219, -209, -196, -182],
        4: [-296, -294, -291, -287, -283, -278, -272, -266, -258, -248, -238, -228, -215, -201],
    },
    "chmiel": {
        1: [None, None, None, -230, -220, -212, -205, -199, -194, -190, -186, -182, None, None],
        2: [None, None, None, -248, -238, -230, -223, -217, -212, -208, -204, -200, None, None],
        3: [None, None, None, -285, -275, -267, -260, -254, -249, -245, -241, -237, None, None],
        4: [None, None, None, -302, -292, -284, -277, -271, -266, -262, -258, -254, None, None],
    },
    "tyton": {
        1: [None, None, None, -189, -187, -186, -185, -186, -187, -190, -195, -200, None, None],
        2: [None, None, None, -201, -199, -198, -197, -198, -199, -202, -207, -212, None, None],
        3: [None, None, None, -227, -225, -224, -223, -224, -225, -228, -233, -238, None, None],
        4: [None, None, None, -240, -238, -237, -236, -237, -238, -241, -246, -251, None, None],
    },
    "warzywa": {
        1: [None, None, None, -189, -187, -185, -184, -184, -184, -185, -187, -188, None, None],
        2: [None, None, None, -207, -205, -203, -202, -202, -202, -203, -205, -206, None, None],
        3: [None, None, None, -243, -241, -239, -238, -238, -238, -239, -241, -242, None, None],
        4: [None, None, None, -263, -261, -259, -258, -258, -258, -259, -261, -262, None, None],
    },
    "krzewy": {
        1: [-149, -148, -147, -147, -149, -154, -159, -162, -163, -162, -160, -157, None, None],
        2: [-166, -165, -164, -164, -166, -171, -176, -179, -180, -179, -177, -174, None, None],
        3: [-200, -199, -198, -198, -200, -205, -210, -213, -214, -213, -211, -208, None, None],
        4: [-217, -216, -215, -215, -217, -222, -227, -230, -231, -230, -228, -225, None, None],
    },
    "drzewa": {
        1: [-168, -171, -175, -180, -187, -193, -199, -205, -210, -215, -220, -223, None, None],
        2: [-190, -193, -197, -202, -209, -215, -221, -227, -232, -237, -242, -245, None, None],
        3: [-229, -232, -236, -241, -248, -254, -260, -266, -271, -276, -281, -284, None, None],
        4: [-249, -252, -256, -261, -268, -274, -280, -286, -291, -296, -301, -304, None, None],
    },
    "truskawki": {
        1: [-133, -137, -143, -152, -163, -178, -190, -198, -202, None, None, None, None, None],
        2: [-150, -154, -160, -169, -180, -195, -207, -215, -219, None, None, None, None, None],
        3: [-183, -187, -193, -202, -213, -228, -240, -248, -252, None, None, None, None, None],
        4: [-204, -208, -214, -223, -234, -249, -261, -269, -273, None, None, None, None, None],
    },
    "straczkowe": {
        1: [None, None, None, -161, -161, -163, -165, -166, -167, -168, -170, -172, -174, -176],
        2: [None, None, None, -182, -182, -184, -186, -187, -188, -189, -191, -193, -195, -197],
        3: [None, None, None, -213, -213, -215, -217, -218, -219, -220, -222, -224, -226, -228],
        4: [None, None, None, -234, -234, -236, -238, -239, -240, -241, -243, -245, -247, -249],
    },
}

# IUNG soil drought-susceptibility classes by usable water (WOD ≈ AWC mm/m).
# https://susza.iung.pulawy.pl/kategorie/
AWC_CAT_I_MAX = 127.5
AWC_CAT_II_MAX = 169.9
AWC_CAT_III_MAX = 202.5

# Rolling 60-day KBW is compared with the SMSR window that ends nearest to the analysis date,
# but only if that window ends within this many days – otherwise the two periods differ too much.
MAX_PERIOD_GAP_DAYS = 10
# A SMSR window is a "risk period" for this plot when the drought line was crossed in at least
# this many of the last 10 years (3/10 = roughly one year in three).
RISK_MIN_YEARS = 3


@dataclass(frozen=True)
class SmsrMatch:
    crop_row: str
    soil_cat: SoilCat
    period_label: str
    period_index: int
    threshold_mm: float
    kbw_60d_mm: float
    below_threshold: bool
    margin_mm: float  # kbw − threshold; negative ⇒ drier than SMSR drought line
    soil_source: SoilCatSource = "awc"


@dataclass(frozen=True)
class SmsrWindowStat:
    """One SMSR window over the last 10 years: how often KBW fell below the crop×soil threshold."""
    index: int
    label: str
    start_md: tuple[int, int]
    end_md: tuple[int, int]
    threshold_mm: float | None
    years_below: int
    years_total: int
    below_years: tuple[int, ...]
    median_kbw_mm: float | None


def soil_category_from_awc(awc_mm: float | None) -> SoilCat | None:
    """Map SoilGrids AWC (mm / 1 m) onto IUNG SMSR soil categories I–IV."""
    if awc_mm is None:
        return None
    if awc_mm < AWC_CAT_I_MAX:
        return 1
    if awc_mm <= AWC_CAT_II_MAX:
        return 2
    if awc_mm <= AWC_CAT_III_MAX:
        return 3
    return 4


def _md(d: date) -> tuple[int, int]:
    return d.month, d.day


def _date_in_year(year: int, md: tuple[int, int]) -> date:
    return date(year, md[0], md[1])


def pick_period_index(analysis_date: date) -> int | None:
    """Choose the SMSR 6-dekad window whose end is nearest to analysis_date (monitoring season)."""
    if analysis_date.month < 3 or (analysis_date.month == 3 and analysis_date.day < 21):
        return None
    if analysis_date.month > 9 or (analysis_date.month == 9 and analysis_date.day > 30):
        return None

    best_i, best_dist = None, 10**9
    for i, (_label, _start, end_md) in enumerate(PERIODS):
        end = _date_in_year(analysis_date.year, end_md)
        dist = abs((analysis_date - end).days)
        if dist < best_dist:
            best_i, best_dist = i, dist
    return best_i if best_dist <= MAX_PERIOD_GAP_DAYS else None


def lookup_threshold(crop_row: str, soil_cat: SoilCat, period_index: int) -> float | None:
    row = _THRESHOLDS.get(crop_row)
    if not row:
        return None
    # "-" in the regulation (sugar beet on soil I) = crop not indicated → no threshold, never borrowed.
    vals = row.get(soil_cat)
    if not vals or period_index < 0 or period_index >= len(vals):
        return None
    return vals[period_index]


def evaluate_smsr(
    *,
    crop_id: str,
    analysis_date: date,
    kbw_60d: float | None,
    awc_mm: float | None,
    soil_cat: SoilCat | None = None,
) -> SmsrMatch | None:
    """Compare 60-day KBW to the MRiRW/IUNG threshold for this crop, soil, and period.

    `soil_cat` from the IUNG category map wins; the SoilGrids AWC proxy is only a fallback.
    """
    if crop_id not in _THRESHOLDS or kbw_60d is None:
        return None
    soil = soil_cat or soil_category_from_awc(awc_mm)
    source: SoilCatSource = "iung_map" if soil_cat else "awc"
    if soil is None:
        return None
    period_i = pick_period_index(analysis_date)
    if period_i is None:
        return None
    thr = lookup_threshold(crop_id, soil, period_i)
    if thr is None:
        return None
    margin = kbw_60d - thr
    return SmsrMatch(
        crop_row=crop_id,
        soil_cat=soil,
        period_label=PERIODS[period_i][0],
        period_index=period_i,
        threshold_mm=thr,
        kbw_60d_mm=kbw_60d,
        below_threshold=kbw_60d < thr,
        margin_mm=round(margin, 1),
        soil_source=source,
    )


def crop_not_indicated(crop_id: str, soil_cat: SoilCat | None) -> bool:
    """True when the regulation marks the crop as not indicated on this soil ("-": sugar beet, soil I)."""
    row = _THRESHOLDS.get(crop_id)
    return bool(row and soil_cat and all(v is None for v in row.get(soil_cat, [])))


def smsr_history(crop_id: str, soil_cat: SoilCat | None, windows: list[dict]) -> list[SmsrWindowStat]:
    """Per SMSR window: in how many of the last 10 years KBW fell below this crop×soil threshold.

    `windows` = meteo adapter `kbw_smsr_windows` ([{index, by_year: [{year, kbw}]}]).
    Windows without a threshold ("x": no yield loss expected then) are kept with threshold None.
    """
    if crop_id not in _THRESHOLDS or soil_cat is None:
        return []
    out: list[SmsrWindowStat] = []
    for w in windows:
        i = int(w.get("index", -1))
        if not 0 <= i < len(PERIODS):
            continue
        rows = [r for r in w.get("by_year") or [] if r.get("kbw") is not None]
        thr = lookup_threshold(crop_id, soil_cat, i)
        below = tuple(sorted(int(r["year"]) for r in rows if thr is not None and r["kbw"] < thr))
        vals = sorted(float(r["kbw"]) for r in rows)
        med = None
        if vals:
            n = len(vals)
            med = round(vals[n // 2] if n % 2 else (vals[n // 2 - 1] + vals[n // 2]) / 2, 1)
        label, start_md, end_md = PERIODS[i]
        out.append(SmsrWindowStat(index=i, label=label, start_md=start_md, end_md=end_md, threshold_mm=thr,
                                  years_below=len(below), years_total=len(rows), below_years=below,
                                  median_kbw_mm=med))
    return out


def soil_cat_label(cat: SoilCat) -> str:
    return {1: "I (bardzo lekka)", 2: "II (lekka)", 3: "III (średnia)", 4: "IV (ciężka)"}[cat]
