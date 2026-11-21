"""Template narrative always fills Polish section prose from Evidence."""

from __future__ import annotations

from datetime import date

from app.engine.run import run_engine
from app.narrative.run import narrate
from app.orchestrate import analyze
from app.schemas.requests import AnalyzeRequest


def test_narrate_sections(sample_bundle) -> None:
    report = run_engine(bundle=sample_bundle, crop_id="ziemniak", analysis_date=date(2025, 7, 15))
    narrative = narrate(report)
    assert narrative.sections[0].id == "assessment"
    assert len(narrative.sections) >= 4


async def test_analyze_includes_narrative() -> None:
    report = await analyze(AnalyzeRequest(plotId="141201_2.0001.123", cropId="ziemniak",
                                          analysisDate=date(2025, 7, 15)))
    assert report.narrative is not None
    assert report.narrative.sections[0].id == "assessment"
