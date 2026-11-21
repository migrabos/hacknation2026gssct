"""FastAPI entrypoint (single app): /health, /crops, /plot/*, /analyze.

Run from apps/api:  uvicorn app.main:app --reload   (or: uvicorn main:app --reload)
"""

from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app import ENGINE_VERSION
from app.config import get_settings
from app.crops.catalog import list_crops
from app.orchestrate import analyze
from app.schemas.evidence import HealthResponse, Report
from app.schemas.requests import AnalyzeRequest
from plot.resolver import InvalidPlotInput, PlotError, PlotNotFound, PlotServiceUnavailable
from plot.router import router as plot_router

app = FastAPI(
    title="Retencja API",
    description="KOWR water retention DSS — live data adapters, deterministic Evidence engine, grounded narrator",
    version=ENGINE_VERSION,
)

_origins = [o.strip() for o in get_settings().cors_origins.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins or ["*"],
    allow_credentials="*" not in _origins,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

app.include_router(plot_router)


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    s = get_settings()
    return HealthResponse(
        status="ok",
        version=s.engine_version,
        adapters=s.adapters,
        llm=s.llm_enabled,
        model=s.ollama_model if s.llm_enabled else None,
    )


@app.get("/crops")
def crops() -> list[dict]:
    return list_crops()


@app.post("/analyze", response_model=Report, response_model_exclude_none=True)
async def analyze_endpoint(req: AnalyzeRequest) -> Report:
    try:
        return await analyze(req)
    except PlotNotFound as exc:
        raise HTTPException(404, detail=str(exc)) from exc
    except (InvalidPlotInput, ValueError) as exc:
        raise HTTPException(422, detail=str(exc)) from exc
    except PlotServiceUnavailable as exc:
        raise HTTPException(503, detail=str(exc)) from exc
    except PlotError as exc:
        raise HTTPException(500, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(503, detail=str(exc)) from exc
