"""Shared fixtures for API / engine tests."""

from __future__ import annotations

from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.adapters.mocks import MockAdapterBundle, fetch_all_mocks
from app.main import app


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("LLM_ENABLED", "false")
    from app.config import get_settings

    get_settings.cache_clear()
    with TestClient(app) as c:
        yield c
    get_settings.cache_clear()


@pytest.fixture
async def mock_bundle() -> MockAdapterBundle:
    return await fetch_all_mocks(
        plot_id="141201_2.0001.123",
        lat=None,
        lng=None,
        analysis_date=date(2025, 7, 15),
    )
