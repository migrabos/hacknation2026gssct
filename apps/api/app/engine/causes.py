"""Multi-label cause detection with confidence + evidence ids (sorted most-certain first)."""

from __future__ import annotations

from app.engine.assess import (
    AWC_LOW,
    DRY_SPELL_DEFICIT,
    HIGH_SENSITIVITY,
    KBW_PCT_LOW,
    NDMI_ANOM,
    PRECIP_RATIO_WATCH,
    SAND_HIGH,
    satellite_moisture_signal,
)
from app.engine.facts import RUNOFF_PL, SHOW_WEAK_PCT, Facts, fmt
from app.schemas.evidence import Cause, MoistureAssessment, confidence_label

CAUSE_TITLES = {
    "precip_deficit": "Za mało deszczu",
    "low_soil_storage": "Gleba słabo trzyma wodę",
    "runoff": "Część deszczu spływa z pola",
    "crop_sensitivity": "Uprawa potrzebuje dużo wody",
    "bare_soil": "Pole stoi bez okrywy roślinnej",
}

# Bare soil on the satellite image counts as a cause only outside sowing / emergence,
# when the field "should" be covered (after harvest, autumn, winter, early spring).
BARE_CAUSE_PCT = 50.0
OFF_SEASON_MONTHS = {8, 9, 10, 11, 12, 1, 2, 3}
WINTER_CROPS = {"zboza_ozime", "rzepak"}  # sown VIII–X: young sowing looks bare in autumn
WINTER_SOWING_MONTHS = {8, 9, 10, 11}


def bare_soil_off_season(f: Facts) -> bool:
    m = f.scene_month
    if f.bare_pct is None or f.bare_pct < BARE_CAUSE_PCT or m not in OFF_SEASON_MONTHS:
        return False
    if f.crop_id in WINTER_CROPS and m in WINTER_SOWING_MONTHS:
        return False
    return f.land_agri is not False


def _cause(id_: str, conf: float, refs: list[str], text: str) -> Cause:
    conf = round(min(0.95, conf), 2)
    return Cause(id=id_, title=CAUSE_TITLES[id_], explanation=text, confidence=confidence_label(conf),  # type: ignore[arg-type]
                 evidenceRefs=refs, confidence0to1=conf)


def detect_causes(*, assessment: MoistureAssessment, f: Facts) -> list[Cause]:
    causes: list[Cause] = []
    dry_now = assessment.current.level in ("dry", "very_dry")

    # precip_deficit
    ratio = f.precip_ratio
    low_ratio = ratio is not None and ratio < PRECIP_RATIO_WATCH
    low_kbw = f.kbw_pct is not None and f.kbw_pct <= KBW_PCT_LOW
    long_dry = f.dry_spell is not None and f.dry_spell >= 10
    if low_ratio or low_kbw or long_dry:
        conf = 0.5 + (0.25 if ratio is not None and ratio < 0.5 else 0.15 if low_ratio else 0)
        conf += 0.1 if low_kbw else 0
        conf += 0.1 if f.dry_spell is not None and f.dry_spell >= DRY_SPELL_DEFICIT else 0
        parts = []
        if ratio is not None:
            parts.append(f"W ostatnich 30 dniach spadło {fmt(f.precip30, 0)} mm deszczu, "
                         f"a zwykle w tym czasie pada około {fmt(f.precip30_normal, 0)} mm.")
        if f.kbw30 is not None and f.kbw30 < 0:
            parts.append(f"Z pola wyparowało o {fmt(-f.kbw30, 0)} mm więcej wody, niż spadło.")
        if long_dry:
            parts.append(f"Od {fmt(f.dry_spell, 0)} dni nie było deszczu.")
        refs = ["ev_precip_30d", "ev_kbw_30d", "ev_dry_spell"]
        sat_delta, _ = satellite_moisture_signal(f)
        if sat_delta < 0:  # independent confirmation from the satellite image
            conf += 0.1
            refs.append("ev_ndmi")
            anom = f.ndmi_anomaly
            parts.append(
                f"Zdjęcie satelitarne z {f.ndvi_date} to potwierdza: rośliny mają mniej wody niż zwykle "
                f"o tej porze roku (NDMI {fmt(f.ndmi, 2)}, zwykle {fmt(f.hist_ndmi, 2)})."
                if anom is not None and anom <= -NDMI_ANOM else
                f"Zdjęcie satelitarne z {f.ndvi_date} to potwierdza: rośliny mają mało wody w liściach "
                f"(NDMI {fmt(f.ndmi, 2)}).")
        causes.append(_cause("precip_deficit", conf, refs, " ".join(parts)))

    # low_soil_storage
    low_awc = f.awc is not None and f.awc < AWC_LOW
    sandy = f.sand is not None and f.sand >= SAND_HIGH
    if low_awc or sandy:
        conf = 0.5 + (0.25 if f.awc is not None and f.awc < 90 else 0.1 if low_awc else 0) + (0.1 if sandy else 0)
        text = "Gleba"
        if sandy:
            text += f" ma dużo piasku ({fmt(f.sand, 0)}%)"
        if low_awc:
            text += (" i" if sandy else "") + f" może zatrzymać tylko ok. {fmt(f.awc, 0)} mm wody w 1 m profilu"
        text += ". Deszcz szybko w nią wsiąka i ucieka w głąb, poza zasięg korzeni."
        refs = ["ev_soil_sand", "ev_soil_awc", "ev_soil_soc"]
        if f.weak_pct is not None and f.weak_pct >= SHOW_WEAK_PCT:
            text += (f" Na zdjęciu satelitarnym ok. {fmt(f.weak_pct, 0)}% pola ma wyraźnie słabsze rośliny – "
                     "zwykle to lżejsze, wyżej położone miejsca, gdzie brak wody widać najpierw.")
            refs.append("ev_weak_zone")
        causes.append(_cause("low_soil_storage", conf, refs, text))

    # runoff
    if f.slope is not None and (f.slope >= 3.5 or f.runoff in ("medium", "high")):
        conf = 0.45 + (0.2 if f.slope >= 5 else 0.1) + (0.15 if f.runoff == "high" else 0.05)
        causes.append(_cause(
            "runoff", conf, ["ev_slope"],
            f"Działka ma spadek ok. {fmt(f.slope)}% (ryzyko spływu: {RUNOFF_PL.get(f.runoff or '', 'nieznane')}). "
            "Przy ulewach część wody spływa po powierzchni, zamiast wsiąkać.",
        ))

    # crop_sensitivity — FAO Ky (structural) and/or SMSR threshold breach (situational)
    smsr_hit = f.smsr is not None and f.smsr.below_threshold
    high_ky = f.crop_sens >= HIGH_SENSITIVITY
    if smsr_hit or (high_ky and (dry_now or assessment.susceptibility.level == "high")):
        refs = ["ev_crop_sensitivity"]
        if f.fao_ky is not None:
            refs.append("ev_fao_ky")
        parts: list[str] = []
        if high_ky:
            if f.fao_ky is not None:
                parts.append(
                    f"Ta uprawa ma wysoki współczynnik FAO Ky ({fmt(f.fao_ky, 2)}) – "
                    "plon mocno spada przy niedoborze wody."
                )
            else:
                parts.append("Ta uprawa jest bardzo wrażliwa na brak wody.")
        if smsr_hit and f.smsr is not None:
            refs.extend(["ev_smsr_threshold", "ev_kbw_60d"])
            parts.append(
                f"Bilans wodny 60 dni ({fmt(f.smsr.kbw_60d_mm, 0)} mm) jest poniżej progu SMSR "
                f"({fmt(f.smsr.threshold_mm, 0)} mm) dla tej uprawy i kategorii gleby – "
                "to poziom odpowiadający przeciętnie ok. 20% spadku plonu."
            )
        elif high_ky:
            parts.append("Nawet krótki niedobór może obniżyć plon.")
        conf = 0.4 + f.crop_sens * 0.25 + (0.15 if smsr_hit else 0)
        causes.append(_cause("crop_sensitivity", conf, refs, " ".join(parts)))

    # bare_soil — satellite: most of the plot without green cover when it could be covered
    if bare_soil_off_season(f):
        conf = 0.55 + (0.15 if f.bare_pct >= 75 else 0) + (0.1 if (f.sand or 0) >= SAND_HIGH or
                                                             (f.awc is not None and f.awc < AWC_LOW) else 0)
        text = (f"Na zdjęciu satelitarnym z {f.ndvi_date} ok. {fmt(f.bare_pct, 0)}% działki to odkryta gleba "
                "bez roślin. Słońce i wiatr wysuszają ją szybciej, a deszcz łatwiej ją zmywa – woda nie zostaje "
                "w polu.")
        refs = ["ev_bare_soil"]
        if f.slope is not None and f.slope >= 3.5:
            text += f" Przy spadku {fmt(f.slope)}% odkryta gleba jest też narażona na spływ i erozję."
            refs.append("ev_slope")
        causes.append(_cause("bare_soil", conf, refs, text))

    causes.sort(key=lambda c: -(c.confidence0to1 or 0))
    return causes
