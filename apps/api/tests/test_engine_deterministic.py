"""Engine determinism + current vs multi-year separation + honest failure."""

from __future__ import annotations

from datetime import date

import pytest

from app.adapters.mocks import fetch_all_mocks
from app.engine.run import run_engine

D = date(2025, 7, 15)


def _strip(r):
    return r.model_dump(exclude={"generatedAt", "meta"})


async def test_engine_deterministic() -> None:
    kw = dict(plot_id="141201_2.0001.123", lat=None, lng=None, analysis_date=D)
    r1 = run_engine(bundle=await fetch_all_mocks(**kw), crop_id="kukurydza", analysis_date=D)
    r2 = run_engine(bundle=await fetch_all_mocks(**kw), crop_id="kukurydza", analysis_date=D)
    assert _strip(r1) == _strip(r2)


async def test_current_vs_multiyear() -> None:
    b = await fetch_all_mocks(plot_id="demo-plot-A", lat=None, lng=None, analysis_date=date(2025, 6, 1))
    r = run_engine(bundle=b, crop_id="warzywa", analysis_date=date(2025, 6, 1))
    cur, sus = r.moistureAssessment.current, r.moistureAssessment.susceptibility
    assert cur.summary != sus.summary
    assert set(cur.evidenceRefs) != set(sus.evidenceRefs)


async def test_no_report_without_meteo(mock_bundle) -> None:
    mock_bundle.meteo = {"values": {}, "sources": [], "fetchedAt": "", "coverage": "none", "errors": ["x"]}
    with pytest.raises(RuntimeError, match="meteo"):
        run_engine(bundle=mock_bundle, crop_id="zboza", analysis_date=D)


async def test_failed_source_is_reported(mock_bundle) -> None:
    mock_bundle.soil = {"values": {}, "sources": [{"name": "ISRIC SoilGrids 2.0", "url": "u", "fetchedAt": "t"}],
                        "fetchedAt": "t", "coverage": "none", "errors": ["Przekroczono limit czasu (20 s)"]}
    r = run_engine(bundle=mock_bundle, crop_id="zboza", analysis_date=D)
    assert r.status == "partial"
    soil = next(s for s in r.sources if s.id == "soilgrids")
    assert soil.status == "failed" and "limit czasu" in (soil.error or "")
    assert any(m.id == "missing_soilgrids" for m in r.missingData)
    assert not any(e.sourceId == "soilgrids" for e in r.evidence)  # nothing invented
