"""Irrigation is last and only under strict conditions."""

from __future__ import annotations

from datetime import date

import pytest

from app.engine.run import run_engine
from tests.conftest import dry_bundle

D = date(2025, 7, 20)


@pytest.mark.parametrize("kind", ["river", "stream", "canal", "water", None, "ditch", "drain"])
async def test_ditch_action_requires_mapped_ditch(sample_bundle, kind):
    bundle = dry_bundle(sample_bundle)
    bundle.plot["hydro"] = {"nearbyWater": True, "nearestType": kind, "nearestDistanceM": 42}
    report = run_engine(bundle=bundle, crop_id="kukurydza", analysis_date=D)
    actions = {action.actionId: action for action in report.recommendations.retention}
    assert ("ditch_retention" in actions) == (kind in ("ditch", "drain"))
    if kind in ("ditch", "drain"):
        assert "42 m" in actions["ditch_retention"].why
        assert actions["ditch_retention"].evidenceRefs == ["ev_water"]
    if kind is None:
        assert any("Sprawdź w terenie" in note for note in report.limitations)


async def test_dry_sensitive_crop_gets_irrigation_after_retention(sample_bundle) -> None:
    r = run_engine(bundle=dry_bundle(sample_bundle), crop_id="warzywa", analysis_date=D)
    assert r.moistureAssessment.current.level in ("dry", "very_dry")
    assert r.recommendations.retention
    assert r.recommendations.irrigation and r.recommendations.irrigation[0].actionId == "irrigation_timing"
    assert {c.id for c in r.causes} >= {"precip_deficit", "low_soil_storage", "runoff"}
    assert r.recommendations.retention[0].actionId == "buffer_strips"  # runoff plot → strips first


async def test_tolerant_crop_gets_no_irrigation(sample_bundle) -> None:
    r = run_engine(bundle=dry_bundle(sample_bundle), crop_id="zboza_ozime", analysis_date=D)
    assert not r.recommendations.irrigation
    assert r.recommendations.irrigationNote


async def test_causes_sorted_by_confidence(sample_bundle) -> None:
    r = run_engine(bundle=dry_bundle(sample_bundle), crop_id="kukurydza", analysis_date=D)
    confs = [c.confidence0to1 for c in r.causes]
    assert confs == sorted(confs, reverse=True)
