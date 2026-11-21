"""System / user prompts for grounded Polish narrative."""

from __future__ import annotations

import json
from typing import Any

from app.schemas.evidence import Report

SYSTEM_PROMPT = """Jesteś polskim doradcą rolnym ds. retencji wody.
ODPOWIADASZ WYŁĄCZNIE na podstawie przekazanego Evidence JSON.
Zasady:
- Nie wymyślaj liczb (mm deszczu, NDVI, hektary, score) których nie ma w Evidence.
- Nie wymyślaj ID działań — używaj tylko ID z recommendations.
- Po każdym zdaniu z faktem dodaj znacznik [evidence_id] jeśli to możliwe.
- Jeśli danych brakuje, napisz o tym wprost.
- Kolejność sekcji: ocena → przyczyny → retencja → agrotech → nawadnianie (tylko jeśli jest) → źródła/braki.
- Odpowiedź MUSI być czystym JSON: {"sections":[{"id":"...","titlePl":"...","bodyPl":"..."}]}
- id sekcji: ocena|przyczyny|retencja|agrotech|nawadnianie|zrodla
"""


def compact_evidence(report: Report) -> dict[str, Any]:
    """Strip huge geometry polygons for the LLM context."""
    data = report.model_dump(mode="json")
    data.pop("narrative", None)
    plot = data.get("plot") or {}
    if plot.get("geometry"):
        plot["geometry"] = {"type": "omitted", "note": "polygon stripped for LLM"}
    data["plot"] = plot
    return data


def build_user_prompt(report: Report, *, stricter: bool = False) -> str:
    evidence = compact_evidence(report)
    allowed_actions = []
    recs = report.recommendations
    for bucket in (recs.retention, recs.agrotech, recs.irrigation):
        for r in bucket:
            allowed_actions.append(r.id)

    reminder = ""
    if stricter:
        reminder = (
            "\nUWAGA (ponowienie): poprzednia odpowiedź naruszyła reguły. "
            "Nie dodawaj żadnych nowych liczb ani ID działań poza listą allowedActionIds. "
            "Tylko parafrazuj Evidence.\n"
        )

    return (
        f"{reminder}"
        f"allowedActionIds: {json.dumps(allowed_actions, ensure_ascii=False)}\n"
        f"Evidence JSON:\n{json.dumps(evidence, ensure_ascii=False, indent=2)}\n"
        "Zwróć wyłącznie JSON z polem sections."
    )
