"""Data adapters for the engine — live public sources only."""

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
    from app.adapters.live import fetch_live

    return await fetch_live(
        plot_id=plot_id,
        lat=lat,
        lng=lng,
        analysis_date=analysis_date,
    )


__all__ = ["AdapterBundle", "fetch_bundle"]
