from calendar import monthrange
from datetime import date

from adapters.open_meteo import monthly_precip
from app.engine.run import run_engine


async def test_single_month_does_not_establish_long_term_risk(sample_bundle):
    sample_bundle.meteo["values"] = {"precip_30d": 25}
    report = run_engine(bundle=sample_bundle, crop_id="kukurydza", analysis_date=date(2026, 7, 15))
    assert report.moistureAssessment.susceptibility.level == "insufficient_data"
    assert report.moistureAssessment.susceptibility.score0to100 is None
    assert any(m.id == "missing_summer_history" for m in report.missingData)


def test_historical_february_excludes_january_rain():
    series = {}
    for year in range(2014, 2025):
        series[date(year, 1, 31)] = [100, 0, 0]
        for day in range(1, monthrange(year, 2)[1] + 1):
            series[date(year, 2, day)] = [1, 0, 0]
    complete = monthly_precip(series, date(2024, 2, 29), months=1)[0]
    assert complete["normal"] == 28.2
    partial = monthly_precip(series, date(2024, 2, 28), months=1)[0]
    assert partial["normal"] == 28
