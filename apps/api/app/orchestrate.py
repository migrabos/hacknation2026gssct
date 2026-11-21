"""Analyze pipeline: adapters → engine → narrative."""

from __future__ import annotations

import time

from app.adapters import fetch_bundle
from app.crops.catalog import get_crop
from app.engine.run import run_engine
from app.narrative.run import narrate
from app.schemas.evidence import Report
from app.schemas.requests import AnalyzeRequest


async def analyze(req: AnalyzeRequest) -> Report:
    """Full /analyze orchestration. Raises ValueError (bad input), PlotError, RuntimeError."""
    t0 = time.perf_counter()
    get_crop(req.cropId)  # validate early (clear PL error)

    bundle = await fetch_bundle(
        plot_id=req.plotId,
        lat=req.lat,
        lng=req.lng,
        analysis_date=req.analysisDate,
    )
    report = run_engine(
        bundle=bundle,
        crop_id=req.cropId,
        analysis_date=req.analysisDate,
        duration_ms=int((time.perf_counter() - t0) * 1000),
    )
    report.narrative = await narrate(report)
    if report.meta:
        report.meta.durationMs = int((time.perf_counter() - t0) * 1000)
    return report
