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
    timeout_s: float | None = None,
) -> str | None:
    """Call Ollama chat API. Returns content string or None on failure.

    `timeout_s` caps this call (e.g. time left in the /analyze budget); default from settings.
    """
    timeout = settings.ollama_timeout_s if timeout_s is None else timeout_s
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
        async with httpx.AsyncClient(timeout=timeout) as client:
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
