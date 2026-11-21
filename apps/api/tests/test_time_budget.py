"""Data adapters share one /analyze deadline."""

from __future__ import annotations

import asyncio
import time

from adapters.base import adapter_deadline, run_adapter


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
