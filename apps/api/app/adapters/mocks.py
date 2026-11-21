"""Deterministic mock adapters — seeded from plotId/lat/crop/date hash.

Person 2 replaces these with live HTTP adapters that return the same AdapterResult shape.
"""

from __future__ import annotations

import asyncio
import hashlib
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any

from app.schemas.adapters import AdapterResult


def _seed_int(*parts: Any) -> int:
    raw = "|".join("" if p is None else str(p) for p in parts)
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return int(digest[:8], 16)


def _unit(seed: int, salt: int = 0) -> float:
    """Deterministic float in [0, 1)."""
    return ((seed + salt * 9973) % 10_000) / 10_000.0


def _now_iso(analysis_date: date) -> datetime:
    return datetime(
        analysis_date.year,
        analysis_date.month,
        analysis_date.day,
        12,
        0,
        0,
        tzinfo=timezone.utc,
    )


VOIVODESHIPS = [
    "mazowieckie",
    "wielkopolskie",
    "dolnośląskie",
    "małopolskie",
    "lubelskie",
    "podlaskie",
]


class MockPlotAdapter:
    async def fetch(
        self,
        *,
        plot_id: str | None,
        lat: float | None,
        lng: float | None,
        analysis_date: date,
    ) -> AdapterResult:
        seed = _seed_int(plot_id, lat, lng, analysis_date.isoformat())
        lat_v = lat if lat is not None else 49.0 + _unit(seed, 1) * 5.5
        lng_v = lng if lng is not None else 14.0 + _unit(seed, 2) * 10.0
        slope = round(0.5 + _unit(seed, 3) * 8.0, 2)
        runoff = "low" if slope < 2 else ("moderate" if slope < 5 else "high")
        nearby = _unit(seed, 4) > 0.55
        values = {
            "plotId": plot_id or f"mock-{seed % 1_000_000:06d}",
            "geometry": {
                "type": "Polygon",
                "coordinates": [
                    [
                        [lng_v - 0.001, lat_v - 0.001],
                        [lng_v + 0.001, lat_v - 0.001],
                        [lng_v + 0.001, lat_v + 0.001],
                        [lng_v - 0.001, lat_v + 0.001],
                        [lng_v - 0.001, lat_v - 0.001],
                    ]
                ],
            },
            "centroid": {"lat": round(lat_v, 6), "lng": round(lng_v, 6)},
            "areaHa": round(0.5 + _unit(seed, 5) * 8.0, 2),
            "bbox": [lng_v - 0.001, lat_v - 0.001, lng_v + 0.001, lat_v + 0.001],
            "voivodeship": VOIVODESHIPS[seed % len(VOIVODESHIPS)],
            "terrain": {"slopePct": slope, "runoffRisk": runoff},
            "hydro": {
                "nearbyWater": nearby,
                "distanceClass": "near" if nearby else "far",
            },
        }
        return AdapterResult(
            values=values,
            sources=[
                {
                    "id": "mock_plot",
                    "name": "Mock ULDK plot resolver",
                    "url": None,
                    "coverage": "demo",
                }
            ],
            fetchedAt=_now_iso(analysis_date),
            coverage="demo",
            errors=[],
        )


class MockMeteoAdapter:
    async def fetch(
        self,
        *,
        plot_id: str | None,
        lat: float | None,
        lng: float | None,
        analysis_date: date,
    ) -> AdapterResult:
        seed = _seed_int("meteo", plot_id, lat, lng, analysis_date.isoformat())
        climate30 = round(40 + _unit(seed, 1) * 40, 1)  # 40–80 mm
        anomaly = -35 + _unit(seed, 2) * 50  # -35% … +15%
        precip30 = round(climate30 * (1 + anomaly / 100.0), 1)
        dry_spell = int(2 + _unit(seed, 3) * 20)
        monthly = []
        for m in range(12):
            base = 35 + 25 * abs(6 - m) / 6  # peaking away from midsummer dryness feel
            # Summer months (5–8) tend drier for demo susceptibility
            if m + 1 in (6, 7, 8):
                base *= 0.55 + _unit(seed, 10 + m) * 0.3
            else:
                base *= 0.85 + _unit(seed, 10 + m) * 0.4
            monthly.append(round(base, 1))
        precip_anomaly_10y = round(-20 + _unit(seed, 4) * 30, 1)
        values = {
            "precipMmLast30d": precip30,
            "precipMmClimate30d": climate30,
            "drySpellDays": dry_spell,
            "precipAnomalyPct10y": precip_anomaly_10y,
            "monthlyPrecipMm": monthly,
        }
        return AdapterResult(
            values=values,
            sources=[
                {
                    "id": "mock_meteo",
                    "name": "Mock Open-Meteo climate",
                    "url": "https://open-meteo.com/",
                    "coverage": "demo",
                }
            ],
            fetchedAt=_now_iso(analysis_date),
            coverage="demo",
            errors=[],
        )


class MockSoilAdapter:
    async def fetch(
        self,
        *,
        plot_id: str | None,
        lat: float | None,
        lng: float | None,
        analysis_date: date,
    ) -> AdapterResult:
        seed = _seed_int("soil", plot_id, lat, lng)
        sand = round(25 + _unit(seed, 1) * 55, 1)
        clay = round(5 + _unit(seed, 2) * 30, 1)
        if sand + clay > 90:
            clay = max(5.0, 90 - sand)
        soc = round(0.5 + _unit(seed, 3) * 2.5, 2)
        # Rough AWC proxy mm: more clay/SOC → higher storage; sand hurts
        awc = round(40 + clay * 1.2 + soc * 15 - sand * 0.35, 1)
        awc = max(20.0, min(180.0, awc))
        values = {
            "sandPct": sand,
            "clayPct": clay,
            "socPct": soc,
            "awcMmProxy": awc,
        }
        return AdapterResult(
            values=values,
            sources=[
                {
                    "id": "mock_soil",
                    "name": "Mock SoilGrids",
                    "url": "https://soilgrids.org/",
                    "coverage": "demo",
                }
            ],
            fetchedAt=_now_iso(analysis_date),
            coverage="demo",
            errors=[],
        )


class MockSatAdapter:
    async def fetch(
        self,
        *,
        plot_id: str | None,
        lat: float | None,
        lng: float | None,
        analysis_date: date,
    ) -> AdapterResult:
        seed = _seed_int("sat", plot_id, lat, lng, analysis_date.isoformat())
        # Stub: sometimes null anomaly to exercise missingData paths
        ndvi = round(0.25 + _unit(seed, 1) * 0.5, 3)
        anomaly = None if _unit(seed, 2) < 0.25 else round(-0.2 + _unit(seed, 3) * 0.35, 3)
        values = {"ndviLatest": ndvi, "ndviAnomaly": anomaly}
        errors: list[str] = []
        if anomaly is None:
            errors.append("ndviAnomaly unavailable (stub)")
        return AdapterResult(
            values=values,
            sources=[
                {
                    "id": "mock_sat",
                    "name": "Mock Sentinel-2 NDVI",
                    "url": "https://earth-search.aws.element84.com/",
                    "coverage": "demo-stub",
                }
            ],
            fetchedAt=_now_iso(analysis_date),
            coverage="demo-stub",
            errors=errors,
        )


class MockDroughtAdapter:
    async def fetch(
        self,
        *,
        plot_id: str | None,
        lat: float | None,
        lng: float | None,
        analysis_date: date,
    ) -> AdapterResult:
        seed = _seed_int("drought", plot_id, lat, lng, analysis_date.month)
        classes = [None, "I", "II", "III", "IV"]
        iung = classes[seed % len(classes)]
        values = {"iungClass": iung}
        errors = [] if iung else ["iungClass unavailable (best-effort stub)"]
        return AdapterResult(
            values=values,
            sources=[
                {
                    "id": "mock_drought",
                    "name": "Mock IUNG drought class",
                    "url": None,
                    "coverage": "demo-stub",
                }
            ],
            fetchedAt=_now_iso(analysis_date),
            coverage="demo-stub",
            errors=errors,
        )


class MockHydroAdapter:
    async def fetch(
        self,
        *,
        plot_id: str | None,
        lat: float | None,
        lng: float | None,
        analysis_date: date,
    ) -> AdapterResult:
        seed = _seed_int("hydro", plot_id, lat, lng)
        nearby = _unit(seed, 1) > 0.5
        values = {
            "nearbyWater": nearby,
            "distanceClass": "near" if nearby else ("mid" if _unit(seed, 2) > 0.4 else "far"),
        }
        return AdapterResult(
            values=values,
            sources=[
                {
                    "id": "mock_hydro",
                    "name": "Mock ISOK / Wody Polskie proximity",
                    "url": None,
                    "coverage": "demo",
                }
            ],
            fetchedAt=_now_iso(analysis_date),
            coverage="demo",
            errors=[],
        )


@dataclass
class MockAdapterBundle:
    plot: AdapterResult
    meteo: AdapterResult
    soil: AdapterResult
    sat: AdapterResult
    drought: AdapterResult
    hydro: AdapterResult


async def fetch_all_mocks(
    *,
    plot_id: str | None,
    lat: float | None,
    lng: float | None,
    analysis_date: date,
) -> MockAdapterBundle:
    """Fetch all mock adapters in parallel (instant)."""
    kwargs = dict(plot_id=plot_id, lat=lat, lng=lng, analysis_date=analysis_date)
    plot, meteo, soil, sat, drought, hydro = await asyncio.gather(
        MockPlotAdapter().fetch(**kwargs),
        MockMeteoAdapter().fetch(**kwargs),
        MockSoilAdapter().fetch(**kwargs),
        MockSatAdapter().fetch(**kwargs),
        MockDroughtAdapter().fetch(**kwargs),
        MockHydroAdapter().fetch(**kwargs),
    )
    return MockAdapterBundle(
        plot=plot,
        meteo=meteo,
        soil=soil,
        sat=sat,
        drought=drought,
        hydro=hydro,
    )
