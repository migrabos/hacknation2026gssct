"""Assemble Report from adapter bundle — pure deterministic pipeline."""

from __future__ import annotations

from datetime import date
from typing import Any

from app.adapters.mocks import MockAdapterBundle
from app.config import get_settings
from app.crops.catalog import get_crop
from app.engine.assess import assess_moisture
from app.engine.causes import detect_causes
from app.engine.rank import rank_recommendations
from app.schemas.evidence import (
    Centroid,
    CropInfo,
    HydroInfo,
    PlotInfo,
    Report,
    ReportMeta,
    Source,
    TerrainInfo,
)


def _merge_sources(bundle: MockAdapterBundle) -> list[Source]:
    out: list[Source] = []
    seen: set[str] = set()
    for part in (
        bundle.plot,
        bundle.meteo,
        bundle.soil,
        bundle.sat,
        bundle.drought,
        bundle.hydro,
    ):
        for s in part.sources:
            sid = str(s.get("id") or s.get("name") or id(s))
            if sid in seen:
                continue
            seen.add(sid)
            out.append(
                Source(
                    id=sid,
                    name=str(s.get("name") or sid),
                    url=s.get("url"),
                    fetchedAt=part.fetchedAt.isoformat(),
                    coverage=s.get("coverage") or part.coverage,
                )
            )
    return out


def _missing_data(bundle: MockAdapterBundle) -> list[str]:
    missing: list[str] = []
    if bundle.sat.values.get("ndviAnomaly") is None:
        missing.append("Anomalia NDVI niedostępna (stub satelitarny).")
    if not bundle.drought.values.get("iungClass"):
        missing.append("Klasa suszy IUNG niedostępna (best-effort).")
    if bundle.plot.values.get("geometry") is None:
        missing.append("Pełna geometria działki niedostępna.")
    for part_name, part in (
        ("plot", bundle.plot),
        ("meteo", bundle.meteo),
        ("soil", bundle.soil),
        ("sat", bundle.sat),
        ("drought", bundle.drought),
        ("hydro", bundle.hydro),
    ):
        for err in part.errors:
            missing.append(f"{part_name}: {err}")
    return missing


def run_engine(
    *,
    bundle: MockAdapterBundle,
    crop_id: str,
    analysis_date: date,
    duration_ms: int = 0,
) -> Report:
    """Build Evidence Report. Raises RuntimeError if assessment cannot run."""
    plot_v = bundle.plot.values or {}
    meteo_v = bundle.meteo.values or {}
    soil_v = bundle.soil.values or {}

    if not plot_v and not meteo_v:
        raise RuntimeError(
            "Brak danych działki i meteo — nie można wykonać oceny wilgoci."
        )
    if not meteo_v:
        raise RuntimeError(
            "Brak danych meteorologicznych — ocena wilgoci niemożliwa."
        )
    if not plot_v.get("centroid"):
        raise RuntimeError(
            "Brak lokalizacji działki (centroid) — ocena niemożliwa."
        )

    crop = get_crop(crop_id)
    missing = _missing_data(bundle)
    uncertainty_flags = list(missing)

    assessment = assess_moisture(
        meteo=meteo_v,
        soil=soil_v,
        sat=bundle.sat.values or {},
        drought=bundle.drought.values or {},
        crop_sensitivity=float(crop["droughtSensitivity"]),
        missing_flags=uncertainty_flags[:3],
    )

    terrain = plot_v.get("terrain") or {}
    causes = detect_causes(
        assessment=assessment,
        meteo=meteo_v,
        soil=soil_v,
        terrain=terrain if isinstance(terrain, dict) else {},
        crop_sensitivity=float(crop["droughtSensitivity"]),
    )

    hydro_v: dict[str, Any] = {}
    if isinstance(plot_v.get("hydro"), dict):
        hydro_v.update(plot_v["hydro"])
    hydro_v.update(bundle.hydro.values or {})

    recommendations = rank_recommendations(
        assessment=assessment,
        causes=causes,
        terrain=terrain if isinstance(terrain, dict) else {},
        hydro=hydro_v,
        crop_sensitivity=float(crop["droughtSensitivity"]),
    )

    centroid_raw = plot_v["centroid"]
    centroid = Centroid(lat=float(centroid_raw["lat"]), lng=float(centroid_raw["lng"]))

    terrain_info = None
    if isinstance(terrain, dict) and terrain:
        terrain_info = TerrainInfo(
            slopePct=terrain.get("slopePct"),
            runoffRisk=terrain.get("runoffRisk"),
        )

    hydro_info = HydroInfo(
        nearbyWater=hydro_v.get("nearbyWater"),
        distanceClass=hydro_v.get("distanceClass"),
    )

    settings = get_settings()
    limitations = [
        "Silnik używa uproszczonych progów wodnych (proxy), nie pełnego modelu hydrologicznego.",
        "Adaptery są mockami do czasu podłączenia żywych źródeł danych (Person 2).",
        "Rekomendacje to wskazówki retencyjne/agrotechniczne, nie decyzja administracyjna.",
    ]

    return Report(
        plot=PlotInfo(
            plotId=plot_v.get("plotId"),
            centroid=centroid,
            areaHa=plot_v.get("areaHa"),
            geometry=plot_v.get("geometry"),
            voivodeship=plot_v.get("voivodeship"),
            terrain=terrain_info,
            hydro=hydro_info,
        ),
        crop=CropInfo(
            id=crop["id"],
            namePl=crop["namePl"],
            droughtSensitivity=float(crop["droughtSensitivity"]),
        ),
        analysisDate=analysis_date,
        moistureAssessment=assessment,
        causes=causes,
        recommendations=recommendations,
        sources=_merge_sources(bundle),
        limitations=limitations,
        missingData=missing,
        narrative=None,
        meta=ReportMeta(
            engineVersion=settings.engine_version,
            llmEnabled=settings.llm_enabled,
            llmModel=settings.ollama_model if settings.llm_enabled else None,
            durationMs=duration_ms,
        ),
    )
