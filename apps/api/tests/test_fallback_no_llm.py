"""LLM_ENABLED=false → template narrative."""

from __future__ import annotations

from datetime import date

from app.engine.run import run_engine
from app.narrative.run import narrate
from app.orchestrate import analyze
from app.schemas.requests import AnalyzeRequest


async def test_fallback_no_llm(sample_bundle) -> None:
    report = run_engine(bundle=sample_bundle, crop_id="ziemniak", analysis_date=date(2025, 7, 15))
    narrative = await narrate(report)
    assert narrative.generatedBy == "template"
    assert narrative.sections[0].id == "assessment"


async def test_analyze_template_when_llm_off() -> None:
    req = AnalyzeRequest(plotId="141201_2.0001.999", cropId="rzepak", analysisDate=date(2025, 7, 15))
    report = await analyze(req)
    assert report.narrative is not None and report.narrative.generatedBy == "template"
