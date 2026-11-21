"""Adapter result envelopes shared with Person 2."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class AdapterResult(BaseModel):
    """Envelope returned by every data adapter (mock or live)."""

    values: dict[str, Any] = Field(default_factory=dict)
    sources: list[dict[str, Any]] = Field(default_factory=list)
    fetchedAt: datetime
    coverage: str | None = None
    errors: list[str] = Field(default_factory=list)
