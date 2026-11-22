"""Irrigation respects the crop season, gives a dose; slope uses a plane fit; pond cites the low spot."""

from __future__ import annotations

from shapely.geometry import Point

from app.crops.catalog import CROPS, NO_CROP_ID, get_crop
from app.engine.assess import assess_moisture
from app.engine.causes import detect_causes
from app.engine.facts import Facts, build_evidence
from app.engine.rank import rank_recommendations
from plot.resolver import _slope_from_heights

DRY = dict(precip30=5, precip30_normal=60, kbw30=-110, kbw_pct=5, dry_spell=25, awc=80, et0_30d=120)


def _potato_facts(month: int, **kw) -> Facts:
    c = get_crop("ziemniak")
    return Facts(**{**DRY, **kw}, crop_sens=c["droughtSensitivity"], crop_id=c["id"], crop_kc=c["kcMid"],
                 crop_season=c["seasonMonths"], crop_critical=c["criticalMonths"],
                 crop_phase_pl=c["criticalPhasePl"], month=month)


def _rank(f: Facts):
    a = assess_moisture(f)
    return rank_recommendations(assessment=a, causes=detect_causes(assessment=a, f=f), f=f)


def test_catalog_critical_months_inside_season():
    for c in CROPS.values():
        if c["id"] == NO_CROP_ID:  # „Brak uprawy”: no season, Kc = 0 by design
            continue
        assert set(c["criticalMonths"]) <= set(c["seasonMonths"]), c["id"]
        assert 0.5 < c["kcMid"] < 1.4


def test_no_irrigation_outside_season():
    recs = _rank(_potato_facts(month=11))
    assert recs.irrigation is None
    assert "poza sezonem" in (recs.irrigationNote or "")


def test_irrigation_in_critical_phase_has_dose_and_timing():
    f = _potato_facts(month=7, area_ha=2.0)
    recs = _rank(f)
    assert recs.irrigation, "dry July + potato should allow irrigation"
    rec = recs.irrigation[0]
    assert rec.timeframe.startswith("teraz")
    assert "15–20 litrów wody na m²" in rec.why  # AWC 80 mm = light soil
    assert "150–200 m³ na hektar" in rec.why
    assert "2 ha) ok. 300–400 m³" in rec.why
    # daily use = 120 × 1.15 / 30 = 4.6 mm → 15/4.6 = 3, 20/4.6 = 4 days
    assert "co 3–4 dni" in rec.why and "co 3–4 dni" in rec.timeframe
    assert "ev_crop_deficit" in rec.evidenceRefs
    # deficit = 120 × 1.15 − 5 = 133 mm, shown as evidence
    ev = {e.id: e for e in build_evidence(f, get_crop("ziemniak"))}
    assert ev["ev_crop_deficit"].value == 133


def test_plane_fit_ignores_single_outlier():
    # 10 m grid on a 2 % slope along x, plus one pit: max−min/distance would exaggerate.
    pts, hs = [], []
    for i in range(5):
        for j in range(5):
            pts.append(Point(i * 10, j * 10))
            hs.append(100 + 0.02 * i * 10)
    hs[12] -= 1.0  # pit in the middle
    res = _slope_from_heights(pts, hs)
    assert res["slopeMethod"] == "plane_fit"
    assert 1.5 < res["slopePct"] < 2.5


def test_pond_cites_lowest_spot():
    f = _potato_facts(month=7, spot_drop=1.4, spot_near_edge=False)
    recs = _rank(f)
    pond = [r for r in recs.retention if r.actionId == "small_pond"]
    assert pond and "ev_low_spot" in pond[0].evidenceRefs
    assert "1,4 m" in pond[0].why


def test_interval_clamped_and_missing():
    from app.engine.rank import irrigation_interval
    assert irrigation_interval((25, 30), 0.5) == (14, 14)
    assert irrigation_interval((15, 20), 12.0) == (2, 2)
    assert irrigation_interval((25, 30), None) is None
