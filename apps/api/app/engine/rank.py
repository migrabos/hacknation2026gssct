"""Rank recommendations: retention → agrotech → irrigation last."""

from __future__ import annotations

from typing import Any

from app.actions.catalog import ACTIONS, get_action
from app.engine.assess import HIGH_SENSITIVITY
from app.schemas.evidence import Cause, MoistureAssessment, Recommendation, Recommendations


def _has_cause(causes: list[Cause], cause_id: str) -> bool:
    return any(c.id == cause_id for c in causes)


def rank_recommendations(
    *,
    assessment: MoistureAssessment,
    causes: list[Cause],
    terrain: dict[str, Any] | None,
    hydro: dict[str, Any] | None,
    crop_sensitivity: float,
) -> Recommendations:
    """Eligibility + ordering. Irrigation only under strict conditions and always last."""
    if assessment is None:
        raise RuntimeError("Nie można rekomendować bez oceny wilgoci.")

    cause_ids = {c.id for c in causes}
    moisture_risk = assessment.current.level in ("watch", "deficit", "severe") or (
        assessment.multiYearSusceptibility.level in ("moderate", "high")
    )

    retention: list[Recommendation] = []
    agrotech: list[Recommendation] = []
    irrigation: list[Recommendation] = []

    if not moisture_risk and not cause_ids:
        return Recommendations(retention=[], agrotech=[], irrigation=[])

    # Always emit some retention + agrotech when any moisture risk
    selected_retention: list[str] = []
    selected_agrotech: list[str] = []

    for action_id, meta in ACTIONS.items():
        if meta["kind"] == "irrigation":
            continue
        triggers = set(meta["triggers"])
        eligible = bool(triggers & cause_ids)
        # Soft eligibility when moisture risk even without exact cause match
        if not eligible and moisture_risk:
            if meta["kind"] == "retention" and (
                "runoff" in cause_ids or (terrain or {}).get("runoffRisk") in ("moderate", "high")
            ):
                eligible = action_id in ("buffer_strips", "ditch_retention", "small_pond")
            if meta["kind"] == "agrotech" and (
                "low_soil_storage" in cause_ids or "precip_deficit" in cause_ids or moisture_risk
            ):
                eligible = action_id in ("residues", "cover_crops", "reduce_tillage")
        if not eligible and moisture_risk:
            # Ensure at least one of each bucket later via defaults
            continue
        if eligible:
            if meta["kind"] == "retention":
                selected_retention.append(action_id)
            else:
                selected_agrotech.append(action_id)

    if moisture_risk:
        if not selected_retention:
            selected_retention = ["small_pond", "buffer_strips"]
        if not selected_agrotech:
            selected_agrotech = ["residues", "cover_crops"]

    # Hydro nearby → prefer ditch_retention
    hydro = hydro or {}
    if hydro.get("nearbyWater") and "ditch_retention" not in selected_retention:
        if "runoff" in cause_ids or moisture_risk:
            selected_retention.append("ditch_retention")

    def _to_rec(action_id: str, priority: int, extra_evidence: list[str]) -> Recommendation:
        a = get_action(action_id)
        ev = list(extra_evidence)
        for t in a["triggers"]:
            if t in cause_ids:
                ev.append(f"cause.{t}")
        return Recommendation(
            id=a["id"],
            titlePl=a["titlePl"],
            whyPl=a["whyTemplatePl"],
            priority=priority,
            evidenceIds=sorted(set(ev)),
            kind=a["kind"],
        )

    # Sort by catalog basePriority
    selected_retention = sorted(
        set(selected_retention), key=lambda i: ACTIONS[i]["basePriority"]
    )
    selected_agrotech = sorted(
        set(selected_agrotech), key=lambda i: ACTIONS[i]["basePriority"]
    )

    for i, aid in enumerate(selected_retention, start=1):
        retention.append(
            _to_rec(
                aid,
                i,
                ["moisture.current", "terrain.slopePct"]
                if aid != "small_pond"
                else ["moisture.current", "meteo.precipMmLast30d"],
            )
        )

    for i, aid in enumerate(selected_agrotech, start=1):
        agrotech.append(_to_rec(aid, i, ["soil.awcMmProxy", "moisture.current"]))

    # Irrigation last: only if current deficit/severe AND high crop sensitivity
    # AND retention already present
    if (
        assessment.current.level in ("deficit", "severe")
        and crop_sensitivity >= HIGH_SENSITIVITY
        and len(retention) > 0
    ):
        irrigation.append(
            _to_rec(
                "irrigation_timing",
                1,
                ["moisture.current", "crop.droughtSensitivity"],
            )
        )

    return Recommendations(
        retention=retention,
        agrotech=agrotech,
        irrigation=irrigation,
    )
