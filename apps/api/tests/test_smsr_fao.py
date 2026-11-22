"""FAO Ky mapping + IUNG SMSR threshold lookup — deterministic, no network."""

from __future__ import annotations

from datetime import date

from app.crops.catalog import CROPS, get_crop, list_crops, sensitivity_level
from app.crops.fao import FAO_KY, ky_to_sensitivity
from app.crops.smsr import (
    _THRESHOLDS,
    evaluate_smsr,
    lookup_threshold,
    pick_period_index,
    soil_category_from_awc,
)
from app.engine.run import run_engine


def test_catalog_matches_smsr_rows_exactly() -> None:
    assert set(CROPS) == set(_THRESHOLDS)
    assert len(list_crops()) == 14


def test_fao_ky_maize_is_high() -> None:
    assert FAO_KY["kukurydza_ziarno"] == 1.25
    sens = ky_to_sensitivity(1.25)
    assert sens >= 0.65
    assert sensitivity_level(sens) == "high"
    assert get_crop("kukurydza_ziarno")["droughtSensitivity"] == sens
    assert get_crop("kukurydza")["id"] == "kukurydza_ziarno"  # legacy alias


def test_fao_ky_winter_cereals_below_spring() -> None:
    assert ky_to_sensitivity(FAO_KY["zboza_ozime"]) < ky_to_sensitivity(FAO_KY["zboza_jare"])


def test_smsr_soil_categories() -> None:
    assert soil_category_from_awc(100.0) == 1
    assert soil_category_from_awc(140.0) == 2
    assert soil_category_from_awc(180.0) == 3
    assert soil_category_from_awc(220.0) == 4
    assert soil_category_from_awc(None) is None


def test_smsr_period_mid_july() -> None:
    idx = pick_period_index(date(2025, 7, 15))
    assert idx in (5, 6)
    assert pick_period_index(date(2025, 1, 10)) is None


def test_smsr_maize_threshold_soil_i() -> None:
    assert lookup_threshold("kukurydza_ziarno", 1, 6) == -153
    assert lookup_threshold("kukurydza_kiszonka", 1, 6) == -153
    assert lookup_threshold("kukurydza_kiszonka", 1, 7) == -152


def test_smsr_evaluate_below_threshold() -> None:
    m = evaluate_smsr(
        crop_id="kukurydza_ziarno",
        analysis_date=date(2025, 7, 15),
        kbw_60d=-180.0,
        awc_mm=100.0,
    )
    assert m is not None
    assert m.below_threshold is True
    assert m.crop_row == "kukurydza_ziarno"


def test_smsr_evaluate_above_threshold() -> None:
    m = evaluate_smsr(
        crop_id="kukurydza_ziarno",
        analysis_date=date(2025, 7, 15),
        kbw_60d=-50.0,
        awc_mm=100.0,
    )
    assert m is not None
    assert m.below_threshold is False


def test_smsr_names_match_regulation() -> None:
    names = {c["namePl"] for c in CROPS.values()}
    assert names == {
        "Zboża ozime", "Zboża jare", "Kukurydza na ziarno", "Kukurydza na kiszonkę",
        "Rzepak i rzepik", "Ziemniak", "Burak cukrowy", "Chmiel", "Tytoń",
        "Warzywa gruntowe", "Krzewy owocowe", "Drzewa owocowe", "Truskawki", "Rośliny strączkowe",
    }


def test_analyze_exposes_fao_and_smsr_evidence(sample_bundle) -> None:
    sample_bundle.soil["values"]["awc_mm"] = 100.0
    sample_bundle.meteo["values"]["kbw_60d"] = -200.0
    report = run_engine(bundle=sample_bundle, crop_id="kukurydza_ziarno", analysis_date=date(2025, 7, 15))
    ev = {e.id: e for e in report.evidence}
    assert "ev_fao_ky" in ev
    assert ev["ev_fao_ky"].value == 1.25
    assert "ev_smsr_threshold" in ev
    assert "ev_kbw_60d" in ev
    src = {s.id for s in report.sources}
    assert {"fao_ky", "smsr_kbw"} <= src
