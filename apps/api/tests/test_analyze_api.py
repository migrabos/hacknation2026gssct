"""HTTP smoke: /health, /crops, /analyze."""

from __future__ import annotations


def test_health(client) -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "engineVersion" in data


def test_crops(client) -> None:
    resp = client.get("/crops")
    assert resp.status_code == 200
    crops = resp.json()
    ids = {c["id"] for c in crops}
    assert {"kukurydza", "ziemniak", "warzywa", "zboza", "rzepak"} <= ids


def test_analyze_api(client) -> None:
    resp = client.post(
        "/analyze",
        json={
            "plotId": "141201_2.0001.123",
            "cropId": "kukurydza",
            "analysisDate": "2025-07-15",
        },
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["crop"]["id"] == "kukurydza"
    assert "moistureAssessment" in data
    assert "current" in data["moistureAssessment"]
    assert "multiYearSusceptibility" in data["moistureAssessment"]
    assert data["narrative"]["mode"] in ("template", "llm")
    assert "sources" in data
    assert "missingData" in data
    assert data["meta"]["engineVersion"]


def test_analyze_rejects_both_plot_and_coords(client) -> None:
    resp = client.post(
        "/analyze",
        json={
            "plotId": "abc",
            "lat": 52.2,
            "lng": 21.0,
            "cropId": "zboza",
            "analysisDate": "2025-07-15",
        },
    )
    assert resp.status_code == 422


def test_analyze_by_coords(client) -> None:
    resp = client.post(
        "/analyze",
        json={
            "lat": 52.2297,
            "lng": 21.0122,
            "cropId": "warzywa",
            "analysisDate": "2025-06-01",
        },
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["plot"]["centroid"]["lat"]
