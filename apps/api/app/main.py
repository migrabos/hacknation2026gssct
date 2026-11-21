"""FastAPI entrypoint: /health, /crops, /analyze."""

from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app import ENGINE_VERSION
from app.config import get_settings
from app.crops.catalog import list_crops
from app.orchestrate import analyze
from app.schemas.evidence import Report
from app.schemas.requests import AnalyzeRequest

app = FastAPI(
    title="Retencja API",
    description="KOWR water retention decision support — Evidence engine + grounded narrator",
    version=ENGINE_VERSION,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict:
    settings = get_settings()
    return {
        "status": "ok",
        "llm": settings.llm_enabled,
        "model": settings.ollama_model if settings.llm_enabled else None,
        "engineVersion": settings.engine_version,
    }


@app.get("/crops")
def crops() -> list[dict]:
    return list_crops()


@app.post("/analyze", response_model=Report)
async def analyze_endpoint(req: AnalyzeRequest) -> Report:
    try:
        return await analyze(req)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
