"""Bundle → flat facts → Evidence[] / Source[] / MissingData[].

Facts are plain numbers copied from adapter values (never invented; None = missing).
Every Evidence item points at a Source id, and every rule in the engine cites
Evidence ids — so each number in the report can be traced back to a public API.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any

from adapters.dates import shift_years
from adapters.licenses import license_for
from app.adapters.bundle import AdapterBundle
from app.crops.catalog import CropEntry, sensitivity_level
from app.schemas.evidence import Evidence, MissingData, Source

# Source ids used across Evidence.sourceId
SRC_ULDK = "uldk"
SRC_DEM = "dem"
SRC_HYDRO = "hydro"
SRC_LAND = "land_use"
SRC_METEO = "open_meteo"
SRC_SOIL = "soilgrids"
SRC_SAT = "sentinel2"
SRC_EDO = "edo"
SRC_ENGINE = "engine"
SRC_CROPS = "crop_table"

RUNOFF_PL = {"low": "niskie", "medium": "umiarkowane", "high": "wysokie"}
WATER_TYPE_PL = {
    "river": "rzeka", "stream": "strumień", "ditch": "rów", "drain": "rów melioracyjny",
    "canal": "kanał", "water": "zbiornik wodny",
}
RETENTION_CLASS_PL = {"low": "niska pojemność", "medium": "średnia pojemność", "high": "wysoka pojemność"}


def _num(v: Any) -> float | None:
    try:
        return None if v is None else float(v)
    except (TypeError, ValueError):
        return None


def fmt(x: float, digits: int = 1) -> str:
    """Polish number formatting for generated text (4.2 → '4,2')."""
    s = f"{x:.{digits}f}".rstrip("0").rstrip(".") if digits else f"{x:.0f}"
    return s.replace(".", ",")


@dataclass
class Facts:
    # meteo
    precip30: float | None = None
    precip30_normal: float | None = None
    kbw30: float | None = None
    kbw_pct: float | None = None
    dry_spell: float | None = None
    temp30: float | None = None
    precip365: float | None = None
    precip365_normal: float | None = None
    kbw_summer_mean: float | None = None
    summers: list[dict[str, Any]] = field(default_factory=list)
    # soil
    sand: float | None = None
    clay: float | None = None
    soc: float | None = None
    awc: float | None = None
    awc_class: str | None = None
    # terrain / hydro
    slope: float | None = None
    runoff: str | None = None
    nearby_water: bool | None = None
    water_dist: float | None = None
    water_type: str | None = None
    # land use (EGiB register only)
    land_category: str | None = None
    land_label: str | None = None
    land_source: str | None = None
    land_soil_classes: list[str] = field(default_factory=list)
    land_agri: bool | None = None
    # satellite / drought
    ndvi: float | None = None
    ndvi_date: str | None = None
    cdi: int | None = None
    cdi_label: str | None = None
    # crop
    crop_sens: float = 0.5

    @property
    def precip_ratio(self) -> float | None:
        if self.precip30 is None or not self.precip30_normal:
            return None
        return self.precip30 / self.precip30_normal

    @property
    def precip365_anomaly_pct(self) -> float | None:
        if self.precip365 is None or not self.precip365_normal:
            return None
        return (self.precip365 / self.precip365_normal - 1) * 100

    @property
    def dry_summers(self) -> tuple[int, int] | None:
        vals = [s["kbw"] for s in self.summers if s.get("kbw") is not None]
        if len(vals) < 3:
            return None
        return sum(v < DRY_SUMMER_KBW for v in vals), len(vals)


# Summer (VI–VIII) climatic water balance below this counts as a "dry summer".
DRY_SUMMER_KBW = -150.0


def extract_facts(bundle: AdapterBundle, crop: CropEntry) -> Facts:
    m = bundle.meteo.get("values") or {}
    s = bundle.soil.get("values") or {}
    sat = bundle.sat.get("values") or {}
    dr = bundle.drought.get("values") or {}
    terrain = bundle.plot.get("terrain") or {}
    hydro = bundle.plot.get("hydro") or {}
    lu = bundle.plot.get("landUse") or {}

    runoff = terrain.get("runoffRisk")
    cdi = dr.get("cdi_class")
    return Facts(
        precip30=_num(m.get("precip_30d")),
        precip30_normal=_num(m.get("precip_30d_median_10y")),
        kbw30=_num(m.get("kbw_30d")),
        kbw_pct=_num(m.get("kbw_10y_percentile")),
        dry_spell=_num(m.get("dry_spell_days")),
        temp30=_num(m.get("temp_mean_30d")),
        precip365=_num(m.get("precip_365d")),
        precip365_normal=_num(m.get("precip_365d_median_prev")),
        kbw_summer_mean=_num(m.get("kbw_summer_mean_10y")),
        summers=list(m.get("kbw_summer_by_year") or []),
        sand=_num(s.get("sand_pct")),
        clay=_num(s.get("clay_pct")),
        soc=_num(s.get("soc_pct")),
        awc=_num(s.get("awc_mm")),
        awc_class=s.get("retention_class"),
        slope=_num(terrain.get("slopePct")),
        runoff=runoff if runoff in ("low", "medium", "high") else None,
        nearby_water=hydro.get("nearbyWater") if not hydro.get("missing") else None,
        water_dist=_num(hydro.get("nearestDistanceM")),
        water_type=hydro.get("nearestType"),
        land_category=lu.get("category"),
        land_label=lu.get("labelPl"),
        land_source=lu.get("source"),
        land_soil_classes=list(lu.get("soilClasses") or []),
        land_agri=lu.get("isAgricultural"),
        ndvi=_num(sat.get("ndvi_mean")),
        ndvi_date=sat.get("scene_date"),
        cdi=int(cdi) if isinstance(cdi, (int, float)) else None,
        cdi_label=dr.get("cdi_label"),
        crop_sens=float(crop["droughtSensitivity"]),
    )


# --------------------------------------------------------------------------- evidence


def build_evidence(f: Facts, crop: CropEntry) -> list[Evidence]:
    ev: list[Evidence] = []

    def add(id_: str, label: str, value: float | str | None, src: str, unit: str | None = None,
            comparison: str | None = None) -> None:
        if value is None:
            return
        ev.append(Evidence(id=id_, label=label, value=value, unit=unit, comparison=comparison, sourceId=src))

    ratio = f.precip_ratio
    add("ev_precip_30d", "Opady w ostatnich 30 dniach", f.precip30, SRC_METEO, "mm",
        f"zwykle w tym okresie: {fmt(f.precip30_normal, 0)} mm ({fmt(ratio * 100, 0)}% normy)"
        if ratio is not None and f.precip30_normal is not None else None)
    add("ev_kbw_30d", "Bilans wodny 30 dni (opad minus parowanie)", f.kbw30, SRC_METEO, "mm",
        f"bardziej sucho było w {fmt(f.kbw_pct, 0)}% lat z ostatnich 10 (ten sam okres)"
        if f.kbw_pct is not None else None)
    add("ev_dry_spell", "Dni bez deszczu (do dnia oceny)", f.dry_spell, SRC_METEO, "dni",
        "liczone od dnia oceny wstecz, dzień suchy = opad < 1 mm")
    add("ev_temp_30d", "Średnia temperatura 30 dni", f.temp30, SRC_METEO, "°C")
    anom = f.precip365_anomaly_pct
    add("ev_precip_365d", "Opady w ostatnich 12 miesiącach", f.precip365, SRC_METEO, "mm",
        f"zwykle: {fmt(f.precip365_normal, 0)} mm ({'+' if anom >= 0 else ''}{fmt(anom, 0)}%)"
        if anom is not None and f.precip365_normal is not None else None)
    add("ev_kbw_summer", "Średni letni bilans wodny (VI–VIII, 10 lat)", f.kbw_summer_mean, SRC_METEO, "mm",
        "ujemny = latem więcej wody paruje, niż spada deszczu")
    ds = f.dry_summers
    if ds:
        add("ev_dry_summers", "Suche lata w ostatnich latach", f"{ds[0]} z {ds[1]}", SRC_METEO,
            comparison=f"lato z bilansem wodnym poniżej {fmt(DRY_SUMMER_KBW, 0)} mm")

    add("ev_soil_sand", "Udział piasku w glebie (0–30 cm)", f.sand, SRC_SOIL, "%")
    add("ev_soil_clay", "Udział iłu w glebie (0–30 cm)", f.clay, SRC_SOIL, "%")
    add("ev_soil_soc", "Węgiel organiczny (próchnica, 0–30 cm)", f.soc, SRC_SOIL, "%")
    add("ev_soil_awc", "Ile wody gleba może zatrzymać", f.awc, SRC_SOIL, "mm na 1 m gleby",
        f"{RETENTION_CLASS_PL.get(f.awc_class or '', 'szacunek')} (szacunek z tekstury gleby)")

    add("ev_slope", "Spadek terenu na działce", f.slope, SRC_DEM, "%",
        f"ryzyko spływu: {RUNOFF_PL[f.runoff]}" if f.runoff else None)
    if f.nearby_water is not None:
        if f.nearby_water:
            what = WATER_TYPE_PL.get(f.water_type or "", "ciek lub zbiornik")
            add("ev_water", "Najbliższa woda (rów, ciek, zbiornik)", f.water_dist, SRC_HYDRO, "m",
                f"{what} w promieniu 500 m")
        else:
            add("ev_water", "Woda w pobliżu działki", "nie znaleziono w promieniu 500 m", SRC_HYDRO,
                comparison="rowy mogą być niezmapowane – sprawdź na miejscu")

    if f.land_label:
        parts = ["z ewidencji gruntów (EGiB)"]
        if f.land_soil_classes:
            parts.append("klasa gleby " + ", ".join(f.land_soil_classes))
        if f.land_agri is False:
            parts.append("nie jest to pole, łąka, pastwisko ani sad")
        add("ev_land_use", "Rodzaj użytku na działce", f.land_label, SRC_LAND, comparison="; ".join(parts))

    add("ev_ndvi", "Kondycja roślin z satelity (NDVI)", f.ndvi, SRC_SAT,
        comparison=f"zdjęcie z {f.ndvi_date}; 0 = goła gleba, >0,6 = gęsta zieleń" if f.ndvi_date else None)
    if f.cdi is not None:
        add("ev_cdi", "Wskaźnik suszy w regionie (EDO)", f.cdi_label or str(f.cdi), SRC_EDO,
            comparison=f"klasa {f.cdi} w skali 0–3")

    add("ev_crop_sensitivity", "Wrażliwość uprawy na suszę",
        {"high": "wysoka", "medium": "średnia", "low": "niska"}[sensitivity_level(f.crop_sens)],
        SRC_CROPS, comparison=crop["criticalPhasePl"])
    return ev


# --------------------------------------------------------------------------- sources


def _status(coverage: str | None) -> str:
    return {"full": "ok", "partial": "partial"}.get(coverage or "", "failed")


def _providers(srcs: list[dict[str, Any]]) -> tuple[str | None, str | None, str | None, str | None]:
    """(provider names, first url, latest fetchedAt, license) from adapter source refs."""
    if not srcs:
        return None, None, None, None
    names = list(dict.fromkeys(s.get("name") for s in srcs if s.get("name")))
    url = next((s.get("url") for s in srcs if s.get("url")), None)
    fetched = max((s.get("fetchedAt") for s in srcs if s.get("fetchedAt")), default=None)
    lic = "; ".join(dict.fromkeys(filter(None, (license_for(n) for n in names)))) or None
    return " + ".join(names) or None, url, fetched, lic


def _from_resp(id_: str, name: str, resp: dict[str, Any], period: str | None) -> Source:
    provider, url, fetched, lic = _providers(resp.get("sources") or [])
    status = _status(resp.get("coverage"))
    return Source(
        id=id_, name=name, provider=provider, url=url, fetchedAt=fetched or resp.get("fetchedAt"),
        dataPeriod=period, mode="cached" if resp.get("fromCache") else "live", status=status,  # type: ignore[arg-type]
        license=lic, error="; ".join(resp.get("errors") or []) or None if status != "ok" else None,
    )


def build_sources(bundle: AdapterBundle, analysis_date: date) -> list[Source]:
    plot = bundle.plot
    psrc = plot.get("sources") or []
    pick = lambda *keys: [s for s in psrc if any(k in (s.get("name") or "") for k in keys)]  # noqa: E731
    terrain = plot.get("terrain") or {}
    hydro = plot.get("hydro") or {}
    notes = plot.get("missingData") or []
    note = lambda *pre: next((n for n in notes if n.startswith(pre)), None)  # noqa: E731

    out: list[Source] = []
    prov, url, fetched, lic = _providers(pick("ULDK"))
    out.append(Source(id=SRC_ULDK, name="Granice działki", provider=prov, url=url, fetchedAt=fetched,
                      mode="live", status="ok", license=lic, dataPeriod="stan ewidencji na dzień pobrania"))

    prov, url, fetched, lic = _providers(pick("NMT", "Elevation"))
    dem_status = "failed" if terrain.get("slopePct") is None else (
        "partial" if (terrain.get("resolutionM") or 0) >= 90 else "ok")
    out.append(Source(id=SRC_DEM, name="Ukształtowanie terenu", provider=prov or "GUGiK NMT", url=url,
                      fetchedAt=fetched, mode="live", status=dem_status, license=lic,  # type: ignore[arg-type]
                      dataPeriod=f"model terenu, siatka ~{terrain.get('resolutionM')} m"
                      if terrain.get("resolutionM") else None,
                      error=None if dem_status == "ok" else (
                          note("Ukształtowanie", "Spadek") or "nie udało się policzyć spadku terenu")))

    prov, url, fetched, lic = _providers(pick("OpenStreetMap"))
    hydro_ok = not hydro.get("missing")
    out.append(Source(id=SRC_HYDRO, name="Rowy, cieki i zbiorniki w pobliżu",
                      provider=prov or "OpenStreetMap (Overpass API)", url=url, fetchedAt=fetched, mode="live",
                      status="ok" if hydro_ok else "failed", license=lic or license_for("OpenStreetMap"),
                      error=None if hydro_ok else (note("Cieki") or str(hydro.get("missing")))))

    lu = plot.get("landUse")
    if lu is not None:  # None = context not computed (old cache / mock) → no source row
        prov, url, fetched, lic = _providers(pick("KIEG"))
        lu_ok = lu.get("category") is not None
        out.append(Source(
            id=SRC_LAND, name="Rodzaj użytku (ewidencja gruntów)",
            provider=prov or "GUGiK KIEG (EGiB)", url=url, fetchedAt=fetched, mode="live",
            status="ok" if lu_ok else "failed", license=lic or license_for("KIEG GUGiK"),
            dataPeriod=f"ewidencja gruntów EGiB, publikacja {(lu.get('egib') or {}).get('dataDate')}"
            if (lu.get("egib") or {}).get("dataDate") else None,
            error=None if lu_ok else ("; ".join(lu.get("notes") or []) or "brak danych o użytkowaniu")))

    mv = bundle.meteo.get("values") or {}
    start = shift_years(analysis_date, -10)
    out.append(_from_resp(SRC_METEO, "Pogoda (opady, parowanie, temperatura)", bundle.meteo,
                          f"{start.isoformat()} – {mv.get('analysis_date') or analysis_date.isoformat()}"))
    out.append(_from_resp(SRC_SOIL, "Gleba (skład, próchnica, pojemność wodna)", bundle.soil,
                          "model SoilGrids 2.0, siatka 250 m"))
    sv = bundle.sat.get("values") or {}
    out.append(_from_resp(SRC_SAT, "Zdjęcia satelitarne (kondycja roślin)", bundle.sat,
                          f"zdjęcie z {sv['scene_date']}" if sv.get("scene_date") else "21 dni przed dniem oceny"))
    dv = bundle.drought.get("values") or {}
    out.append(_from_resp(SRC_EDO, "Susza w regionie (Europejskie Obserwatorium Suszy)", bundle.drought,
                          f"dekada od {dv['dekad_start']}" if dv.get("dekad_start") else None))

    out.append(Source(id=SRC_ENGINE, name="Obliczenia własne", provider="Retencja – silnik reguł (deterministyczny)",
                      mode="static", status="ok"))
    out.append(Source(id=SRC_CROPS, name="Tabela wrażliwości upraw", provider="Retencja – tabela upraw",
                      mode="static", status="ok"))
    return out


# --------------------------------------------------------------------------- missing data

_MISSING_COPY: dict[str, tuple[str, str]] = {
    SRC_DEM: ("Ukształtowanie terenu (spadek)",
              "Nie oceniamy dokładnie spływu wody z pola – zalecenia przeciw spływowi są ostrożniejsze."),
    SRC_HYDRO: ("Rowy i cieki w pobliżu",
                "Nie wiemy, czy przy działce jest rów – zalecenie retencji w rowie sprawdź na miejscu."),
    SRC_LAND: ("Rodzaj użytku z ewidencji gruntów (pole, łąka, las…)",
               "Nie potwierdzamy, czy to pole, łąka czy inny użytek – sprawdź, czy wybrana uprawa "
               "zgadza się ze stanem faktycznym."),
    SRC_METEO: ("Dane pogodowe",
                "Bez opadów i parowania ocena wilgotności jest mniej pewna."),
    SRC_SOIL: ("Dane o glebie",
               "Nie znamy pojemności wodnej gleby – ocena zakłada glebę przeciętną i ma niższą pewność."),
    SRC_SAT: ("Zdjęcie satelitarne",
              "Brak sprawdzenia kondycji roślin z satelity – ocena opiera się na pogodzie i glebie."),
    SRC_EDO: ("Wskaźnik suszy w regionie",
              "Brak porównania z regionalną mapą suszy – nie zmienia to głównych wniosków."),
}


def build_missing(sources: list[Source]) -> list[MissingData]:
    out: list[MissingData] = []
    for s in sources:
        if s.status == "ok" or s.id not in _MISSING_COPY:
            continue
        what, impact = _MISSING_COPY[s.id]
        if s.status == "partial":
            what += " – częściowo"
        out.append(MissingData(id=f"missing_{s.id}", what=what,
                               reason=s.error or "źródło nie odpowiedziało", impact=impact))
    return out
