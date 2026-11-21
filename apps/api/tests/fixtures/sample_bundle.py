"""Deterministic AdapterBundle builder for offline unit/API tests.

Not a runtime adapter mode — tests import this directly or patch fetch_bundle.
"""

from __future__ import annotations

import hashlib
import math
from datetime import date
from typing import Any

from app.adapters.bundle import AdapterBundle

FETCHED_AT = "2026-01-01T12:00:00Z"
VOIVODESHIPS = ["mazowieckie", "wielkopolskie", "dolnośląskie", "małopolskie", "lubelskie", "podlaskie"]


def _seed(*parts: Any) -> int:
    raw = "|".join("" if p is None else str(p) for p in parts)
    return int(hashlib.sha256(raw.encode("utf-8")).hexdigest()[:8], 16)


def _u(seed: int, salt: int = 0) -> float:
    """Deterministic float in [0, 1)."""
    return ((seed + salt * 9973) % 10_000) / 10_000.0


def _resp(name: str, values: dict[str, Any], errors: list[str] | None = None) -> dict[str, Any]:
    errors = errors or []
    return {
        "values": values,
        "sources": [{"name": name, "url": "", "fetchedAt": FETCHED_AT}],
        "fetchedAt": FETCHED_AT,
        "coverage": "none" if not values else ("partial" if errors else "full"),
        "errors": errors if values else (errors or ["Źródło nie zwróciło żadnych danych."]),
        "fromCache": False,
    }


def sample_plot(plot_id: str | None, lat: float | None, lng: float | None) -> dict[str, Any]:
    seed = _seed(plot_id, lat, lng)
    lat_v = lat if lat is not None else 50.0 + _u(seed, 1) * 3.5
    lng_v = lng if lng is not None else 15.5 + _u(seed, 2) * 7.5
    dx, dy = 0.0012, 0.0008
    ring = [
        [lng_v - dx, lat_v - dy],
        [lng_v + dx, lat_v - dy],
        [lng_v + dx, lat_v + dy],
        [lng_v - dx, lat_v + dy],
        [lng_v - dx, lat_v - dy],
    ]
    slope = round(0.3 + _u(seed, 3) * 6.0, 2)
    runoff = "low" if slope < 1.5 else ("medium" if slope <= 3.5 else "high")
    near = _u(seed, 4) > 0.5
    area = round(2 * dx * 111_320 * math.cos(math.radians(lat_v)) * 2 * dy * 111_320 / 10_000, 2)
    return {
        "plotId": plot_id or f"TEST_{lat_v:.4f}_{lng_v:.4f}",
        "geometry": {"type": "Polygon", "coordinates": [ring]},
        "centroid": [round(lat_v, 6), round(lng_v, 6)],
        "areaHa": area,
        "bbox": [lng_v - dx, lat_v - dy, lng_v + dx, lat_v + dy],
        "voivodeship": VOIVODESHIPS[seed % len(VOIVODESHIPS)],
        "county": None,
        "commune": None,
        "terrain": {"slopePct": slope, "runoffRisk": runoff, "resolutionM": 1, "dem": "test"},
        "hydro": {
            "nearbyWater": near,
            "distanceClass": "near" if near else "none",
            "missing": None,
            "nearestDistanceM": round(40 + _u(seed, 5) * 200, 1) if near else None,
            "nearestType": "ditch" if near else None,
        },
        "landUse": {
            "category": "arable", "labelPl": "grunt orny (pole uprawne)", "isAgricultural": True,
            "source": "egib", "uses": ["grunt orny (pole uprawne)"], "codes": ["RIVa"],
            "soilClasses": ["IVa"], "egib": {"dataDate": "DEMO"}, "notes": [],
        },
        "sources": [
            {"name": "ULDK GUGiK", "url": "", "fetchedAt": FETCHED_AT},
            {"name": "GUGiK NMT (numeryczny model terenu)", "url": "", "fetchedAt": FETCHED_AT},
            {"name": "OpenStreetMap (Overpass API)", "url": "", "fetchedAt": FETCHED_AT},
            {"name": "KIEG GUGiK – EGiB użytki gruntowe", "url": "", "fetchedAt": FETCHED_AT},
        ],
        "missingData": [],
        "limitations": [],
        "fetchedAt": FETCHED_AT,
    }


def sample_meteo(key: Any, d: date) -> dict[str, Any]:
    seed = _seed("meteo", key, d.isoformat())
    normal = round(45 + _u(seed, 1) * 35, 1)
    precip = round(normal * (0.3 + _u(seed, 2) * 1.0), 1)
    et0 = round(60 + _u(seed, 3) * 70, 1)
    p365_norm = round(520 + _u(seed, 6) * 160, 1)
    summers = [
        {"year": d.year - k, "kbw": round(-220 + _u(seed, 20 + k) * 200, 1), "precip": None}
        for k in range(1, 11)
    ]
    return _resp("Open-Meteo Historical Weather API (ERA5)", {
        "analysis_date": d.isoformat(),
        "precip_30d": precip,
        "et0_30d": et0,
        "kbw_30d": round(precip - et0, 1),
        "kbw_10y_percentile": round(_u(seed, 4) * 100, 1),
        "precip_30d_median_10y": normal,
        "dry_spell_days": int(_u(seed, 5) * 22),
        "temp_mean_30d": round(8 + _u(seed, 7) * 12, 1),
        "precip_365d": round(p365_norm * (0.75 + _u(seed, 8) * 0.45), 1),
        "precip_365d_median_prev": p365_norm,
        "kbw_summer_by_year": summers,
        "kbw_summer_mean_10y": round(sum(s["kbw"] for s in summers) / len(summers), 1),
        "precip_monthly": _sample_monthly(seed, d),
    })


# Typical Polish monthly precipitation (mm), Jan..Dec — shapes the sample rain histogram.
_PL_MONTHLY_MM = [35, 30, 35, 35, 55, 65, 80, 70, 50, 40, 40, 40]


def _sample_monthly(seed: int, d: date) -> list[dict[str, Any]]:
    out = []
    for back in range(11, -1, -1):
        m = d.year * 12 + d.month - 1 - back
        y, mo = m // 12, m % 12 + 1
        normal = round(_PL_MONTHLY_MM[mo - 1] * (0.85 + _u(seed, 40 + back) * 0.3), 1)
        frac = d.day / 31 if back == 0 else 1.0
        out.append({
            "month": f"{y:04d}-{mo:02d}",
            "precip": round(normal * frac * (0.3 + _u(seed, 60 + back) * 1.1), 1),
            "normal": round(normal * frac, 1),
            "years": 10,
            "partial": back == 0,
        })
    return out


def sample_soil(key: Any) -> dict[str, Any]:
    seed = _seed("soil", key)
    sand = round(20 + _u(seed, 1) * 60, 1)
    clay = round(min(5 + _u(seed, 2) * 25, 95 - sand), 1)
    soc = round(0.6 + _u(seed, 3) * 1.8, 2)
    awc = round(max(60.0, 210 - sand * 1.6 + clay * 0.8), 1)
    cls = "low" if awc < 110 else ("medium" if awc <= 155 else "high")
    return _resp("ISRIC SoilGrids 2.0", {
        "sand_pct": sand, "clay_pct": clay, "silt_pct": round(100 - sand - clay, 1), "soc_pct": soc,
        "awc_mm": awc, "awc_depth_cm": 100, "retention_class": cls,
    })


def sample_sat(key: Any, d: date) -> dict[str, Any]:
    seed = _seed("sat", key, d.isoformat())
    if _u(seed, 1) < 0.3:
        return _resp("Sentinel-2 L2A (Copernicus, AWS Earth Search)", {},
                     ["Brak czystego zdjęcia działki w ciągu 21 dni."])
    return _resp("Sentinel-2 L2A (Copernicus, AWS Earth Search)", {
        "ndvi_mean": round(0.2 + _u(seed, 2) * 0.6, 3),
        "ndmi_mean": round(-0.1 + _u(seed, 3) * 0.4, 3),
        "scene_date": d.isoformat(),
    })


def sample_drought(key: Any, d: date) -> dict[str, Any]:
    seed = _seed("drought", key, d.month)
    cls = seed % 4
    labels = ["brak sygnału suszy wg EDO", "Obserwacja (Watch)", "Ostrzeżenie (Warning)", "Alarm (Alert)"]
    return _resp("EDO Combined Drought Indicator (Copernicus EMS)", {
        "cdi_class": cls, "cdi_label": labels[cls], "dekad_start": d.replace(day=1).isoformat(),
    })


def make_sample_bundle(
    *,
    plot_id: str | None,
    lat: float | None,
    lng: float | None,
    analysis_date: date,
) -> AdapterBundle:
    plot = sample_plot(plot_id, lat, lng)
    key = plot["plotId"]
    return AdapterBundle(
        plot=plot,
        meteo=sample_meteo(key, analysis_date),
        soil=sample_soil(key),
        sat=sample_sat(key, analysis_date),
        drought=sample_drought(key, analysis_date),
        mode="live",
    )
