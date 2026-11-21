"""Moisture assessment: current situation vs multi-year susceptibility.

Thresholds are tunable constants — honest but simple water-balance proxies.
"""

from __future__ import annotations

from typing import Any

from app.schemas.evidence import (
    MoistureAssessment,
    MoistureLevel,
    SituationBlock,
    SusceptibilityBlock,
    SusceptibilityLevel,
)

# --- tunable thresholds ---
PRECIP_RATIO_OK = 0.90
PRECIP_RATIO_WATCH = 0.70
PRECIP_RATIO_DEFICIT = 0.50
DRY_SPELL_WATCH = 7
DRY_SPELL_DEFICIT = 14
DRY_SPELL_SEVERE = 21
AWC_LOW = 60.0
AWC_HIGH = 110.0
HIGH_SENSITIVITY = 0.65


def storage_score(sand_pct: float, clay_pct: float, soc_pct: float, awc_mm: float) -> float:
    """0–100 storage proxy from texture + SOC + AWC."""
    sand_pen = max(0.0, sand_pct - 40) * 0.6
    clay_bonus = min(clay_pct, 35) * 0.8
    soc_bonus = soc_pct * 12
    awc_norm = min(100.0, max(0.0, (awc_mm - 20) / 1.4))
    raw = 35 + clay_bonus + soc_bonus + awc_norm * 0.35 - sand_pen
    return max(0.0, min(100.0, raw))


def _current_level(score: int) -> MoistureLevel:
    if score >= 70:
        return "ok"
    if score >= 50:
        return "watch"
    if score >= 30:
        return "deficit"
    return "severe"


def _susceptibility_level(score: int) -> SusceptibilityLevel:
    if score < 40:
        return "low"
    if score < 65:
        return "moderate"
    return "high"


def assess_moisture(
    *,
    meteo: dict[str, Any],
    soil: dict[str, Any],
    sat: dict[str, Any],
    drought: dict[str, Any],
    crop_sensitivity: float,
    missing_flags: list[str],
) -> MoistureAssessment:
    precip = float(meteo.get("precipMmLast30d", 0))
    climate = float(meteo.get("precipMmClimate30d", 1) or 1)
    dry_spell = int(meteo.get("drySpellDays", 0))
    anomaly_10y = float(meteo.get("precipAnomalyPct10y", 0))
    monthly = list(meteo.get("monthlyPrecipMm") or [])

    sand = float(soil.get("sandPct", 50))
    clay = float(soil.get("clayPct", 15))
    soc = float(soil.get("socPct", 1.0))
    awc = float(soil.get("awcMmProxy", 70))

    store = storage_score(sand, clay, soc, awc)
    ratio = precip / climate if climate > 0 else 0.0

    # Current moisture score (higher = wetter/better)
    current_score = 55.0
    evidence_cur = ["meteo.precipMmLast30d", "meteo.precipMmClimate30d", "soil.awcMmProxy"]

    if ratio >= PRECIP_RATIO_OK:
        current_score += 25
    elif ratio >= PRECIP_RATIO_WATCH:
        current_score += 5
    elif ratio >= PRECIP_RATIO_DEFICIT:
        current_score -= 15
    else:
        current_score -= 30

    if dry_spell >= DRY_SPELL_SEVERE:
        current_score -= 25
        evidence_cur.append("meteo.drySpellDays")
    elif dry_spell >= DRY_SPELL_DEFICIT:
        current_score -= 15
        evidence_cur.append("meteo.drySpellDays")
    elif dry_spell >= DRY_SPELL_WATCH:
        current_score -= 8
        evidence_cur.append("meteo.drySpellDays")

    # Low AWC hurts short-term buffer
    if awc < AWC_LOW:
        current_score -= 12
    elif awc > AWC_HIGH:
        current_score += 8

    ndvi_anom = sat.get("ndviAnomaly")
    if ndvi_anom is not None:
        evidence_cur.append("sat.ndviAnomaly")
        current_score += float(ndvi_anom) * 40  # negative anomaly hurts

    iung = drought.get("iungClass")
    if iung in ("III", "IV"):
        current_score -= 10
        evidence_cur.append("drought.iungClass")
    elif iung in ("I", "II"):
        current_score -= 4
        evidence_cur.append("drought.iungClass")

    current_score = int(round(max(0, min(100, current_score))))
    cur_level = _current_level(current_score)

    # Multi-year susceptibility (higher = more chronic risk) — separate math
    sus_score = 35.0
    evidence_sus = ["meteo.precipAnomalyPct10y", "crop.droughtSensitivity"]
    if anomaly_10y < -15:
        sus_score += 20
    elif anomaly_10y < -5:
        sus_score += 10
    elif anomaly_10y > 5:
        sus_score -= 10

    # Dry summer months from monthly series
    peak_months: list[int] = []
    if len(monthly) == 12:
        evidence_sus.append("meteo.monthlyPrecipMm")
        mean_m = sum(monthly) / 12
        for i, mm in enumerate(monthly):
            if mm < mean_m * 0.75:
                peak_months.append(i + 1)
        # Focus susceptibility on Jun–Aug dryness
        summer = [monthly[m - 1] for m in (6, 7, 8)]
        summer_mean = sum(summer) / 3
        if summer_mean < mean_m * 0.7:
            sus_score += 18
        elif summer_mean < mean_m * 0.85:
            sus_score += 8

    # Soil storage: low storage → higher chronic susceptibility
    sus_score += (100 - store) * 0.25
    sus_score += crop_sensitivity * 25

    if store < 45:
        evidence_sus.append("soil.awcMmProxy")

    sus_score_i = int(round(max(0, min(100, sus_score))))
    sus_level = _susceptibility_level(sus_score_i)

    # Confidence from completeness
    confidence = 0.9
    uncertainty: list[str] = []
    if "sat.ndviAnomaly" not in evidence_cur:
        confidence -= 0.08
        uncertainty.append("Brak anomalii NDVI — ocena bez sygnału satelitarnego.")
    if not drought.get("iungClass"):
        confidence -= 0.07
        uncertainty.append("Brak klasy suszy IUNG — kontekst wieloletni ograniczony.")
    for flag in missing_flags:
        confidence -= 0.05
        uncertainty.append(flag)
    confidence = max(0.35, min(1.0, confidence))
    uncertainty.append(
        "Ocena pojemności wodnej gleby to proxy z tekstury, nie pomiar lokalny."
    )

    cur_summaries = {
        "ok": "Sytuacja wodna w normie względem ostatnich 30 dni i pojemności gleby.",
        "watch": "Sytuacja wymaga uwagi — opady lub zapas gleby poniżej komfortu.",
        "deficit": "Niedobór wilgoci: opady poniżej normy i/lub ograniczony zapas gleby.",
        "severe": "Silny niedobór wilgoci — ryzyko stresu wodnego uprawy jest wysokie.",
    }
    sus_summaries = {
        "low": "Wieloletnia podatność niska — lokalizacja zwykle nie jest chronicznie sucha.",
        "moderate": "Wieloletnia podatność umiarkowana — w suchszych miesiącach ryzyko rośnie.",
        "high": "Wieloletnia podatność wysoka — gleba i klimat sprzyjają powtarzalnym niedoborom.",
    }

    return MoistureAssessment(
        current=SituationBlock(
            level=cur_level,
            score0to100=current_score,
            summaryPl=cur_summaries[cur_level],
            evidenceIds=sorted(set(evidence_cur)),
        ),
        multiYearSusceptibility=SusceptibilityBlock(
            level=sus_level,
            score0to100=sus_score_i,
            peakMonths=peak_months[:6],
            summaryPl=sus_summaries[sus_level],
            evidenceIds=sorted(set(evidence_sus)),
        ),
        confidence0to1=round(confidence, 2),
        uncertaintyNotes=uncertainty,
    )
