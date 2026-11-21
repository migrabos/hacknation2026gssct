"""Sample report fixture must validate against the API schema.

If this fails, apps/web/lib/types.ts and app/schemas/evidence.py have drifted apart.
"""

from __future__ import annotations

import json
from pathlib import Path

from app.crops.catalog import list_crops
from app.schemas.evidence import Crop, Report

ROOT = Path(__file__).resolve().parents[3]
FIXTURE = ROOT / "fixtures" / "evidence_sample.json"


def test_sample_report_matches_schema() -> None:
    Report.model_validate(json.loads(FIXTURE.read_text(encoding="utf-8")))


def test_crop_catalog_ids_stable() -> None:
    crops = list_crops()
    for c in crops:
        Crop.model_validate(c)
    assert {c["id"] for c in crops} >= {"kukurydza", "ziemniak", "warzywa", "zboza", "rzepak"}
