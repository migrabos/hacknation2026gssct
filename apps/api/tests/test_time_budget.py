"""/analyze time budget: the LLM never runs past the deadline; template fills in."""

from __future__ import annotations

import time
from datetime import date

import pytest

from app.config import get_settings
from app.engine.run import run_engine
from app.narrative import run as narrative_run


@pytest.fixture
def llm_on(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("LLM_ENABLED", "true")
    get_settings.cache_clear()
    calls: list[float | None] = []

    async def fake_chat(*, settings, system, user, timeout_s=None):  # noqa: ARG001
        calls.append(timeout_s)
        return '{"sections": []}'  # invalid on purpose → would trigger the stricter retry

    monkeypatch.setattr(narrative_run, "ollama_chat", fake_chat)
    yield calls
    get_settings.cache_clear()


async def test_no_llm_call_when_budget_used_up(sample_bundle, llm_on) -> None:
    report = run_engine(bundle=sample_bundle, crop_id="ziemniak", analysis_date=date(2025, 7, 15))
    narrative = await narrative_run.narrate(report, deadline=time.perf_counter() + 1.0)
    assert narrative.generatedBy == "template"
    assert llm_on == []  # < llm_min_time_s left → LLM not even called


async def test_no_retry_when_little_time_left(sample_bundle, llm_on) -> None:
    report = run_engine(bundle=sample_bundle, crop_id="ziemniak", analysis_date=date(2025, 7, 15))
    narrative = await narrative_run.narrate(report, deadline=time.perf_counter() + 6.0)
    assert narrative.generatedBy == "template"
    assert len(llm_on) == 1  # first call only, stricter retry skipped
    assert llm_on[0] is not None and llm_on[0] <= 6.0  # call capped by time left


async def test_retry_when_enough_time(sample_bundle, llm_on) -> None:
    report = run_engine(bundle=sample_bundle, crop_id="ziemniak", analysis_date=date(2025, 7, 15))
    await narrative_run.narrate(report, deadline=time.perf_counter() + 60.0)
    assert len(llm_on) == 2  # first call + stricter retry
    assert all(t is not None and t <= get_settings().ollama_timeout_s for t in llm_on)
