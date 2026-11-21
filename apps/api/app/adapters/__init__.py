"""Data adapters for the engine: live (Person 1+2 adapters) or deterministic mocks."""

from __future__ import annotations

from datetime import date

from app.adapters.bundle import AdapterBundle


async def fetch_bundle(
    *,
    plot_id: str | None,
    lat: float | None,
    lng: float | None,
    analysis_date: date,
) -> AdapterBundle:
    """Pick live or mock adapters based on ADAPTERS env (default: live)."""
    from app.config import get_settings

    kwargs = dict(plot_id=plot_id, lat=lat, lng=lng, analysis_date=analysis_date)
    if get_settings().adapters == "mock":
        from app.adapters.mocks import fetch_all_mocks

        return await fetch_all_mocks(**kwargs)
    from app.adapters.live import fetch_live

    return await fetch_live(**kwargs)


__all__ = ["AdapterBundle", "fetch_bundle"]
