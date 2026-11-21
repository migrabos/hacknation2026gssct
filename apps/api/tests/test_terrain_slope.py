from shapely.geometry import Point

from plot.resolver import _slope_from_heights


def test_equal_heights_at_distinct_locations_give_zero_slope():
    result = _slope_from_heights([Point(0, 0), Point(100, 0)], [120, 120])
    assert result["distanceM"] == 100
    assert result["slopePct"] == 0
    assert result["runoffRisk"] == "low"


def test_repeated_location_has_no_measurable_slope():
    result = _slope_from_heights([Point(0, 0), Point(0, 0)], [120, 120])
    assert result["slopePct"] is None
    assert result["runoffRisk"] == "unknown"
