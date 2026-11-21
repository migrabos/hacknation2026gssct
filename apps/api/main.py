"""FastAPI entrypoint. Run from apps/api:  uvicorn main:app --reload"""

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from plot.router import router as plot_router

app = FastAPI(title="Retencja API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in os.environ.get("CORS_ORIGINS", "*").split(",")],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

app.include_router(plot_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
