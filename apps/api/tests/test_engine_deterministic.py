"""Engine determinism + current vs multi-year separation."""

from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

from app.adapters.mocks import MockAdapterBundle, fetch_all_mocks
from app.engine.run import run_engine
from app.schemas.adapters import AdapterResult


@pytest.mark.asyncio
async def test_engine_deterministic() -> None:
    kwargs = dict(
        plot_id="141201_2.0001.123",
        lat=None,
        lng=None,
        analysis_date=date(2025, 7, 15),
    )
    b1 = await fetch_all_mocks(**kwargs)
    b2 = await fetch_all_mocks(**kwargs)
    r1 = run_engine(bundle=b1, crop_id="kukurydza", analysis_date=date(2025, 7, 15))
    r2 = run_engine(bundle=b2, crop_id="kukurydza", analysis_date=date(2025, 7, 15))

    assert r1.moistureAssessment.current.score0to100 == r2.moistureAssessment.current.score0to100
    assert (
        r1.moistureAssessment.multiYearSusceptibility.score0to100
        == r2.moistureAssessment.multiYearSusceptibility.score0to100
    )
    assert r1.moistureAssessment.current.level == r2.moistureAssessment.current.level
    assert [c.id for c in r1.causes] == [c.id for c in r2.causes]
    assert [x.id for x in r1.recommendations.retention] == [
        x.id for x in r2.recommendations.retention
    ]


@pytest.mark.asyncio
async def test_current_vs_multiyear() -> None:
    bundle = await fetch_all_mocks(
        plot_id="demo-plot-A",
        lat=None,
        lng=None,
        analysis_date=date(2025, 6, 1),
    )
    report = run_engine(bundle=bundle, crop_id="warzywa", analysis_date=date(2025, 6, 1))
    cur = report.moistureAssessment.current
    multi = report.moistureAssessment.multiYearSusceptibility

    assert cur.summaryPl != multi.summaryPl
    assert set(cur.evidenceIds) != set(multi.evidenceIds) or cur.score0to100 != multi.score0to100
    assert cur.level in ("ok", "watch", "deficit", "severe")
    assert multi.level in ("low", "moderate", "high")


@pytest.mark.asyncio
async def test_no_recs_without_assessment() -> None:
    empty = AdapterResult(
        values={},
        sources=[],
        fetchedAt=datetime(2025, 7, 15, tzinfo=timezone.utc),
        coverage=None,
        errors=["missing"],
    )
    bundle = MockAdapterBundle(
        plot=empty,
        meteo=empty,
        soil=empty,
        sat=empty,
        drought=empty,
        hydro=empty,
    )
    with pytest.raises(RuntimeError, match="oceny|ocena|meteo|działki"):
        run_engine(bundle=bundle, crop_id="zboza", analysis_date=date(2025, 7, 15))
