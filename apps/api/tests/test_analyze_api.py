"""HTTP smoke: /health, /crops, /plot, /analyze."""

from __future__ import annotations


def test_health(client) -> None:
    data = client.get("/health").json()
    assert data["status"] == "ok"
    assert data["adapters"] == "live"


def test_crops(client) -> None:
    crops = client.get("/crops").json()
    assert {
        "brak", "zboza_ozime", "zboza_jare", "kukurydza_ziarno", "kukurydza_kiszonka", "rzepak",
        "ziemniak", "burak", "chmiel", "tyton", "warzywa", "krzewy", "drzewa", "truskawki", "straczkowe",
    } <= {c["id"] for c in crops}
    assert len(crops) == 15
    assert crops[0]["id"] == "brak"
    assert crops[0]["name"] == "Brak uprawy"
    for c in crops:
        assert set(c) == {"id", "name", "droughtSensitivity"}
        assert c["droughtSensitivity"] in ("low", "medium", "high")


def test_plot_by_point(client) -> None:
    p = client.get("/plot/by-point", params={"lat": 52.2, "lng": 19.4}).json()
    assert p["centroid"] == [19.4, 52.2]  # [lng, lat]
    assert p["geometry"]["type"] == "Polygon"
    assert p["areaHa"] > 0


def test_analyze_api(client) -> None:
    resp = client.post("/analyze", json={"plotId": "141201_2.0001.123", "cropId": "kukurydza",
                                          "analysisDate": "2025-07-15"})
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["crop"] == {"id": "kukurydza_ziarno", "name": "Kukurydza na ziarno", "droughtSensitivity": "high"}
    assert data["moistureAssessment"]["current"]["level"] in ("very_dry", "dry", "normal", "wet")
    assert data["moistureAssessment"]["susceptibility"]["level"] in ("low", "medium", "high")
    assert data["narrative"]["sections"][0]["id"] == "assessment"
    assert data["status"] in ("complete", "partial")
    assert data["meta"]["adapters"] == "live"
    ev_ids = {e["id"] for e in data["evidence"]}
    src_ids = {s["id"] for s in data["sources"]}
    assert all(e["sourceId"] in src_ids for e in data["evidence"])
    for c in data["causes"]:
        assert set(c["evidenceRefs"]) <= ev_ids


def test_analyze_plot_id_wins_over_coords(client) -> None:
    """Web sends plotId + centroid; plotId must win (no XOR rejection)."""
    resp = client.post("/analyze", json={"plotId": "141201_2.0001.123", "lat": 52.2, "lng": 21.0,
                                          "cropId": "zboza_ozime", "analysisDate": "2025-07-15"})
    assert resp.status_code == 200, resp.text
    assert resp.json()["plot"]["plotId"] == "141201_2.0001.123"


def test_analyze_requires_location(client) -> None:
    resp = client.post("/analyze", json={"cropId": "zboza_ozime", "analysisDate": "2025-07-15"})
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


def test_analyze_with_only_zero_rainfall(client, sample_bundle, monkeypatch) -> None:
    async def sparse_bundle(**kwargs):
        sample_bundle.meteo["values"] = {"precip_30d": 0}
        for source in (sample_bundle.soil, sample_bundle.sat, sample_bundle.drought):
            source.update(values={}, coverage="none")
        return sample_bundle

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


def test_legacy_crop_ids_still_accepted():
    from app.crops.catalog import get_crop
    assert get_crop("pszenica")["id"] == "zboza_ozime"
    assert get_crop("zboza")["id"] == "zboza_ozime"
    assert get_crop("kukurydza")["id"] == "kukurydza_ziarno"
    assert get_crop("sad")["id"] == "drzewa"
    assert get_crop("jagodowe")["id"] == "truskawki"
