"""The web's sample report (apps/web/mocks/report.json) must validate against the API schema.

If this fails, apps/web/lib/types.ts and app/schemas/evidence.py have drifted apart.
"""

from __future__ import annotations

import json
from pathlib import Path

from app.schemas.evidence import Crop, Plot, Report

WEB = Path(__file__).resolve().parents[2] / "web"


def test_web_mock_report_matches_schema() -> None:
    Report.model_validate(json.loads((WEB / "mocks" / "report.json").read_text(encoding="utf-8")))


def test_web_mock_plot_matches_schema() -> None:
    Plot.model_validate(json.loads((WEB / "mocks" / "plot.json").read_text(encoding="utf-8")))


def test_web_mock_crops_match_api_catalog() -> None:
    from app.crops.catalog import list_crops

    web = json.loads((WEB / "mocks" / "crops.json").read_text(encoding="utf-8"))
    for c in web:
        Crop.model_validate(c)
    assert [c["id"] for c in web] == [c["id"] for c in list_crops()]
