"""Crop fit ranking (engine/crop_fit.py) on synthetic plots — offline, deterministic."""

from __future__ import annotations

from datetime import date

from app.crops.catalog import VALID_CROP_IDS
from app.crops.fit_profiles import FIT_PROFILES
from app.engine.crop_fit import rank_crop_fit
from app.engine.crop_fit_report import run_crop_fit_report
from app.engine.facts import Facts
from app.engine.run import run_engine

DRY_SUMMERS = [{"year": 2016 + i, "kbw": -230.0} for i in range(10)]
WET_SUMMERS = [{"year": 2016 + i, "kbw": -60.0} for i in range(10)]


def _rank(**kw) -> list[str]:
    fit = rank_crop_fit(Facts(**kw))
    assert fit is not None
    return [i.id for i in fit.ranking]


def _item(fit, crop_id):
    return next(i for i in fit.ranking if i.id == crop_id)


def test_profiles_point_at_real_catalog_groups() -> None:
    assert {p["group"] for p in FIT_PROFILES} <= VALID_CROP_IDS
    assert len({p["id"] for p in FIT_PROFILES}) == len(FIT_PROFILES)


def test_dry_sandy_plot_prefers_rye_over_wheat_and_strawberries() -> None:
    order = _rank(sand=80, awc=70, kbw_summer_mean=-230, summers=DRY_SUMMERS)
    assert order.index("zyto") < order.index("pszenica_ozima")
    assert order.index("zyto") < 5
    assert order.index("truskawki") > order.index("krzewy_jagodowe")  # shallow roots lose on dry sand
    assert order[-1] in ("truskawki", "warzywa")


def test_reasons_cite_evidence() -> None:
    fit = rank_crop_fit(Facts(sand=80, awc=70, kbw_summer_mean=-230, summers=DRY_SUMMERS))
    wheat = _item(fit, "pszenica_ozima")
    assert wheat.fit != "good" and wheat.cons
    assert "ev_soil_awc" in wheat.evidenceRefs or "ev_soil_sand" in wheat.evidenceRefs
    rye = _item(fit, "zyto")
    assert any("słabej" in p for p in rye.pros)


def test_good_soil_wet_summers_suits_demanding_crops() -> None:
    fit = rank_crop_fit(Facts(sand=30, clay=20, awc=180, kbw_summer_mean=-60, summers=WET_SUMMERS,
                              land_soil_classes=["II"], land_label="grunty orne", land_category="arable",
                              land_agri=True))
    for crop in ("pszenica_ozima", "rzepak", "burak"):
        assert _item(fit, crop).fit == "good", crop
    assert "ev_land_use" in _item(fit, "pszenica_ozima").evidenceRefs  # EGiB class used, not SoilGrids


def test_slope_penalises_row_crops() -> None:
    flat = rank_crop_fit(Facts(awc=150, kbw_summer_mean=-120, slope=1.0))
    steep = rank_crop_fit(Facts(awc=150, kbw_summer_mean=-120, slope=8.0))
    assert _item(steep, "kukurydza").score0to100 < _item(flat, "kukurydza").score0to100
    assert _item(steep, "laka").score0to100 >= _item(flat, "laka").score0to100
    assert any("spadku" in c for c in _item(steep, "burak").cons)


def test_wet_heavy_soil_favours_meadow() -> None:
    fit = rank_crop_fit(Facts(clay=48, awc=170, kbw_summer_mean=-80, water_dist=40.0, nearby_water=True))
    assert _item(fit, "laka").score0to100 > _item(fit, "rzepak").score0to100
    assert any("zastoisk" in c for c in _item(fit, "rzepak").cons)


def test_registered_grassland_warns_about_ploughing() -> None:
    fit = rank_crop_fit(Facts(awc=150, kbw_summer_mean=-120, land_category="meadow", land_label="łąka trwała",
                              land_agri=True))
    assert fit.ranking[0].id == "laka"
    assert any("TUZ" in c for c in _item(fit, "kukurydza").cons)


def test_no_crop_advice_on_non_agricultural_land() -> None:
    assert rank_crop_fit(Facts(awc=150, land_category="built", land_agri=False)) is None


def test_missing_data_lowers_confidence_but_still_ranks() -> None:
    fit = rank_crop_fit(Facts())
    assert fit.confidence == "low" and len(fit.ranking) == len(FIT_PROFILES)
    assert fit.notConsidered


def test_crop_fit_report_is_separate_and_deterministic(sample_bundle) -> None:
    d = date(2025, 7, 15)
    r1 = run_crop_fit_report(bundle=sample_bundle, analysis_date=d)
    r2 = run_crop_fit_report(bundle=sample_bundle, analysis_date=d)
    assert r1.cropFit is not None and r1.cropFit.selectedGroupId is None
    assert r1.cropFit.model_dump() == r2.cropFit.model_dump()
    ev_ids = {e.id for e in r1.evidence}
    assert all(ref in ev_ids for i in r1.cropFit.ranking for ref in i.evidenceRefs)
    assert "ev_crop_sensitivity" not in ev_ids and "ev_ndvi" not in ev_ids  # no crop, no current season
    assert {s.id for s in r1.sources}.isdisjoint({"sentinel2", "edo"})
    scores = [i.score0to100 for i in r1.cropFit.ranking]
    assert scores == sorted(scores, reverse=True)


def test_water_report_has_no_crop_fit(sample_bundle) -> None:
    r = run_engine(bundle=sample_bundle, crop_id="kukurydza", analysis_date=date(2025, 7, 15))
    assert "cropFit" not in r.model_dump()


def test_crop_fit_api(client) -> None:
    resp = client.post("/crop-fit", json={"plotId": "141201_2.0001.123", "analysisDate": "2025-07-15"})
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["plot"]["plotId"] == "141201_2.0001.123"
    assert len(data["cropFit"]["ranking"]) == len(FIT_PROFILES)
    assert data["cropFit"]["notConsidered"]
    assert client.post("/crop-fit", json={"analysisDate": "2025-07-15"}).status_code == 422
