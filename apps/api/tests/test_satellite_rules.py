"""Satellite (Sentinel-2) facts feed the engine: canopy water, bare soil, standing water, history."""

from __future__ import annotations

from datetime import date

from app.engine.assess import assess_moisture, satellite_moisture_signal
from app.engine.causes import detect_causes
from app.engine.facts import Facts
from app.engine.rank import rank_recommendations
from app.engine.run import run_engine
from tests.fixtures.sample_bundle import make_sample_bundle

WEATHER = dict(precip30=40, precip30_normal=50, kbw30=-30, kbw_pct=40, dry_spell=3, awc=140)


def _ids(recs):
    return [r.actionId for r in recs]


def test_ndmi_anomaly_lowers_score_and_is_cited():
    base = assess_moisture(Facts(**WEATHER)).current
    f = Facts(**WEATHER, ndvi=0.7, ndmi=0.12, hist_ndmi=0.30, hist_ndvi=0.72, hist_n=4, ndvi_date="2025-07-10")
    cur = assess_moisture(f).current
    assert cur.score0to100 < base.score0to100
    assert "ev_ndmi" in cur.evidenceRefs
    assert "zwykle" in cur.summary


def test_ndmi_ignored_without_green_cover_or_history():
    # Bare field: canopy water is meaningless → no satellite effect.
    assert satellite_moisture_signal(Facts(ndvi=0.15, ndmi=-0.3, hist_ndmi=0.2, hist_n=5)) == (0.0, [])
    # Two years are not a baseline.
    assert Facts(ndmi=0.1, hist_ndmi=0.3, hist_n=2).ndmi_anomaly is None


def test_satellite_effect_is_bounded():
    delta, _ = satellite_moisture_signal(Facts(ndvi=0.8, ndmi=-0.4, hist_ndmi=0.4, hist_n=5))
    assert delta >= -10


def test_bare_soil_after_harvest_is_a_cause_with_cover_crops():
    f = Facts(**WEATHER, ndvi=0.12, bare_pct=85, ndvi_date="2025-09-20", crop_id="kukurydza")
    a = assess_moisture(f)
    causes = detect_causes(assessment=a, f=f)
    assert "bare_soil" in {c.id for c in causes}
    recs = rank_recommendations(assessment=a, causes=causes, f=f)
    assert "cover_crops" in _ids(recs.agrotech)
    cover = next(r for r in recs.agrotech if r.actionId == "cover_crops")
    assert "ev_bare_soil" in cover.evidenceRefs


def test_bare_soil_not_a_cause_for_fresh_winter_sowing_or_spring():
    for kw in (dict(ndvi_date="2025-10-05", crop_id="zboza_ozime"), dict(ndvi_date="2025-05-05", crop_id="kukurydza")):
        f = Facts(**WEATHER, ndvi=0.1, bare_pct=90, **kw)
        assert "bare_soil" not in {c.id for c in detect_causes(assessment=assess_moisture(f), f=f)}


def test_standing_water_suggests_pond_even_when_wet():
    f = Facts(precip30=90, precip30_normal=50, kbw30=40, kbw_pct=90, awc=170,
              ndvi=0.5, water_pct=6, ndvi_date="2025-04-10", crop_id="zboza_ozime")
    a = assess_moisture(f)
    recs = rank_recommendations(assessment=a, causes=detect_causes(assessment=a, f=f), f=f)
    pond = next(r for r in recs.retention if r.actionId == "small_pond")
    assert "ev_standing_water" in pond.evidenceRefs


def test_history_source_and_missing_data():
    d = date(2025, 7, 15)
    b = make_sample_bundle(plot_id="sat-hist", lat=None, lng=None, analysis_date=d)
    b.sat_history = {"values": {}, "sources": [], "fetchedAt": "", "coverage": "none", "errors": ["x"]}
    r = run_engine(bundle=b, crop_id="kukurydza", analysis_date=d)
    # Optional baseline: visible in sources + limitations, but never flags the report incomplete.
    assert not any(m.id == "missing_sentinel2_history" for m in r.missingData)
    assert next(s for s in r.sources if s.id == "sentinel2_history").status == "failed"
    if any(e.id == "ev_ndvi" for e in r.evidence):
        assert any("poprzednimi latami" in x for x in r.limitations)
    # Evidence refs never dangle.
    ev = {e.id for e in r.evidence}
    for c in r.causes:
        assert set(c.evidenceRefs) <= ev


def test_crop_rotation_blocks_history_comparison():
    # Green now, bare in past years → different crop, not "wetter than usual".
    f = Facts(**WEATHER, ndvi=0.6, ndmi=0.21, hist_ndvi=0.2, hist_ndmi=-0.09, hist_n=5)
    assert f.ndmi_anomaly is None
    assert satellite_moisture_signal(f)[0] == 0.0
