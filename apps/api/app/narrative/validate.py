"""Validate LLM narrative — reject invented action IDs or numeric literals."""

from __future__ import annotations

import json
import re
from typing import Any

from app.actions.catalog import VALID_ACTION_IDS
from app.schemas.evidence import Narrative, NarrativeSection, Report

_SECTION_IDS = frozenset(
    {"ocena", "przyczyny", "retencja", "agrotech", "nawadnianie", "zrodla"}
)

# Numbers that look like measurements (not years / tiny ints used as ranks)
_NUMBER_RE = re.compile(
    r"(?<![A-Za-z_/])(-?\d+\.\d+|-?\d{2,})(?![A-Za-z_])"
)


def _evidence_number_whitelist(report: Report) -> set[str]:
    """All numeric literals that appear in Evidence stringification."""
    blob = json.dumps(report.model_dump(mode="json"), ensure_ascii=False)
    return {m.group(0) for m in _NUMBER_RE.finditer(blob)}


def _allowed_action_ids(report: Report) -> set[str]:
    ids: set[str] = set()
    recs = report.recommendations
    for bucket in (recs.retention, recs.agrotech, recs.irrigation):
        for r in bucket:
            ids.add(r.id)
    return ids


def parse_llm_json(raw: str) -> dict[str, Any] | None:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        # Try to extract first JSON object
        start = raw.find("{")
        end = raw.rfind("}")
        if start < 0 or end <= start:
            return None
        try:
            data = json.loads(raw[start : end + 1])
        except json.JSONDecodeError:
            return None
    if not isinstance(data, dict):
        return None
    return data


def validate_narrative_payload(
    payload: dict[str, Any],
    report: Report,
) -> Narrative | None:
    """Return Narrative if valid, else None."""
    sections_raw = payload.get("sections")
    if not isinstance(sections_raw, list) or not sections_raw:
        return None

    allowed_actions = _allowed_action_ids(report)
    whitelist = _evidence_number_whitelist(report)
    # Always allow scores / small structural numbers already in evidence;
    # also allow common 0-100 ints that appear in report scores.
    for n in (
        report.moistureAssessment.current.score0to100,
        report.moistureAssessment.multiYearSusceptibility.score0to100,
    ):
        whitelist.add(str(n))

    sections: list[NarrativeSection] = []
    for item in sections_raw:
        if not isinstance(item, dict):
            return None
        sid = str(item.get("id") or "")
        title = str(item.get("titlePl") or "").strip()
        body = str(item.get("bodyPl") or "").strip()
        if not sid or not title or not body:
            return None
        if sid not in _SECTION_IDS:
            return None

        # Reject unknown action IDs mentioned as snake_case catalog ids
        for token in re.findall(r"\b[a-z]+_[a-z_]+\b", body):
            if token in VALID_ACTION_IDS and token not in allowed_actions:
                return None

        # Reject numeric literals not present in Evidence
        for m in _NUMBER_RE.finditer(body):
            lit = m.group(0)
            if lit not in whitelist:
                return None

        sections.append(NarrativeSection(id=sid, titlePl=title, bodyPl=body))

    # Irrigation section only if irrigation recs exist
    has_irr_section = any(s.id == "nawadnianie" for s in sections)
    if has_irr_section and not report.recommendations.irrigation:
        return None

    return Narrative(mode="llm", sections=sections)
