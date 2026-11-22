"""Live adapters: ULDK plot → (terrain+hydro ‖ meteo ‖ soil ‖ Sentinel-2 now + previous years ‖ EDO ‖ IUNG soil
category) in parallel.

Raises plot.resolver.PlotError subclasses when the plot itself cannot be resolved
(no plot = no report). Every other source fails soft inside `run_adapter`.
"""

from __future__ import annotations

import asyncio
import contextvars
from datetime import date
from typing import Any

from adapters.drought_edo import fetch_drought_context
from adapters.iung_soil import fetch_iung_soil_category
from adapters.open_meteo import fetch_meteo
from adapters.sentinel_stac import fetch_sentinel, fetch_sentinel_history
from adapters.soilgrids import fetch_soil
from app.adapters.bundle import AdapterBundle
from plot.resolver import add_plot_context, resolve_plot, resolve_point, to_2180


# The multi-year satellite baseline is a bonus, never worth a slow report: it runs as a
# background task (outside the request deadline) and fills the disk cache. The report
# waits only briefly — enough for cached years — and otherwise goes out without it.
HISTORY_WAIT_SEC = 3.0
_history_tasks: dict[tuple, asyncio.Task] = {}


async def history_or_pending(bbox: list[float], d: str, geometry: dict[str, Any]) -> dict[str, Any]:
    key = (tuple(round(float(v), 4) for v in bbox), d)
    task = _history_tasks.get(key)
    if task is None:
        # Fresh context = no shared adapter deadline, so the background fetch is not cut short.
        task = asyncio.get_running_loop().create_task(
            fetch_sentinel_history(bbox, d, geometry), context=contextvars.Context())
        _history_tasks[key] = task
        task.add_done_callback(lambda _t: _history_tasks.pop(key, None))
    done, _ = await asyncio.wait({task}, timeout=HISTORY_WAIT_SEC)
    if done:
        return task.result()
    return {"values": {}, "sources": [], "fetchedAt": "", "coverage": "none", "fromCache": False,
            "errors": ["Zdjęcia z poprzednich lat są jeszcze pobierane – porównanie pojawi się przy "
                       "kolejnym raporcie dla tej działki."]}


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

    async def satellite() -> tuple[dict, dict]:
        # Current scene first: run side by side with the history they compete for bandwidth
        # and the current scene (the one that matters) could time out.
        now = await fetch_sentinel(base["bbox"], d, base["geometry"])
        return now, await history_or_pending(base["bbox"], d, base["geometry"])

    plot, meteo, soil, (sat, sat_history), drought, iung_soil = await asyncio.gather(
        add_plot_context(base),
        fetch_meteo(base["centroid"], d),
        fetch_soil(base["centroid"]),
        satellite(),
        fetch_drought_context(base["centroid"], d),
        fetch_iung_soil_category(base["plotId"], to_2180(base["geometry"])),
    )
    return AdapterBundle(plot=plot, meteo=meteo, soil=soil, sat=sat, drought=drought, mode="live",
                         sat_history=sat_history, iung_soil=iung_soil)
