"""Validator rejects invented action IDs / numbers → fallback path."""

from __future__ import annotations

from datetime import date

from app.actions.catalog import VALID_ACTION_IDS
from app.engine.run import run_engine
from app.narrative.prompt import allowed_action_ids
from app.narrative.validate import parse_llm_json, validate_narrative_payload


async def _report(sample_bundle):
    return run_engine(bundle=sample_bundle, crop_id="zboza_ozime", analysis_date=date(2025, 7, 15))


async def test_validator_rejects_invented_action(sample_bundle) -> None:
    report = await _report(sample_bundle)
    not_allowed = sorted(VALID_ACTION_IDS - set(allowed_action_ids(report)))
    assert not_allowed, "sample report recommends every action — pick another fixture"
    payload = {"sections": [{"id": "retention", "text": f"Zalecam {not_allowed[0]}."}]}
    assert validate_narrative_payload(payload, report) is None


async def test_validator_rejects_invented_number(sample_bundle) -> None:
    report = await _report(sample_bundle)
    payload = {"sections": [{"id": "assessment", "text": "Spadło dokładnie 4242,5 mm deszczu."}]}
    assert validate_narrative_payload(payload, report) is None


async def test_validator_accepts_grounded_numbers(sample_bundle) -> None:
    report = await _report(sample_bundle)
    p30 = next(e for e in report.evidence if e.id == "ev_precip_30d").value
    text = f"W ostatnich 30 dniach spadło {str(p30).replace('.', ',')} mm deszczu."
    nar = validate_narrative_payload({"sections": [{"id": "assessment", "text": text}]}, report)
    assert nar is not None and nar.generatedBy == "llm"
    assert nar.sections[0].evidenceRefs


def test_parse_llm_json_extracts_object() -> None:
    data = parse_llm_json('Here you go:\n{"sections":[{"id":"assessment","text":"B"}]}\n')
    assert data is not None and "sections" in data
