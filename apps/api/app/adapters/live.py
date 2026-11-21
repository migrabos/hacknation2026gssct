"""Live adapters: ULDK plot → (terrain+hydro ‖ meteo ‖ soil ‖ Sentinel-2 ‖ EDO) in parallel.

Raises plot.resolver.PlotError subclasses when the plot itself cannot be resolved
(no plot = no report). Every other source fails soft inside `run_adapter`.
"""

from __future__ import annotations

import asyncio
from datetime import date

from adapters.drought_edo import fetch_drought_context
from adapters.open_meteo import fetch_meteo
from adapters.sentinel_stac import fetch_sentinel
from adapters.soilgrids import fetch_soil
from app.adapters.bundle import AdapterBundle
from plot.resolver import add_plot_context, resolve_plot, resolve_point


async def fetch_live(
    *,
    plot_id: str | None,
    lat: float | None,
    lng: float | None,
    analysis_date: date,
) -> AdapterBundle:
    if plot_id:
        base = await resolve_plot(plot_id, with_context=False)
    else:
        base = await resolve_point(float(lat), float(lng), with_context=False)  # type: ignore[arg-type]

    d = analysis_date.isoformat()
    plot, meteo, soil, sat, drought = await asyncio.gather(
        add_plot_context(base),
        fetch_meteo(base["centroid"], d),
        fetch_soil(base["centroid"]),
        fetch_sentinel(base["bbox"], d, base["geometry"]),
        fetch_drought_context(base["centroid"], d),
    )
    return AdapterBundle(plot=plot, meteo=meteo, soil=soil, sat=sat, drought=drought, mode="live")
