"""Compat entrypoint. Run from apps/api:  uvicorn main:app --reload

The single FastAPI app lives in app/main.py (plot router + /crops + /analyze).
"""

from app.main import app

__all__ = ["app"]
