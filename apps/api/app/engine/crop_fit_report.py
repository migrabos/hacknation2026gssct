"""Separate report: which crops cope best with the water on this plot (POST /crop-fit).

Independent of the water report: no crop is chosen, nothing here changes the moisture
assessment or the retention recommendations. Same AdapterBundle, same Evidence/Source
conventions, so every number still traces back to a public source.
Only multi-year conditions are used (soil, 10-year climate, terrain, register) — the current
season (satellite NDVI, regional drought index, last 30 days) is deliberately left out.
"""

from __future__ import annotations

import hashlib
from datetime import date, datetime, timezone

from app.adapters.bundle import AdapterBundle
from app.config import get_settings
from app.engine.crop_fit import rank_crop_fit
from app.engine.facts import (
    SRC_CROPS, SRC_DEM, SRC_ENGINE, SRC_HYDRO, SRC_LAND, SRC_METEO, SRC_SOIL, SRC_ULDK,
    build_evidence, build_sources, extract_facts,
)
from app.plot_dto import plot_to_dto
from app.schemas.evidence import CropFitReport, MissingData, ReportMeta, Source

# Evidence the crop-fit report can show (multi-year / static plot properties only).
FIT_EVIDENCE = {
    "ev_soil_awc", "ev_soil_sand", "ev_soil_clay", "ev_soil_soc",
    "ev_kbw_summer", "ev_dry_summers", "ev_precip_365d",
    "ev_slope", "ev_water", "ev_land_use",
}
FIT_SOURCES = (SRC_ULDK, SRC_DEM, SRC_HYDRO, SRC_LAND, SRC_METEO, SRC_SOIL, SRC_ENGINE, SRC_CROPS)

# What a missing source means for THIS report (the water report has its own wording).
_FIT_MISSING: dict[str, tuple[str, str]] = {
    SRC_SOIL: ("Dane o glebie (skład, pojemność wodna)",
               "Nie wiemy, ile wody gleba zatrzyma dla korzeni — porównanie upraw opiera się na klimacie, "
               "terenie i ewidencji gruntów i jest mniej pewne."),
    SRC_METEO: ("Pogoda z ostatnich 10 lat",
                "Nie wiemy, jak suche są tu lata — porównanie zakłada przeciętne warunki i jest mniej pewne."),
    SRC_DEM: ("Spadek terenu",
              "Nie oceniamy ryzyka spływu i erozji dla upraw rzędowych."),
    SRC_HYDRO: ("Rowy i cieki w pobliżu",
                "Ryzyko zastoisk wody oceniamy tylko na podstawie gleby."),
    SRC_LAND: ("Rodzaj użytku i klasa gleby z ewidencji gruntów",
               "Jakość gleby szacujemy z modelu SoilGrids zamiast z urzędowej klasy; nie sprawdzamy, czy to "
               "trwały użytek zielony."),
}

FIT_LIMITATIONS = [
    "Porównanie upraw opiera się na warunkach wieloletnich (gleba, pogoda z 10 lat, teren, ewidencja "
    "gruntów), a nie na stanie upraw w bieżącym sezonie.",
    "Pojemność wodna gleby jest szacowana z modelu SoilGrids (siatka 250 m) – lokalnie gleba może się różnić.",
    "Wymagania upraw to wartości orientacyjne z literatury (FAO-56, FAO-33, grupy upraw IUNG-PIB), "
    "a punktacja to jawna heurystyka – nie zastępuje porady doradcy rolnego.",
]


def _report_id(plot_id: str, analysis_date: date) -> str:
    raw = f"crop-fit|{plot_id}|{analysis_date.isoformat()}"
    return f"c-{analysis_date.isoformat()}-{hashlib.sha256(raw.encode()).hexdigest()[:10]}"


def _missing(sources: list[Source]) -> list[MissingData]:
    out = []
    for s in sources:
        if s.status == "ok" or s.id not in _FIT_MISSING:
            continue
        what, impact = _FIT_MISSING[s.id]
        out.append(MissingData(id=f"missing_{s.id}", what=what + (" – częściowo" if s.status == "partial" else ""),
                               reason=s.error or "źródło nie odpowiedziało", impact=impact))
    return out


def run_crop_fit_report(*, bundle: AdapterBundle, analysis_date: date, duration_ms: int = 0) -> CropFitReport:
    if not bundle.plot or not bundle.plot.get("centroid"):
        raise RuntimeError("Brak lokalizacji działki — porównanie upraw niemożliwe.")

    f = extract_facts(bundle, None)
    fit = rank_crop_fit(f)

    evidence = [e for e in build_evidence(f, None) if e.id in FIT_EVIDENCE]
    ev_ids = {e.id for e in evidence}
    if fit:
        for item in fit.ranking:
            item.evidenceRefs = [r for r in item.evidenceRefs if r in ev_ids]

    sources = [s for s in build_sources(bundle, analysis_date) if s.id in FIT_SOURCES]
    missing = _missing(sources)

    limitations = list(FIT_LIMITATIONS)
    if fit is None:
        label = f.land_label or "teren nierolniczy"
        limitations.insert(0, f"UWAGA: w ewidencji gruntów ta działka to {label} — nie porównujemy upraw "
                              "na terenie, który nie jest polem, łąką, pastwiskiem ani sadem.")

    settings = get_settings()
    return CropFitReport(
        reportId=_report_id(bundle.plot["plotId"], analysis_date),
        status="partial" if missing else "complete",
        plot=plot_to_dto(bundle.plot),
        analysisDate=analysis_date.isoformat(),
        generatedAt=datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        cropFit=fit,
        evidence=evidence,
        sources=sources,
        limitations=limitations,
        missingData=missing,
        meta=ReportMeta(engineVersion=settings.engine_version, adapters=bundle.mode, durationMs=duration_ms),
    )
