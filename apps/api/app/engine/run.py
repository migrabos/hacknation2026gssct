"""Assemble Report from an AdapterBundle — pure deterministic pipeline (except generatedAt)."""

from __future__ import annotations

import hashlib
from datetime import date, datetime, timezone

from app.adapters.bundle import AdapterBundle
from app.config import get_settings
from app.crops.catalog import get_crop, sensitivity_level
from app.engine.assess import assess_moisture
from app.engine.causes import detect_causes
from app.engine.facts import build_evidence, build_missing, build_sources, extract_facts
from app.engine.rank import rank_recommendations
from app.plot_dto import plot_to_dto
from app.schemas.evidence import Crop, Report, ReportMeta

ENGINE_LIMITATIONS = [
    "Ocena wilgotności to prosty bilans wodny (opady, parowanie, gleba) z jawnymi progami – nie pomiar "
    "wilgotności w polu ani pełny model hydrologiczny.",
    "Pojemność wodna gleby jest szacowana z modelu SoilGrids (siatka 250 m) – lokalnie gleba może się różnić.",
    "Zalecenia to wskazówki retencyjne i agrotechniczne, nie decyzja administracyjna. Budowa zbiornika czy "
    "zastawki może wymagać zgłoszenia wodnoprawnego.",
]


_GRASS_LAND = {"meadow", "pasture"}
GRASS_CROP = "uzytki_zielone"


def _crop_land_use_mismatch(crop_id: str, crop_name: str, land_use: dict) -> str | None:
    """Warn when the chosen crop does not fit the plot's land use (only for agricultural land;
    non-agricultural plots already get a stronger warning from the plot resolver)."""
    cat, label = land_use.get("category"), land_use.get("labelPl")
    if not cat or not land_use.get("isAgricultural") or cat == "mixed":
        return None
    src = "w ewidencji gruntów (EGiB)"
    if crop_id == GRASS_CROP and cat in ("arable", "orchard"):
        return (f"UWAGA: wybrano „{crop_name}”, a działka {src} to {label}. Sprawdź, czy wybór uprawy jest "
                "właściwy – zalecenia zależą od uprawy.")
    if crop_id != GRASS_CROP and cat in _GRASS_LAND:
        return (f"UWAGA: wybrano uprawę „{crop_name}”, a działka {src} to {label}. Jeśli to trwały użytek "
                "zielony, wybierz „Łąka / pastwisko” – zaorywanie trwałych użytków zielonych może być "
                "ograniczone przepisami (ochrona TUZ w ramach WPR).")
    return None


def _report_id(plot_id: str, crop_id: str, analysis_date: date) -> str:
    raw = f"{plot_id}|{crop_id}|{analysis_date.isoformat()}"
    return f"r-{analysis_date.isoformat()}-{hashlib.sha256(raw.encode()).hexdigest()[:10]}"


def run_engine(
    *,
    bundle: AdapterBundle,
    crop_id: str,
    analysis_date: date,
    duration_ms: int = 0,
) -> Report:
    """Build the Evidence Report. Raises RuntimeError if the assessment cannot run."""
    if not bundle.plot or not bundle.plot.get("centroid"):
        raise RuntimeError("Brak lokalizacji działki — ocena niemożliwa.")

    crop = get_crop(crop_id)
    f = extract_facts(bundle, crop)

    assessment = assess_moisture(f)  # raises without meteo
    causes = detect_causes(assessment=assessment, f=f)
    recommendations = rank_recommendations(assessment=assessment, causes=causes, f=f)

    evidence = build_evidence(f, crop)
    ev_ids = {e.id for e in evidence}

    # Refs may only point at evidence that actually exists in this report.
    def keep(refs: list[str]) -> list[str]:
        return [r for r in dict.fromkeys(refs) if r in ev_ids]

    for block in (assessment.current, assessment.susceptibility):
        block.evidenceRefs = keep(block.evidenceRefs)
    for c in causes:
        c.evidenceRefs = keep(c.evidenceRefs)
    for bucket in (recommendations.retention, recommendations.agrotech, recommendations.irrigation or []):
        for r in bucket:
            r.evidenceRefs = keep(r.evidenceRefs)

    sources = build_sources(bundle, analysis_date)
    missing = build_missing(sources)

    limitations = list(bundle.plot.get("limitations") or []) + ENGINE_LIMITATIONS
    mismatch = _crop_land_use_mismatch(crop_id, crop["namePl"], bundle.plot.get("landUse") or {})
    if mismatch:
        limitations.insert(0, mismatch)
    if bundle.mode == "mock":
        limitations.insert(0, "TRYB DEMO: dane są przykładowe (generowane), nie pochodzą z prawdziwych źródeł.")

    settings = get_settings()
    return Report(
        reportId=_report_id(bundle.plot["plotId"], crop_id, analysis_date),
        status="partial" if missing else "complete",
        plot=plot_to_dto(bundle.plot),
        crop=Crop(id=crop["id"], name=crop["namePl"], droughtSensitivity=sensitivity_level(crop["droughtSensitivity"])),
        analysisDate=analysis_date.isoformat(),
        generatedAt=datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        moistureAssessment=assessment,
        causes=causes,
        recommendations=recommendations,
        evidence=evidence,
        sources=sources,
        limitations=limitations,
        missingData=missing,
        narrative=None,
        meta=ReportMeta(
            engineVersion=settings.engine_version,
            adapters=bundle.mode,
            llmEnabled=settings.llm_enabled,
            llmModel=settings.ollama_model if settings.llm_enabled else None,
            durationMs=duration_ms,
        ),
    )
