"""System / user prompts for grounded Polish narrative."""

from __future__ import annotations

import json
from typing import Any

from app.schemas.evidence import Report

SYSTEM_PROMPT = """Jesteś polskim doradcą rolnym ds. retencji wody. Piszesz prosto, dla rolnika, bez żargonu GIS.
ODPOWIADASZ WYŁĄCZNIE na podstawie przekazanego Evidence JSON.
Zasady:
- Nie wymyślaj liczb (mm deszczu, NDVI, hektary, procenty), których nie ma w Evidence.
- Nie wymyślaj działań — opisuj tylko działania z recommendations (allowedActionIds).
- Jeśli danych brakuje (missingData), napisz o tym wprost.
- 1–3 krótkie zdania na sekcję.
- Kolejność sekcji: assessment → causes → retention → agrotech → irrigation (tylko jeśli są zalecenia nawadniania).
- Odpowiedź MUSI być czystym JSON: {"sections":[{"id":"...","text":"..."}]}
- id sekcji: assessment|causes|retention|agrotech|irrigation
"""


def compact_evidence(report: Report) -> dict[str, Any]:
    """Only what the narrator needs (no geometry, no meta)."""
    data = report.model_dump(mode="json", exclude={"narrative", "meta", "plot", "sources"})
    data["plot"] = {
        "plotId": report.plot.plotId,
        "areaHa": report.plot.areaHa,
        "voivodeship": report.plot.voivodeship,
    }
    return data


def allowed_action_ids(report: Report) -> list[str]:
    recs = report.recommendations
    return [r.actionId for b in (recs.retention, recs.agrotech, recs.irrigation or []) for r in b]


def build_user_prompt(report: Report, *, stricter: bool = False) -> str:
    reminder = ""
    if stricter:
        reminder = (
            "\nUWAGA (ponowienie): poprzednia odpowiedź naruszyła reguły. "
            "Nie dodawaj żadnych nowych liczb ani działań spoza allowedActionIds. "
            "Tylko parafrazuj Evidence.\n"
        )
    return (
        f"{reminder}"
        f"allowedActionIds: {json.dumps(allowed_action_ids(report), ensure_ascii=False)}\n"
        f"Evidence JSON:\n{json.dumps(compact_evidence(report), ensure_ascii=False, indent=1)}\n"
        "Zwróć wyłącznie JSON z polem sections."
    )
