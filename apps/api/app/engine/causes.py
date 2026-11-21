"""Multi-label cause detection with confidence + evidence ids (sorted most-certain first)."""

from __future__ import annotations

from app.engine.assess import (
    AWC_LOW,
    DRY_SPELL_DEFICIT,
    HIGH_SENSITIVITY,
    KBW_PCT_LOW,
    PRECIP_RATIO_WATCH,
    SAND_HIGH,
)
from app.engine.facts import RUNOFF_PL, Facts, fmt
from app.schemas.evidence import Cause, MoistureAssessment, confidence_label

CAUSE_TITLES = {
    "precip_deficit": "Za mało deszczu",
    "low_soil_storage": "Gleba słabo trzyma wodę",
    "runoff": "Część deszczu spływa z pola",
    "crop_sensitivity": "Uprawa potrzebuje dużo wody",
}


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
        causes.append(_cause("precip_deficit", conf, ["ev_precip_30d", "ev_kbw_30d", "ev_dry_spell"], " ".join(parts)))

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
        causes.append(_cause("low_soil_storage", conf, ["ev_soil_sand", "ev_soil_awc", "ev_soil_soc"], text))

    # runoff
    if f.slope is not None and (f.slope >= 3.5 or f.runoff in ("medium", "high")):
        conf = 0.45 + (0.2 if f.slope >= 5 else 0.1) + (0.15 if f.runoff == "high" else 0.05)
        causes.append(_cause(
            "runoff", conf, ["ev_slope"],
            f"Działka ma spadek ok. {fmt(f.slope)}% (ryzyko spływu: {RUNOFF_PL.get(f.runoff or '', 'nieznane')}). "
            "Przy ulewach część wody spływa po powierzchni, zamiast wsiąkać.",
        ))

    # crop_sensitivity — only matters when it's not wet
    if f.crop_sens >= HIGH_SENSITIVITY and (dry_now or assessment.susceptibility.level == "high"):
        causes.append(_cause(
            "crop_sensitivity", 0.4 + f.crop_sens * 0.3, ["ev_crop_sensitivity"],
            "Ta uprawa jest bardzo wrażliwa na brak wody, więc nawet krótki niedobór obniża plon.",
        ))

    causes.sort(key=lambda c: -(c.confidence0to1 or 0))
    return causes
