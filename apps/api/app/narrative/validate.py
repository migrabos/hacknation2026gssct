"""Validate LLM narrative — reject invented action IDs or numeric literals."""

from __future__ import annotations

import json
import re
from typing import Any

from app.actions.catalog import VALID_ACTION_IDS
from app.narrative.prompt import allowed_action_ids
from app.schemas.evidence import Narrative, NarrativeSection, Report

_SECTION_IDS = ("assessment", "causes", "retention", "agrotech", "irrigation")

# Numbers that look like measurements (decimals with . or , — or ≥ 2 digits)
_NUMBER_RE = re.compile(r"(?<![A-Za-z_/])(-?\d+[.,]\d+|-?\d{2,})(?![A-Za-z_])")


def _norm(lit: str) -> str:
    """'4,20' / '4.2' / '-4.0' → canonical '4.2' / '-4'."""
    s = lit.replace(",", ".").lstrip("+")
    try:
        x = float(s)
    except ValueError:
        return s
    return f"{x:.2f}".rstrip("0").rstrip(".")


def _evidence_number_whitelist(report: Report) -> set[str]:
    blob = json.dumps(report.model_dump(mode="json", exclude={"narrative"}), ensure_ascii=False)
    out = {_norm(m.group(0)) for m in _NUMBER_RE.finditer(blob)}
    # Allow rounded forms of every numeric evidence value (LLM may say "58 mm" for 57.6)
    for e in report.evidence:
        if isinstance(e.value, (int, float)):
            out.add(_norm(str(round(e.value))))
            out.add(_norm(f"{e.value:.1f}"))
    return out


def parse_llm_json(raw: str) -> dict[str, Any] | None:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        start, end = raw.find("{"), raw.rfind("}")
        if start < 0 or end <= start:
            return None
        try:
            data = json.loads(raw[start : end + 1])
        except json.JSONDecodeError:
            return None
    return data if isinstance(data, dict) else None


def _section_refs(report: Report, sid: str) -> list[str]:
    ma, recs = report.moistureAssessment, report.recommendations
    groups = {
        "assessment": [ma.current.evidenceRefs, ma.susceptibility.evidenceRefs],
        "causes": [c.evidenceRefs for c in report.causes],
        "retention": [r.evidenceRefs for r in recs.retention],
        "agrotech": [r.evidenceRefs for r in recs.agrotech],
        "irrigation": [r.evidenceRefs for r in recs.irrigation or []],
    }[sid]
    return list(dict.fromkeys(r for g in groups for r in g))


def validate_narrative_payload(payload: dict[str, Any], report: Report) -> Narrative | None:
    """Return Narrative if valid, else None (caller falls back to template)."""
    sections_raw = payload.get("sections")
    if not isinstance(sections_raw, list) or not sections_raw:
        return None

    allowed = set(allowed_action_ids(report))
    whitelist = _evidence_number_whitelist(report)

    sections: dict[str, NarrativeSection] = {}
    for item in sections_raw:
        if not isinstance(item, dict):
            return None
        sid = str(item.get("id") or "")
        text = str(item.get("text") or "").strip()
        if sid not in _SECTION_IDS or not text:
            return None
        for token in re.findall(r"\b[a-z]+_[a-z_]+\b", text):
            if token in VALID_ACTION_IDS and token not in allowed:
                return None
        for m in _NUMBER_RE.finditer(text):
            if _norm(m.group(0)) not in whitelist:
                return None
        sections[sid] = NarrativeSection(id=sid, text=text, evidenceRefs=_section_refs(report, sid))  # type: ignore[arg-type]

    if "irrigation" in sections and not report.recommendations.irrigation:
        return None

    ordered = [sections[s] for s in _SECTION_IDS if s in sections]
    return Narrative(generatedBy="llm", sections=ordered)
