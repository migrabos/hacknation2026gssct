"""LLM_ENABLED=false → template narrative."""

from __future__ import annotations

from datetime import date

import pytest

from app.adapters.mocks import fetch_all_mocks
from app.config import get_settings
from app.engine.run import run_engine
from app.narrative.run import narrate
from app.orchestrate import analyze
from app.schemas.requests import AnalyzeRequest


@pytest.mark.asyncio
async def test_fallback_no_llm(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_ENABLED", "false")
    get_settings.cache_clear()

    bundle = await fetch_all_mocks(
        plot_id="fallback-plot",
        lat=None,
        lng=None,
        analysis_date=date(2025, 7, 15),
    )
    report = run_engine(bundle=bundle, crop_id="ziemniak", analysis_date=date(2025, 7, 15))
    narrative = await narrate(report)
    assert narrative.mode == "template"
    assert narrative.sections
    assert narrative.sections[0].id == "ocena"

    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_analyze_template_when_llm_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_ENABLED", "false")
    get_settings.cache_clear()

    req = AnalyzeRequest(
        plotId="141201_2.0001.999",
        cropId="rzepak",
        analysisDate=date(2025, 7, 15),
    )
    report = await analyze(req)
    assert report.narrative is not None
    assert report.narrative.mode == "template"
    get_settings.cache_clear()
