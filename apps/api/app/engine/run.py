"""Assemble Report from an AdapterBundle — pure deterministic pipeline (except generatedAt)."""

from __future__ import annotations

import hashlib
from datetime import date, datetime, timezone

from app.adapters.bundle import AdapterBundle
from app.config import get_settings
from app.crops.catalog import NO_CROP_ID, ORCHARD_CROPS, get_crop, sensitivity_level
from app.engine.assess import assess_moisture
from app.engine.causes import detect_causes
from app.engine.facts import NO_SAT_HISTORY_NOTE, build_evidence, build_missing, build_sources, extract_facts
from app.engine.rank import rank_recommendations
from app.engine.risk_window import compute_risk_window
from app.engine.runoff import estimate_runoff
from app.plot_dto import plot_to_dto
from app.schemas.evidence import Crop, MissingData, PrecipMonth, Report, ReportMeta

ENGINE_LIMITATIONS = [
    "Ocena wilgotności to prosty bilans wodny (opady, parowanie, gleba) z jawnymi progami – nie pomiar "
    "wilgotności w polu ani pełny model hydrologiczny.",
    "Kategorie upraw są z IUNG SMSR (MRiRW 2019), z opcją „Brak uprawy”. Wrażliwość bierze Ky z FAO-33 "
    "tam, gdzie jest w tabeli; dla pozostałych upraw podajemy wartość przyjętą (nie „FAO”). Porównanie "
    "z progami SMSR używa bilansu 60 dni z Open-Meteo (ET0 FAO-56) i gleby do 1 m – to przybliżenie, "
    "nie oficjalne orzeczenie suszy IUNG.",
    "Pojemność wodna gleby jest szacowana z modelu SoilGrids (siatka 250 m, punkt w środku działki) "
    "i mapowana na kategorie glebowe SMSR – lokalnie gleba może się różnić.",
    "Rowy i cieki bierzemy z OpenStreetMap (nie z MPHP Wód Polskich) – niezmapowany rów wygląda jak "
    "„brak wody w pobliżu”; sprawdź w terenie.",
    "Zalecenia to wskazówki retencyjne i agrotechniczne dopasowane do użytku z EGiB, nie decyzja "
    "administracyjna. Budowa zbiornika czy zastawki może wymagać zgłoszenia wodnoprawnego.",
]


SAT_LIMITATION = (
    "Zdjęcie satelitarne (Sentinel-2, piksel 10 m) pokazuje zieleń roślin i wodę w liściach, "
    "a nie wilgotność gleby. Interpretacja uwzględnia typową zieleń dla wybranej uprawy i miesiąca. "
    "Porównanie z poprzednimi latami (gdy dostępne) nie wchodzi do oceny punktowej – dzięki temu "
    "ten sam raport nie zmienia wyniku przy ponownym uruchomieniu. Woda stojąca to klasyfikacja ESA – "
    "bardzo mokra, ciemna gleba może być wzięta za wodę."
)

SOIL_MOISTURE_LIMITATION = (
    "Wilgotność gleby pochodzi z modelu reanalizy ERA5-Land (Copernicus, siatka ok. 9 km, przez Open-Meteo), "
    "a nie z czujnika w polu. Dobrze pokazuje, czy jest sucho na tle 10 lat w okolicy, ale nie zna "
    "konkretnej gleby i uprawy na działce."
)
RUNOFF_LIMITATION = (
    "Spływ wody i pojemność oczka liczymy metodą SCS-CN (USDA) z dziennych opadów z 10 lat. To szacunek "
    "orientacyjny: pomija roztopy i zamarzniętą glebę, zakłada, że cała woda z działki spływa w jedno miejsce. "
    "Przed budową zbiornika potrzebny jest pomiar w terenie i ewentualne zgłoszenie wodnoprawne."
)

_GRASS_LAND = {"meadow", "pasture"}


def _crop_land_use_mismatch(crop_id: str, crop_name: str, land_use: dict) -> str | None:
    """Warn when the chosen SMSR crop does not fit the plot's land use (agricultural land only;
    non-agricultural plots already get a stronger warning from the plot resolver)."""
    if crop_id == NO_CROP_ID:
        return None
    cat, label = land_use.get("category"), land_use.get("labelPl")
    if not cat or not land_use.get("isAgricultural") or cat == "mixed":
        return None
    src = "w ewidencji gruntów (EGiB)"
    if cat in _GRASS_LAND:
        return (f"UWAGA: działka {src} to {label}. SMSR nie ma kategorii łąka/pastwisko – wybrano "
                f"„{crop_name}” tylko jako przybliżenie. Zaorywanie trwałych użytków zielonych może być "
                "ograniczone przepisami (ochrona TUZ w ramach WPR).")
    if cat == "orchard" and crop_id not in ORCHARD_CROPS:
        return (f"UWAGA: wybrano „{crop_name}”, a działka {src} to {label}. Dla sadu / plantacji "
                "lepiej wybrać drzewa owocowe, krzewy owocowe lub truskawki (kategorie SMSR).")
    # No warning for fruit trees / berries / strawberries on "grunt orny": plantations very often keep
    # the R entry in EGiB, and the engine already follows the chosen crop (no ploughing / cover-crop
    # advice, orchard runoff), so the warning only confused farmers without changing anything.
    return None


def _report_id(plot_id: str, crop_id: str, analysis_date: date) -> str:
    raw = f"{plot_id}|{crop_id}|{analysis_date.isoformat()}"
    return f"r-{analysis_date.isoformat()}-{hashlib.sha256(raw.encode()).hexdigest()[:10]}"


def _precip_monthly(bundle: AdapterBundle) -> list[PrecipMonth]:
    rows = (bundle.meteo.get("values") or {}).get("precip_monthly") or []
    out = []
    for r in rows:
        try:
            out.append(PrecipMonth(
                month=str(r["month"]), precipMm=r.get("precip"), normalMm=r.get("normal"),
                normalYears=int(r.get("years") or 0), partial=bool(r.get("partial")),
            ))
        except Exception:
            continue
    return out


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
    f = extract_facts(bundle, crop, analysis_date)
    f.month = analysis_date.month
    f.risk = compute_risk_window(f)
    f.runoff_est = estimate_runoff(f)

    assessment = assess_moisture(f)  # raises without meteo
    assessment.susceptibility.riskWindow = f.risk
    causes = detect_causes(assessment=assessment, f=f)
    recommendations = rank_recommendations(assessment=assessment, causes=causes, f=f)

    evidence = build_evidence(f, crop)
    ev_ids = {e.id for e in evidence}

    # Refs may only point at evidence that actually exists in this report.
    def keep(refs: list[str]) -> list[str]:
        return [r for r in dict.fromkeys(refs) if r in ev_ids]

    for block in (assessment.current, assessment.susceptibility):
        block.evidenceRefs = keep(block.evidenceRefs)
    if assessment.susceptibility.riskWindow is not None:
        assessment.susceptibility.riskWindow.evidenceRefs = keep(assessment.susceptibility.riskWindow.evidenceRefs)
    for c in causes:
        c.evidenceRefs = keep(c.evidenceRefs)
    for bucket in (recommendations.retention, recommendations.agrotech, recommendations.irrigation or []):
        for r in bucket:
            r.evidenceRefs = keep(r.evidenceRefs)

    sources = build_sources(bundle, analysis_date)
    missing = build_missing(sources)
    if assessment.susceptibility.level == "insufficient_data":
        missing.append(MissingData(
            id="missing_summer_history", what="Historia letniego bilansu wodnego",
            reason=assessment.susceptibility.summary,
            impact="Brak podstaw do określenia wieloletniej podatności działki na suszę.",
        ))
    if assessment.current.level == "insufficient_data":
        missing.append(MissingData(
            id="missing_moisture_comparison", what="Dane do oceny bieżącej wilgotności",
            reason="Brakuje porównania opadów lub bilansu wodnego z poprzednimi latami.",
            impact="Podajemy dostępne wartości bez oceny bieżącej wilgotności.",
        ))

    limitations = list(bundle.plot.get("limitations") or []) + ENGINE_LIMITATIONS
    if f.nearby_water is None or (f.nearby_water and (not f.water_type or f.water_dist is None)):
        limitations.append("Sprawdź w terenie, czy przy działce jest rów odprowadzający wodę z pola.")
    if f.sm_root is not None:
        limitations.append(SOIL_MOISTURE_LIMITATION)
    elif f.sm_note:
        limitations.append(f"Wilgotność gleby z modelu nie została użyta: {f.sm_note}")
    if f.soil_cat_source == "awc":
        limitations.append("Mapa kategorii gleb IUNG nie dała kategorii dla tej działki – kategorię do progów suszy "
                           "oszacowaliśmy z pojemności wodnej gleby (SoilGrids, 1 m profilu; IUNG liczy do 1,5 m).")
    if f.iung_organic:
        limitations.append("Według mapy IUNG działka leży na glebie organicznej (torf, mursz) – rozporządzenie nie "
                           "podaje dla niej progów suszy, więc porównania z progami IUNG nie robimy.")
    if f.crop_not_on_soil:
        limitations.insert(0, f"UWAGA: według rozporządzenia MRiRW (progi IUNG) uprawa „{crop['namePl']}” nie jest "
                              "wskazana na glebie tej kategorii – nie podajemy dla niej progu suszy.")
    if f.runoff_est is not None:
        limitations.append(RUNOFF_LIMITATION)
    if f.ndvi is not None:
        limitations.append(SAT_LIMITATION)
        if bundle.sat_history is not None and not f.has_history:
            limitations.append(NO_SAT_HISTORY_NOTE)
    mismatch = _crop_land_use_mismatch(crop_id, crop["namePl"], bundle.plot.get("landUse") or {})
    if mismatch:
        limitations.insert(0, mismatch)

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
        precipMonthly=_precip_monthly(bundle),
        sources=sources,
        limitations=limitations,
        missingData=missing,
        narrative=None,
        meta=ReportMeta(
            engineVersion=settings.engine_version,
            adapters=bundle.mode,
            durationMs=duration_ms,
        ),
    )
