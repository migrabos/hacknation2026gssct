"""Soil moisture (ERA5-Land), IUNG soil category, SMSR 10-year risk window, SCS-CN runoff — offline."""

from __future__ import annotations

from collections import Counter
from datetime import date, timedelta

import numpy as np

from adapters.iung_soil import LEGEND, classify_pixels, summarize
from adapters.open_meteo import (
    SMSR_WINDOWS,
    compute_metrics,
    monthly_kbw_climatology,
    smsr_window_kbw,
    soil_moisture_metrics,
)
from app.crops.smsr import PERIODS, crop_not_indicated, evaluate_smsr, lookup_threshold, smsr_history
from app.engine.facts import Facts
from app.engine.risk_window import compute_risk_window
from app.engine.run import run_engine
from app.engine.runoff import CN_TABLE, estimate_runoff, hydrologic_group, scs_runoff_mm

D = date(2025, 7, 15)


def _series(p: float = 1.0, e: float = 3.0, start: date = date(2013, 1, 1), end: date = D) -> dict:
    out, d = {}, start
    while d <= end:
        out[d] = [p, e, 15.0]
        d += timedelta(days=1)
    return out


# --------------------------------------------------------------------------- adapter maths


def test_smsr_windows_match_engine_periods() -> None:
    assert tuple((a, b) for _, a, b in PERIODS) == SMSR_WINDOWS


def test_soil_moisture_percentile_vs_same_days_in_previous_years() -> None:
    soil = {}
    for y in range(2014, 2026):
        for i in range(10):
            day = date(y, 7, 15) - timedelta(days=i)
            v = 0.15 if y == 2025 else 0.20 + (y - 2014) * 0.005
            soil[day] = (v, v)
    vals, errs = soil_moisture_metrics(soil, D)
    assert not errs
    assert vals["soil_moisture_root_pct"] == 15.0
    assert vals["soil_moisture_percentile_10y"] == 0.0  # drier than all 10 previous years
    assert len(vals["soil_moisture_prev_years"]) == 10
    assert vals["soil_moisture_date"] == D.isoformat()


def test_soil_moisture_uses_latest_day_within_lag_and_reports_it() -> None:
    soil = {D - timedelta(days=4 + i): (0.2, 0.2) for i in range(10)}
    vals, _ = soil_moisture_metrics(soil, D)
    assert vals["soil_moisture_date"] == (D - timedelta(days=4)).isoformat()


def test_soil_moisture_missing_is_a_note_not_a_meteo_error() -> None:
    values, errors = compute_metrics(_series(), D, soil={})
    assert values["soil_moisture_note"]
    assert not any("wilgotno" in e.lower() for e in errors)


def test_smsr_window_kbw_sums_exact_calendar_window() -> None:
    rows = smsr_window_kbw(_series(p=1.0, e=3.0), D)
    first = rows[0]  # 21.III–20.V = 61 days → KBW = 61 × (1 − 3)
    assert first["by_year"][0] == {"year": 2025, "kbw": -122.0}
    assert len(first["by_year"]) == 10
    late = rows[-1]  # 1.VIII–30.IX has not ended by 15.VII → newest is the previous year
    assert late["by_year"][0]["year"] == 2024


def test_monthly_kbw_climatology_has_12_months_of_complete_years() -> None:
    rows = monthly_kbw_climatology(_series(p=1.0, e=3.0), D)
    assert [r["month"] for r in rows] == list(range(1, 13))
    jul = rows[6]
    assert jul["by_year"][0]["year"] == 2024  # July 2025 not complete on 15.VII
    assert jul["kbw_median"] == -62.0


# --------------------------------------------------------------------------- IUNG soil category


def test_iung_pixel_classification_and_dominant_category() -> None:
    rgba = np.zeros((2, 3, 4), dtype=np.uint8)
    rgba[..., 3] = 255
    rgba[0, 0, :3] = LEGEND[1]
    rgba[0, 1, :3] = LEGEND[3]
    rgba[0, 2, :3] = LEGEND[3]
    rgba[1, 0, :3] = LEGEND[11]  # forest
    rgba[1, 1, :3] = (1, 2, 3)   # unknown colour → skipped
    rgba[1, 2, 3] = 0            # transparent → skipped
    counts = classify_pixels(rgba, np.ones((2, 3), dtype=bool))
    assert counts == Counter({3: 2, 1: 1, 11: 1})
    s = summarize(counts)
    assert s["category"] == 3
    assert s["agri_share_pct"] == 75.0


def test_iung_forest_only_has_no_category() -> None:
    s = summarize(Counter({11: 10}))
    assert s["category"] is None
    assert "las" in s["dominant_label"]


# --------------------------------------------------------------------------- SMSR


def test_sugar_beet_on_soil_i_is_not_indicated_and_gets_no_borrowed_threshold() -> None:
    assert lookup_threshold("burak", 1, 6) is None
    assert crop_not_indicated("burak", 1)
    assert not crop_not_indicated("burak", 2)
    assert evaluate_smsr(crop_id="burak", analysis_date=D, kbw_60d=-300, awc_mm=None, soil_cat=1) is None


def test_iung_map_category_wins_over_awc() -> None:
    m = evaluate_smsr(crop_id="kukurydza_ziarno", analysis_date=D, kbw_60d=-100, awc_mm=100.0, soil_cat=4)
    assert m is not None and m.soil_cat == 4 and m.soil_source == "iung_map"
    m2 = evaluate_smsr(crop_id="kukurydza_ziarno", analysis_date=D, kbw_60d=-100, awc_mm=100.0)
    assert m2 is not None and m2.soil_cat == 1 and m2.soil_source == "awc"


def test_no_smsr_verdict_when_no_window_ends_near_the_date() -> None:
    assert evaluate_smsr(crop_id="zboza_ozime", analysis_date=date(2025, 4, 10), kbw_60d=-300,
                         awc_mm=100.0) is None


def _windows(kbw_by_index: dict[int, list[float]]) -> list[dict]:
    return [{"index": i, "by_year": [{"year": 2024 - k, "kbw": v} for k, v in enumerate(vals)]}
            for i, vals in kbw_by_index.items()]


def test_smsr_history_counts_years_below_threshold() -> None:
    thr = lookup_threshold("kukurydza_ziarno", 2, 7)  # 1.VI–31.VII, soil II = -184
    hist = smsr_history("kukurydza_ziarno", 2, _windows({7: [-200, -190, -100, -185, -50, -60, -70, -80, -90, -95]}))
    assert hist[0].threshold_mm == thr == -184
    assert hist[0].years_below == 3
    assert hist[0].below_years == (2021, 2023, 2024)


# --------------------------------------------------------------------------- risk window


def _facts(**kw) -> Facts:
    base = dict(crop_id="kukurydza_ziarno", crop_critical=(7, 8), crop_season=(5, 6, 7, 8, 9), soil_cat=2)
    base.update(kw)
    return Facts(**base)


def test_risk_window_from_smsr_names_period_years_and_critical_overlap() -> None:
    dry = [-250] * 4 + [-50] * 6
    wet = [-50] * 10
    hist = smsr_history("kukurydza_ziarno", 2, _windows({6: wet, 7: dry, 8: dry, 9: wet}))
    rw = compute_risk_window(_facts(smsr_hist=hist))
    assert rw is not None and rw.method == "smsr"
    assert rw.peakLabel == "1.VI–31.VII"
    assert (rw.yearsHit, rw.yearsTotal) == (4, 10)
    assert rw.months == [6, 7, 8]
    assert rw.criticalOverlap == [7, 8]
    assert "od 1.VI do 10.VIII" in rw.text and "4 z 10" in rw.text
    assert [b.risky for b in rw.bars] == [False, True, True, False]


def test_risk_window_never_crossed_says_so() -> None:
    hist = smsr_history("kukurydza_ziarno", 4, _windows({7: [-50] * 10}))
    rw = compute_risk_window(_facts(smsr_hist=hist, soil_cat=4))
    assert rw is not None and rw.peakLabel is None and "ani razu" in rw.text


def test_risk_window_monthly_fallback_without_smsr_crop() -> None:
    med = [30, 20, -5, -35, -60, -80, -55, -50, -40, 0, 20, 30]
    rows = [{"month": m + 1, "kbw_median": v, "years": 10} for m, v in enumerate(med)]
    rw = compute_risk_window(_facts(crop_id="brak", crop_critical=(), smsr_hist=[], kbw_monthly=rows))
    assert rw is not None and rw.method == "kbw_monthly"
    assert rw.months == [5, 6, 7]
    assert rw.peakLabel == "V–VII"
    assert "czerwiec" in rw.text


# --------------------------------------------------------------------------- SCS-CN runoff


def test_scs_curve_number_formula() -> None:
    # CN 78 → S = 71.6 mm, Ia = 14.3 mm; P = 50 mm → Q ≈ 12.0 mm (TR-55 eq. 2-3)
    assert abs(scs_runoff_mm(50.0, 78) - 12.0) < 0.2
    assert scs_runoff_mm(10.0, 78) == 0.0


def test_hydrologic_soil_group_from_texture() -> None:
    assert hydrologic_group(92, 5) == "A"
    assert hydrologic_group(70, 8) == "B"
    assert hydrologic_group(40, 30) == "C"
    assert hydrologic_group(20, 45) == "D"
    assert hydrologic_group(None, 10) is None


def test_runoff_estimate_volume_and_two_year_storm_pond() -> None:
    rain = [60.0, 50.0, 45.0, 40.0, 35.0, 20.0, 10.0, 5.0] + [4.0] * 100
    f = _facts(sand=40, clay=25, area_ha=2.0, rain_days=rain, rain_years=10, precip_year=600.0)
    ro = estimate_runoff(f)
    assert ro is not None
    assert ro.hsg == "C" and ro.cn == CN_TABLE["row_crops"]["C"] == 85
    q = sum(scs_runoff_mm(p, 85) for p in rain) / 10
    assert ro.runoff_year_mm == round(q, 1)
    assert ro.storm_rain_mm == 35.0  # 5th largest in 10 years ≈ once in 2 years
    assert ro.pond_m3 == round(scs_runoff_mm(35.0, 85) * 2.0 * 10, -1)  # ≥ 100 m³ → rounded to 10 m³


def test_no_runoff_estimate_without_soil_texture() -> None:
    assert estimate_runoff(_facts(sand=None, clay=None, area_ha=2.0, rain_days=[50.0], rain_years=10,
                                  precip_year=600.0)) is None


# --------------------------------------------------------------------------- engine integration


def test_engine_uses_soil_moisture_iung_category_risk_window_and_runoff(sample_bundle) -> None:
    mv = sample_bundle.meteo["values"]
    mv.update({
        "soil_moisture_root_pct": 14.0, "soil_moisture_root_median_10y": 22.0,
        "soil_moisture_percentile_10y": 0.0, "soil_moisture_date": "2025-07-15",
        "kbw_smsr_windows": _windows({7: [-250] * 4 + [-50] * 6}),
        "rain_events_10y": {"years": 10, "min_mm": 3.0, "precip_mean_year": 600.0,
                            "days": [60.0, 50.0, 45.0, 40.0, 35.0, 20.0]},
    })
    sample_bundle.soil["values"].update({"sand_pct": 40.0, "clay_pct": 25.0})
    sample_bundle.iung_soil = {"values": {"category": 2, "category_share_pct": 100.0, "dominant_code": 2},
                               "sources": [], "fetchedAt": "", "coverage": "full", "errors": [], "fromCache": False}
    r = run_engine(bundle=sample_bundle, crop_id="kukurydza_ziarno", analysis_date=D)
    ev = {e.id: e for e in r.evidence}
    assert ev["ev_soil_moisture"].value == 14.0
    assert "ev_soil_moisture" in r.moistureAssessment.current.evidenceRefs
    assert ev["ev_soil_category"].sourceId == "iung_soil"
    assert ev["ev_risk_window"].value == "1.VI–31.VII"
    rw = r.moistureAssessment.susceptibility.riskWindow
    assert rw is not None and rw.yearsHit == 4
    assert {"ev_runoff_volume", "ev_pond_volume"} <= set(ev)
    assert "iung_soil" in {s.id for s in r.sources}
    assert any("ERA5-Land" in lim for lim in r.limitations)
    # every evidence ref used anywhere exists
    ids = set(ev)
    assert set(rw.evidenceRefs) <= ids


# --------------------------------------------------------------------------- susceptibility balance


def _sus(**kw) -> tuple[int, str]:
    from app.engine.assess import assess_moisture

    base = dict(precip30=50.0, precip30_normal=60.0, kbw30=-60.0, kbw_pct=40.0, dry_spell=3.0,
                crop_id="kukurydza_ziarno", crop_sens=0.8, crop_critical=(7, 8), crop_season=(5, 6, 7, 8, 9))
    base.update(kw)
    s = assess_moisture(Facts(**base)).susceptibility
    return s.score0to100 or 0, s.level


def _summers(kbw: float, dry: int) -> list[dict]:
    return [{"year": 2015 + i, "kbw": (-160.0 if i < dry else kbw)} for i in range(10)]


def test_good_loess_soil_with_rare_iung_drought_is_not_high() -> None:
    """Regression: typical Polish summer balance (−110 … −180 mm) must not make every plot 'high'."""
    hist = smsr_history("kukurydza_ziarno", 3, _windows({7: [-100] * 10}))
    score, level = _sus(kbw_summer_mean=-130.0, summers=_summers(-110.0, 3), awc=185.0, sand=20.0, soc=1.5,
                        soil_cat=3, smsr_hist=hist)
    assert level == "low", score


def test_sandy_soil_with_frequent_iung_drought_is_high() -> None:
    hist = smsr_history("kukurydza_ziarno", 1, _windows({7: [-200] * 4 + [-100] * 6}))
    score, level = _sus(kbw_summer_mean=-175.0, summers=_summers(-170.0, 7), awc=85.0, sand=75.0, soc=0.8,
                        soil_cat=1, smsr_hist=hist)
    assert level == "high", score


def test_wet_mountain_climate_is_low() -> None:
    score, level = _sus(kbw_summer_mean=20.0, summers=_summers(10.0, 0), awc=170.0, sand=30.0, soc=2.0)
    assert level == "low", score
