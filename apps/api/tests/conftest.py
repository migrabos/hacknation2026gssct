"""Shared fixtures — every test runs on deterministic mock adapters, LLM off."""

from __future__ import annotations

from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.adapters.bundle import AdapterBundle
from app.adapters.mocks import fetch_all_mocks
from app.config import get_settings


@pytest.fixture(autouse=True)
def _mock_env(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ADAPTERS", "mock")
    monkeypatch.setenv("LLM_ENABLED", "false")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def client() -> TestClient:
    from app.main import app

    with TestClient(app) as c:
        yield c


@pytest.fixture
async def mock_bundle() -> AdapterBundle:
    return await fetch_all_mocks(plot_id="141201_2.0001.123", lat=None, lng=None, analysis_date=date(2025, 7, 15))


def dry_bundle(bundle: AdapterBundle) -> AdapterBundle:
    """Force a clear drought signal on top of mock data."""
    bundle.meteo["values"].update(
        precip_30d=8.0, precip_30d_median_10y=62.0, kbw_30d=-110.0, kbw_10y_percentile=0.0, dry_spell_days=24,
    )
    bundle.soil["values"].update(sand_pct=72.0, awc_mm=85.0, retention_class="low")
    bundle.plot["terrain"] = {"slopePct": 6.0, "runoffRisk": "high", "resolutionM": 1}
    return bundle
