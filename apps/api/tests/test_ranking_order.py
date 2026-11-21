"""Irrigation never precedes retention when both present."""

from __future__ import annotations

from datetime import date

import pytest

from app.adapters.mocks import fetch_all_mocks
from app.engine.rank import rank_recommendations
from app.engine.run import run_engine
from app.schemas.evidence import Cause, MoistureAssessment, SituationBlock, SusceptibilityBlock


def _forced_deficit_assessment() -> MoistureAssessment:
    return MoistureAssessment(
        current=SituationBlock(
            level="deficit",
            score0to100=30,
            summaryPl="niedobór",
            evidenceIds=["moisture.current"],
        ),
        multiYearSusceptibility=SusceptibilityBlock(
            level="moderate",
            score0to100=55,
            peakMonths=[7],
            summaryPl="umiarkowana",
            evidenceIds=["meteo.precipAnomalyPct10y"],
        ),
        confidence0to1=0.7,
        uncertaintyNotes=[],
    )


def test_ranking_order() -> None:
    assessment = _forced_deficit_assessment()
    causes = [
        Cause(
            id="precip_deficit",
            labelPl="Niedobór opadów",
            confidence0to1=0.8,
            evidenceIds=["meteo.precipMmLast30d"],
            rationalePl="test",
        ),
        Cause(
            id="crop_sensitivity",
            labelPl="Wrażliwość",
            confidence0to1=0.8,
            evidenceIds=["crop.droughtSensitivity"],
            rationalePl="test",
        ),
        Cause(
            id="runoff",
            labelPl="Spływ",
            confidence0to1=0.6,
            evidenceIds=["terrain.runoffRisk"],
            rationalePl="test",
        ),
    ]
    recs = rank_recommendations(
        assessment=assessment,
        causes=causes,
        terrain={"slopePct": 6.0, "runoffRisk": "high"},
        hydro={"nearbyWater": True, "distanceClass": "near"},
        crop_sensitivity=0.85,
    )
    assert recs.retention, "expected retention recommendations"
    assert recs.irrigation, "expected irrigation under deficit + high sensitivity"
    # Structural order: retention bucket before irrigation bucket
    ordered_ids = (
        [r.id for r in recs.retention]
        + [r.id for r in recs.agrotech]
        + [r.id for r in recs.irrigation]
    )
    irr_idx = ordered_ids.index("irrigation_timing")
    first_ret_idx = min(ordered_ids.index(r.id) for r in recs.retention)
    assert first_ret_idx < irr_idx
    assert ordered_ids[-1] == "irrigation_timing" or "irrigation_timing" in ordered_ids[len(recs.retention) + len(recs.agrotech) :]


@pytest.mark.asyncio
async def test_ranking_order_from_engine() -> None:
    """End-to-end: when irrigation appears, retention is non-empty and listed first in report."""
    # High-sensitivity crop tends to unlock irrigation under deficit mocks
    bundle = await fetch_all_mocks(
        plot_id="irr-order-plot",
        lat=None,
        lng=None,
        analysis_date=date(2025, 7, 20),
    )
    # Force dry meteo for irrigation path
    bundle.meteo.values["precipMmLast30d"] = 10.0
    bundle.meteo.values["precipMmClimate30d"] = 60.0
    bundle.meteo.values["drySpellDays"] = 18
    report = run_engine(bundle=bundle, crop_id="warzywa", analysis_date=date(2025, 7, 20))
    if report.recommendations.irrigation:
        assert report.recommendations.retention
        assert report.recommendations.irrigation[0].id == "irrigation_timing"
