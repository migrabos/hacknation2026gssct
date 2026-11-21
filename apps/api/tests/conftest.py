"""Shared fixtures — offline sample bundles, no network."""

from __future__ import annotations

from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.adapters.bundle import AdapterBundle
from app.config import get_settings
from tests.fixtures.sample_bundle import make_sample_bundle, sample_plot


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture(autouse=True)
def _offline_data(monkeypatch: pytest.MonkeyPatch):
    """Keep HTTP + engine tests offline by substituting live fetches with fixtures."""

    async def fake_fetch_bundle(**kwargs):
        return make_sample_bundle(**kwargs)

    async def fake_resolve_plot(plot_id: str, with_context: bool = False):
        return sample_plot(plot_id, None, None)

    async def fake_resolve_point(lat: float, lng: float, with_context: bool = False):
        return sample_plot(None, lat, lng)

    async def fake_resolve_region(region_id: str, nr: str, with_context: bool = False):
        return sample_plot(f"{region_id.strip()}.{nr.strip()}", None, None)

    async def fake_region_extent(region_id: str):
        return sample_plot(None, None, None).get("bbox")

    monkeypatch.setattr("app.orchestrate.fetch_bundle", fake_fetch_bundle)
    monkeypatch.setattr("plot.router.resolve_plot", fake_resolve_plot)
    monkeypatch.setattr("plot.router.resolve_point", fake_resolve_point)
    monkeypatch.setattr("plot.router.resolve_region_parcel", fake_resolve_region)
    monkeypatch.setattr("plot.router.region_extent", fake_region_extent)


@pytest.fixture
def client() -> TestClient:
    from app.main import app

    with TestClient(app) as c:
        yield c


@pytest.fixture
def sample_bundle() -> AdapterBundle:
    return make_sample_bundle(
        plot_id="141201_2.0001.123",
        lat=None,
        lng=None,
        analysis_date=date(2025, 7, 15),
    )


def dry_bundle(bundle: AdapterBundle) -> AdapterBundle:
    """Force a clear drought signal on top of sample data."""
    bundle.meteo["values"].update(
        precip_30d=8.0, precip_30d_median_10y=62.0, kbw_30d=-110.0, kbw_10y_percentile=0.0, dry_spell_days=24,
    )
    bundle.soil["values"].update(sand_pct=72.0, awc_mm=85.0, retention_class="low")
    bundle.plot["terrain"] = {"slopePct": 6.0, "runoffRisk": "high", "resolutionM": 1}
    return bundle
