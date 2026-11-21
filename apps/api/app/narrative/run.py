"""Narrate Evidence with Ollama or template fallback."""

from __future__ import annotations

import logging

from app.config import get_settings
from app.narrative.llm_client import ollama_chat
from app.narrative.prompt import SYSTEM_PROMPT, build_user_prompt
from app.narrative.templates_pl import build_template_narrative
from app.narrative.validate import parse_llm_json, validate_narrative_payload
from app.schemas.evidence import Narrative, Report

logger = logging.getLogger(__name__)


async def narrate(report: Report) -> Narrative:
    settings = get_settings()
    if not settings.llm_enabled:
        return build_template_narrative(report)

    user = build_user_prompt(report, stricter=False)
    raw = await ollama_chat(settings=settings, system=SYSTEM_PROMPT, user=user)
    narrative = _try_validate(raw, report)

    if narrative is None and raw is not None:
        # One stricter retry
        user2 = build_user_prompt(report, stricter=True)
        raw2 = await ollama_chat(settings=settings, system=SYSTEM_PROMPT, user=user2)
        narrative = _try_validate(raw2, report)

    if narrative is None:
        logger.info("Falling back to template narrative")
        return build_template_narrative(report)

    return narrative


def _try_validate(raw: str | None, report: Report) -> Narrative | None:
    if not raw:
        return None
    payload = parse_llm_json(raw)
    if not payload:
        return None
    return validate_narrative_payload(payload, report)
