"""Multi-label cause detection with confidence + evidence ids."""

from __future__ import annotations

from typing import Any

from app.engine.assess import AWC_LOW, HIGH_SENSITIVITY, PRECIP_RATIO_WATCH
from app.schemas.evidence import Cause, MoistureAssessment

CAUSE_LABELS = {
    "precip_deficit": "Niedobór opadów",
    "low_soil_storage": "Niska pojemność wodna gleby",
    "runoff": "Spływ powierzchniowy",
    "crop_sensitivity": "Wrażliwość uprawy na suszę",
}


def detect_causes(
    *,
    assessment: MoistureAssessment,
    meteo: dict[str, Any],
    soil: dict[str, Any],
    terrain: dict[str, Any] | None,
    crop_sensitivity: float,
) -> list[Cause]:
    causes: list[Cause] = []

    precip = float(meteo.get("precipMmLast30d", 0))
    climate = float(meteo.get("precipMmClimate30d", 1) or 1)
    dry_spell = int(meteo.get("drySpellDays", 0))
    ratio = precip / climate if climate > 0 else 0.0
    awc = float(soil.get("awcMmProxy", 70))
    sand = float(soil.get("sandPct", 50))

    # precip_deficit
    if ratio < PRECIP_RATIO_WATCH or dry_spell >= 10 or assessment.current.level in (
        "deficit",
        "severe",
    ):
        conf = 0.55
        if ratio < 0.5:
            conf += 0.25
        elif ratio < PRECIP_RATIO_WATCH:
            conf += 0.15
        if dry_spell >= 14:
            conf += 0.1
        causes.append(
            Cause(
                id="precip_deficit",
                labelPl=CAUSE_LABELS["precip_deficit"],
                confidence0to1=round(min(0.95, conf), 2),
                evidenceIds=["meteo.precipMmLast30d", "meteo.precipMmClimate30d", "meteo.drySpellDays"],
                rationalePl=(
                    f"Opady {precip:.0f} mm / 30 dni vs norma {climate:.0f} mm "
                    f"(stosunek {ratio:.2f}); suchy okres {dry_spell} dni."
                ),
            )
        )

    # low_soil_storage
    if awc < AWC_LOW or sand >= 55:
        conf = 0.5 + (0.25 if awc < 45 else 0.1) + (0.1 if sand >= 60 else 0.0)
        causes.append(
            Cause(
                id="low_soil_storage",
                labelPl=CAUSE_LABELS["low_soil_storage"],
                confidence0to1=round(min(0.95, conf), 2),
                evidenceIds=["soil.awcMmProxy", "soil.sandPct"],
                rationalePl=(
                    f"Proxy AWC {awc:.0f} mm i udział piasku {sand:.0f}% "
                    "ograniczają magazynowanie wody w glebie."
                ),
            )
        )

    # runoff
    terrain = terrain or {}
    slope = float(terrain.get("slopePct") or 0)
    runoff_risk = (terrain.get("runoffRisk") or "").lower()
    if slope >= 3.5 or runoff_risk in ("moderate", "high"):
        conf = 0.45 + (0.2 if slope >= 5 else 0.1) + (0.15 if runoff_risk == "high" else 0.05)
        causes.append(
            Cause(
                id="runoff",
                labelPl=CAUSE_LABELS["runoff"],
                confidence0to1=round(min(0.9, conf), 2),
                evidenceIds=["terrain.slopePct", "terrain.runoffRisk"],
                rationalePl=(
                    f"Nachylenie ~{slope:.1f}% i ryzyko spływu '{runoff_risk or 'nieznane'}' "
                    "sprzyjają utracie wody z pola."
                ),
            )
        )

    # crop_sensitivity — fire when crop is sensitive AND moisture not ok
    if crop_sensitivity >= HIGH_SENSITIVITY and assessment.current.level != "ok":
        conf = 0.5 + crop_sensitivity * 0.4
        causes.append(
            Cause(
                id="crop_sensitivity",
                labelPl=CAUSE_LABELS["crop_sensitivity"],
                confidence0to1=round(min(0.95, conf), 2),
                evidenceIds=["crop.droughtSensitivity", "moisture.current"],
                rationalePl=(
                    f"Uprawa o wrażliwości {crop_sensitivity:.2f} przy aktualnej "
                    f"ocenie '{assessment.current.level}'."
                ),
            )
        )

    return causes
