"""FastAPI routes for plot lookup: /plot/by-id, /plot/by-point, /plot/{id}."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from .resolver import (
    InvalidPlotInput,
    PlotError,
    PlotNotFound,
    PlotServiceUnavailable,
    resolve_plot,
    resolve_point,
)

router = APIRouter(prefix="/plot", tags=["plot"])


async def _guard(coro) -> dict[str, Any]:
    try:
        return await coro
    except PlotNotFound as exc:
        raise HTTPException(404, detail=str(exc) or "Nie znaleziono działki ewidencyjnej") from exc
    except InvalidPlotInput as exc:
        raise HTTPException(422, detail=str(exc)) from exc
    except PlotServiceUnavailable as exc:
        raise HTTPException(503, detail=str(exc)) from exc
    except PlotError as exc:
        raise HTTPException(500, detail=str(exc)) from exc


@router.get("/by-id")
async def plot_by_id(id: str = Query(..., description="Identyfikator działki, np. 040308_5.0004.17220")):
    return await _guard(resolve_plot(id))


@router.get("/by-point")
async def plot_by_point(
    lat: float = Query(..., ge=-90, le=90, description="Szerokość geograficzna (WGS84)"),
    lng: float = Query(..., ge=-180, le=180, description="Długość geograficzna (WGS84)"),
):
    return await _guard(resolve_point(lat, lng))


# Must stay last: `:path` also matches "by-id" / "by-point" and IDs containing "/" (e.g. 123/4).
@router.get("/{plot_id:path}")
async def plot_by_path(plot_id: str):
    return await _guard(resolve_plot(plot_id))
