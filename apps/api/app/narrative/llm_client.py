"""httpx client for Ollama /api/chat."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.config import Settings

logger = logging.getLogger(__name__)


async def ollama_chat(
    *,
    settings: Settings,
    system: str,
    user: str,
) -> str | None:
    """Call Ollama chat API. Returns content string or None on failure."""
    url = f"{settings.ollama_base_url.rstrip('/')}/api/chat"
    payload: dict[str, Any] = {
        "model": settings.ollama_model,
        "stream": False,
        "format": "json",
        "options": {
            "temperature": settings.ollama_temperature,
            "num_predict": settings.ollama_max_tokens,
        },
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }
    try:
        async with httpx.AsyncClient(timeout=settings.ollama_timeout_s) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()
            content = (data.get("message") or {}).get("content")
            if not content:
                logger.warning("Ollama returned empty content")
                return None
            return str(content)
    except Exception as exc:  # noqa: BLE001 — soft-fail to template
        logger.warning("Ollama chat failed: %s", exc)
        return None
