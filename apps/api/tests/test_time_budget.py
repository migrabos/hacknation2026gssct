"""/analyze time budget: data adapters share one deadline; the LLM gets what is left."""

from __future__ import annotations

import asyncio
import time
from datetime import date

import pytest

from adapters.base import adapter_deadline, run_adapter
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


# --------------------------------------------------------------------------- data adapters


async def _hang() -> dict:
    await asyncio.sleep(30)
    return {"never": True}


async def test_shared_deadline_cuts_slow_adapters(tmp_path) -> None:
    """Two slow sources in parallel both stop at the shared deadline, not at their own 20 s."""
    t0 = time.perf_counter()
    with adapter_deadline(0.5):
        a, b = await asyncio.gather(
            run_adapter("slow-a", "https://example.org", {"k": 1}, _hang, cache_dir=tmp_path),
            run_adapter("slow-b", "https://example.org", {"k": 2}, _hang, cache_dir=tmp_path),
        )
    assert time.perf_counter() - t0 < 2.0
    for r in (a, b):
        assert r["coverage"] == "none" and "budżecie analizy" in r["errors"][0]


async def test_cache_still_served_after_deadline(tmp_path) -> None:
    async def ok() -> dict:
        return {"x": 1}

    await run_adapter("cached", "https://example.org", {"k": 1}, ok, cache_dir=tmp_path)  # warm
    with adapter_deadline(0.0):  # budget already used up
        r = await run_adapter("cached", "https://example.org", {"k": 1}, _hang, cache_dir=tmp_path)
    assert r["fromCache"] and r["values"] == {"x": 1}


async def test_no_deadline_outside_analyze(tmp_path) -> None:
    async def ok() -> dict:
        return {"x": 1}

    r = await run_adapter("plain", "https://example.org", {"k": 1}, ok, cache_dir=tmp_path)
    assert r["coverage"] == "full"  # /plot/* routes: own per-source timeouts only
