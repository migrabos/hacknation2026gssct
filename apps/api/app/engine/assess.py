"""Moisture assessment: current situation (now) ≠ multi-year susceptibility (chronic).

Deterministic point scores from simple, documented thresholds. Missing inputs
skip their rule and lower confidence — never replaced with guessed values.
"""

from __future__ import annotations

from app.engine.facts import Facts, fmt
from app.schemas.evidence import (
    CurrentBlock,
    MoistureAssessment,
    MoistureLevel,
    RiskLevel,
    SusceptibilityBlock,
    confidence_label,
)

# --- tunable thresholds (documented in docs/verify.md) ---
PRECIP_RATIO_OK = 0.90       # ≥ 90 % of the 10-year median for the same 30 days
PRECIP_RATIO_WATCH = 0.70
PRECIP_RATIO_DEFICIT = 0.50
KBW_PCT_VERY_LOW = 10        # driest 10 % of the last 10 years
KBW_PCT_LOW = 25
KBW_PCT_HIGH = 75
DRY_SPELL_WATCH = 7
DRY_SPELL_DEFICIT = 14
DRY_SPELL_SEVERE = 21
AWC_LOW = 110.0              # mm / 1 m — same class limits as the soil adapter
AWC_HIGH = 155.0
SAND_HIGH = 55.0
HIGH_SENSITIVITY = 0.65
SUMMER_KBW_VERY_DRY = -150.0
SUMMER_KBW_DRY = -100.0
SUMMER_KBW_WET = -50.0


def storage_score(f: Facts) -> float | None:
    """0–100 soil water storage proxy (AWC-based, texture/SOC as modifiers)."""
    if f.awc is None:
        return None
    score = (f.awc - 60.0) / 1.4  # 60 mm → 0, 200 mm → 100
    if f.sand is not None:
        score -= max(0.0, f.sand - 60.0) * 0.4
    if f.soc is not None:
        score += min(f.soc, 3.0) * 3
    return max(0.0, min(100.0, score))


def _current_level(score: int) -> MoistureLevel:
    if score >= 80:
        return "wet"
    if score >= 55:
        return "normal"
    if score >= 32:
        return "dry"
    return "very_dry"


def _sus_level(score: int) -> RiskLevel:
    if score < 40:
        return "low"
    if score < 62:
        return "medium"
    return "high"


CUR_HEADLINE: dict[MoistureLevel, str] = {
    "wet": "Na działce jest teraz wilgotno",
    "normal": "Wilgotność jest teraz w normie",
    "dry": "Na działce jest teraz sucho",
    "very_dry": "Na działce jest teraz bardzo sucho",
}
SUS_HEADLINE: dict[RiskLevel, str] = {
    "low": "Ta działka rzadko cierpi na brak wody",
    "medium": "Ta działka czasem cierpi na brak wody",
    "high": "Ta działka często cierpi na brak wody",
}


def has_meteo(f: Facts) -> bool:
    return f.precip30 is not None or f.kbw30 is not None


def _assess_current(f: Facts) -> CurrentBlock:
    if not has_meteo(f):
        raise RuntimeError("Brak danych meteorologicznych — ocena wilgoci niemożliwa.")

    ratio = f.precip_ratio
    has_kbw_comparison = f.kbw30 is not None and f.kbw_pct is not None
    long_dry_spell = f.dry_spell is not None and f.dry_spell >= DRY_SPELL_WATCH
    if ratio is None and not has_kbw_comparison and not long_dry_spell:
        observations = []
        refs = []
        if f.precip30 is not None:
            observations.append(f"Suma opadów w ostatnich 30 dniach wyniosła {fmt(f.precip30)} mm.")
            refs.append("ev_precip_30d")
        if f.kbw30 is not None:
            observations.append(f"Bilans wodny za ten okres wyniósł {fmt(f.kbw30)} mm.")
            refs.append("ev_kbw_30d")
        return CurrentBlock(level="insufficient_data", headline="Za mało danych do oceny wilgotności",
                            summary=" ".join(observations), confidence="low", evidenceRefs=refs)

    score = 55.0
    refs: list[str] = []
    why: list[str] = []
    conf = 0.9

    if ratio is not None:
        refs.append("ev_precip_30d")
        if ratio >= PRECIP_RATIO_OK:
            score += 20
        elif ratio >= PRECIP_RATIO_WATCH:
            score += 0
        elif ratio >= PRECIP_RATIO_DEFICIT:
            score -= 15
        else:
            score -= 28
        why.append(f"w ostatnich 30 dniach spadło {fmt(f.precip30, 0)} mm deszczu, "
                   f"czyli {fmt(ratio * 100, 0)}% tego, co zwykle")
    else:
        conf -= 0.15

    if has_kbw_comparison:
        refs.append("ev_kbw_30d")
        if f.kbw_pct <= KBW_PCT_VERY_LOW:
            score -= 14
            why.append("bilans wodny jest jednym z najgorszych w ostatnich 10 latach")
        elif f.kbw_pct <= KBW_PCT_LOW:
            score -= 7
            why.append("parowanie wyraźnie przewyższa opady")
        elif f.kbw_pct >= KBW_PCT_HIGH:
            score += 8
    else:
        conf -= 0.08

    if f.dry_spell is not None:
        if f.dry_spell >= DRY_SPELL_SEVERE:
            score -= 18
        elif f.dry_spell >= DRY_SPELL_DEFICIT:
            score -= 10
        elif f.dry_spell >= DRY_SPELL_WATCH:
            score -= 5
        if f.dry_spell >= DRY_SPELL_WATCH:
            refs.append("ev_dry_spell")
            why.append(f"od {fmt(f.dry_spell, 0)} dni nie było deszczu")

    if f.awc is not None:
        refs.append("ev_soil_awc")
        if f.awc < AWC_LOW:
            score -= 8
            why.append("gleba ma mały zapas wody")
        elif f.awc > AWC_HIGH:
            score += 6
    else:
        conf -= 0.1

    if f.cdi is not None:
        if f.cdi >= 1:
            refs.append("ev_cdi")
        score -= {0: 0, 1: 4, 2: 8, 3: 12}.get(f.cdi, 0)
    else:
        conf -= 0.04

    if f.ndvi is not None:
        refs.append("ev_ndvi")  # context only: NDVI depends on crop stage, not scored
    else:
        conf -= 0.05

    cur_score = int(round(max(0, min(100, score))))
    cur_level = _current_level(cur_score)
    cur_summary = (why[0][0].upper() + why[0][1:] + (", " + ", ".join(why[1:3]) if len(why) > 1 else "") + "."
                   if why else f"Bilans wodny z ostatnich 30 dni wyniósł {fmt(f.kbw30)} mm.")
    return CurrentBlock(level=cur_level, headline=CUR_HEADLINE[cur_level], summary=cur_summary,
                        confidence=confidence_label(conf), evidenceRefs=refs, score0to100=cur_score)


def assess_moisture(f: Facts) -> MoistureAssessment:
    current = _assess_current(f)

    # ---------------- multi-year susceptibility (higher = more chronic risk) ----------------
    sus = 30.0
    sus_refs: list[str] = ["ev_crop_sensitivity"]
    sus_why: list[str] = []
    sus_conf = 0.85

    if f.kbw_summer_mean is not None:
        sus_refs.append("ev_kbw_summer")
        if f.kbw_summer_mean < SUMMER_KBW_VERY_DRY:
            sus += 18
            sus_why.append("latem na tym terenie paruje znacznie więcej wody, niż spada deszczu")
        elif f.kbw_summer_mean < SUMMER_KBW_DRY:
            sus += 10
            sus_why.append("latem zwykle brakuje tu wody")
        elif f.kbw_summer_mean > SUMMER_KBW_WET:
            sus -= 8
    else:
        sus_conf -= 0.15

    ds = f.dry_summers
    if ds:
        sus_refs.append("ev_dry_summers")
        share = ds[0] / ds[1]
        sus += 10 * share
        if ds[0]:
            sus_why.append(f"w {ds[0]} z {ds[1]} ostatnich lat lato było suche")

    anom = f.precip365_anomaly_pct
    if anom is not None:
        if anom < -15:
            sus += 8
            sus_refs.append("ev_precip_365d")
            sus_why.append("ostatni rok był wyraźnie suchszy niż zwykle")
        elif anom < -5:
            sus += 4
            sus_refs.append("ev_precip_365d")

    store = storage_score(f)
    if store is not None:
        sus += (100 - store) * 0.22
        sus_refs.append("ev_soil_awc")
        if f.sand is not None and f.sand >= SAND_HIGH:
            sus_refs.append("ev_soil_sand")
            sus_why.append("lekka, piaszczysta gleba słabo trzyma wodę")
        elif store < 35:
            sus_why.append("gleba słabo magazynuje wodę")
    else:
        sus_conf -= 0.15

    sus += f.crop_sens * 20
    sus_score = int(round(max(0, min(100, sus))))
    sus_level = _sus_level(sus_score)
    sus_summary = (sus_why[0][0].upper() + sus_why[0][1:] + (", a " + sus_why[1] if len(sus_why) > 1 else "") + "."
                   if sus_why else "Klimat i gleba w tym miejscu zwykle nie sprzyjają długotrwałym niedoborom wody.")

    return MoistureAssessment(
        current=current,
        susceptibility=SusceptibilityBlock(
            level=sus_level,
            headline=SUS_HEADLINE[sus_level],
            summary=sus_summary,
            confidence=confidence_label(sus_conf),
            evidenceRefs=list(dict.fromkeys(sus_refs)),
            score0to100=sus_score,
        ),
    )
