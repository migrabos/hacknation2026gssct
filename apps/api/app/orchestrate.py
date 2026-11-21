"""Analyze pipeline: adapters → engine → narrative."""

from __future__ import annotations

import time

from app.adapters.mocks import fetch_all_mocks
from app.crops.catalog import get_crop
from app.engine.run import run_engine
from app.narrative.run import narrate
from app.schemas.evidence import Report
from app.schemas.requests import AnalyzeRequest


async def analyze(req: AnalyzeRequest) -> Report:
    """Full /analyze orchestration."""
    t0 = time.perf_counter()

    # Validate crop early (clear PL error)
    get_crop(req.cropId)

    bundle = await fetch_all_mocks(
        plot_id=req.plotId,
        lat=req.lat,
        lng=req.lng,
        analysis_date=req.analysisDate,
    )

    duration_ms = int((time.perf_counter() - t0) * 1000)
    report = run_engine(
        bundle=bundle,
        crop_id=req.cropId,
        analysis_date=req.analysisDate,
        duration_ms=duration_ms,
    )

    narrative = await narrate(report)
    report.narrative = narrative

    report.meta.durationMs = int((time.perf_counter() - t0) * 1000)
    return report
