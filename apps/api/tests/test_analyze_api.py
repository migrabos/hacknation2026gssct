"""HTTP smoke: /health, /crops, /plot, /analyze."""

from __future__ import annotations


def test_health(client) -> None:
    data = client.get("/health").json()
    assert data["status"] == "ok"
    assert data["adapters"] == "mock"


def test_crops(client) -> None:
    crops = client.get("/crops").json()
    assert {"kukurydza", "ziemniak", "warzywa", "zboza", "rzepak"} <= {c["id"] for c in crops}
    for c in crops:
        assert set(c) == {"id", "name", "droughtSensitivity"}
        assert c["droughtSensitivity"] in ("low", "medium", "high")


def test_plot_by_point_mock(client) -> None:
    p = client.get("/plot/by-point", params={"lat": 52.2, "lng": 19.4}).json()
    assert p["centroid"] == [19.4, 52.2]  # [lng, lat]
    assert p["geometry"]["type"] == "Polygon"
    assert p["areaHa"] > 0


def test_analyze_api(client) -> None:
    resp = client.post("/analyze", json={"plotId": "141201_2.0001.123", "cropId": "kukurydza",
                                          "analysisDate": "2025-07-15"})
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["crop"] == {"id": "kukurydza", "name": "Kukurydza", "droughtSensitivity": "high"}
    assert data["moistureAssessment"]["current"]["level"] in ("very_dry", "dry", "normal", "wet")
    assert data["moistureAssessment"]["susceptibility"]["level"] in ("low", "medium", "high")
    assert data["narrative"]["generatedBy"] == "template"
    assert data["status"] in ("complete", "partial")
    assert data["meta"]["adapters"] == "mock"
    ev_ids = {e["id"] for e in data["evidence"]}
    src_ids = {s["id"] for s in data["sources"]}
    assert all(e["sourceId"] in src_ids for e in data["evidence"])
    for c in data["causes"]:
        assert set(c["evidenceRefs"]) <= ev_ids


def test_analyze_plot_id_wins_over_coords(client) -> None:
    """Web sends plotId + centroid; plotId must win (no XOR rejection)."""
    resp = client.post("/analyze", json={"plotId": "141201_2.0001.123", "lat": 52.2, "lng": 21.0,
                                          "cropId": "zboza", "analysisDate": "2025-07-15"})
    assert resp.status_code == 200, resp.text
    assert resp.json()["plot"]["plotId"] == "141201_2.0001.123"


def test_analyze_requires_location(client) -> None:
    resp = client.post("/analyze", json={"cropId": "zboza", "analysisDate": "2025-07-15"})
    assert resp.status_code == 422


def test_analyze_by_coords(client) -> None:
    resp = client.post("/analyze", json={"lat": 52.2297, "lng": 21.0122, "cropId": "warzywa",
                                          "analysisDate": "2025-06-01"})
    assert resp.status_code == 200, resp.text
    lng, lat = resp.json()["plot"]["centroid"]
    assert (round(lat, 4), round(lng, 4)) == (52.2297, 21.0122)


def test_unknown_crop(client) -> None:
    resp = client.post("/analyze", json={"plotId": "x", "cropId": "banan", "analysisDate": "2025-06-01"})
    assert resp.status_code == 422


def test_analyze_with_only_zero_rainfall(client, mock_bundle, monkeypatch) -> None:
    async def sparse_bundle(**kwargs):
        mock_bundle.meteo["values"] = {"precip_30d": 0}
        for source in (mock_bundle.soil, mock_bundle.sat, mock_bundle.drought):
            source.update(values={}, coverage="none")
        return mock_bundle

    monkeypatch.setattr("app.orchestrate.fetch_bundle", sparse_bundle)
    response = client.post("/analyze", json={"plotId": "x", "cropId": "kukurydza", "analysisDate": "2025-07-15"})
    assert response.status_code == 200
    report = response.json()
    current = report["moistureAssessment"]["current"]
    assert current["level"] == "insufficient_data"
    assert "score0to100" not in current
    assert "Za mało danych do oceny" in current["headline"]
    assert "0 mm" in current["summary"]
    assert current["evidenceRefs"] == ["ev_precip_30d"]
    rain = next(e for e in report["evidence"] if e["id"] == "ev_precip_30d")
    assert (rain["value"], rain["unit"]) == (0, "mm")
    assert report["status"] == "partial"
    assert any(m["id"] == "missing_moisture_comparison" for m in report["missingData"])
    assert "irrigation" not in report["recommendations"]
    assert "Za mało danych" in report["recommendations"]["irrigationNote"]
