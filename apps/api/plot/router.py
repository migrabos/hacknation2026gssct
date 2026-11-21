"""FastAPI routes for plot lookup: /plot/by-id, /plot/by-point, /plot/{id}.

Responses use the `Plot` shape from apps/web/lib/types.ts (centroid = [lng, lat]).
By default only ULDK is queried (fast map pick); `?context=true` adds terrain + hydro.
/analyze always computes terrain + hydro itself.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.config import get_settings
from app.plot_dto import plot_to_dto

from .resolver import (
    InvalidPlotInput,
    PlotError,
    PlotNotFound,
    PlotServiceUnavailable,
    resolve_plot,
    resolve_point,
    resolve_region_parcel,
    search_regions,
)

router = APIRouter(prefix="/plot", tags=["plot"])


def _mock(plot_id: str | None = None, lat: float | None = None, lng: float | None = None) -> dict[str, Any] | None:
    if get_settings().adapters != "mock":
        return None
    from app.adapters.mocks import mock_plot

    return plot_to_dto(mock_plot(plot_id, lat, lng)).model_dump(exclude_none=True)


async def _guard(coro) -> dict[str, Any]:
    try:
        return plot_to_dto(await coro).model_dump(exclude_none=True)
    except PlotNotFound as exc:
        raise HTTPException(404, detail=str(exc) or "Nie znaleziono działki ewidencyjnej") from exc
    except InvalidPlotInput as exc:
        raise HTTPException(422, detail=str(exc)) from exc
    except PlotServiceUnavailable as exc:
        raise HTTPException(503, detail=str(exc)) from exc
    except PlotError as exc:
        raise HTTPException(500, detail=str(exc)) from exc


@router.get("/by-id")
async def plot_by_id(
    id: str = Query(..., description="Identyfikator działki, np. 040308_5.0004.17220"),
    context: bool = Query(False, description="Dołącz spadek terenu i wody w pobliżu (wolniej)"),
):
    return _mock(plot_id=id.strip()) or await _guard(resolve_plot(id, with_context=context))


@router.get("/by-point")
async def plot_by_point(
    lat: float = Query(..., ge=-90, le=90, description="Szerokość geograficzna (WGS84)"),
    lng: float = Query(..., ge=-180, le=180, description="Długość geograficzna (WGS84)"),
    context: bool = Query(False, description="Dołącz spadek terenu i wody w pobliżu (wolniej)"),
):
    return _mock(lat=lat, lng=lng) or await _guard(resolve_point(lat, lng, with_context=context))


@router.get("/regions")
async def plot_regions(q: str = Query(..., description="Pełna nazwa miejscowości / obrębu, np. Krzewina")):
    """Cadastral precincts (obręby) with this name, with commune/county/voivodeship + bbox."""
    if get_settings().adapters == "mock":
        from app.adapters.mocks import mock_plot

        p = mock_plot(None, None, None)
        rid = ".".join(str(p.get("plotId", "000000_0.0000.0")).split(".")[:2])
        return [{"regionId": rid, "region": q.strip(), "commune": p.get("commune"), "county": p.get("county"),
                 "voivodeship": p.get("voivodeship"), "bbox": p.get("bbox")}]
    try:
        return await search_regions(q)
    except InvalidPlotInput as exc:
        raise HTTPException(422, detail=str(exc)) from exc
    except PlotServiceUnavailable as exc:
        raise HTTPException(503, detail=str(exc)) from exc


@router.get("/by-region")
async def plot_by_region(
    regionId: str = Query(..., description="Identyfikator obrębu, np. 022503_5.0003"),
    nr: str = Query(..., description="Numer działki w obrębie, np. 134 lub 134/2"),
    context: bool = Query(False),
):
    if get_settings().adapters == "mock":
        return _mock(plot_id=f"{regionId.strip()}.{nr.strip()}")
    return await _guard(resolve_region_parcel(regionId, nr, with_context=context))


# Must stay last: `:path` also matches "by-id" / "by-point" and IDs containing "/" (e.g. 123/4).
@router.get("/{plot_id:path}")
async def plot_by_path(plot_id: str, context: bool = Query(False)):
    return _mock(plot_id=plot_id) or await _guard(resolve_plot(plot_id, with_context=context))
