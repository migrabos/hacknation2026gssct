"""Polish narrative from structured Evidence (template only)."""

from __future__ import annotations

from app.narrative.templates_pl import build_template_narrative
from app.schemas.evidence import Narrative, Report


def narrate(report: Report) -> Narrative:
    return build_template_narrative(report)
