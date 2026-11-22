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
from app.crops.catalog import NO_CROP_ID, CropEntry, sensitivity_level
from app.crops.fao import FAO_SOURCE_NAME, FAO_SOURCE_URL, fao_note
from app.crops.smsr import (
    SMSR_SOURCE_NAME,
    SMSR_SOURCE_URL,
    SmsrMatch,
    SmsrWindowStat,
    crop_not_indicated,
    evaluate_smsr,
    smsr_history,
    soil_cat_label,
    soil_category_from_awc,
)
from app.schemas.evidence import Evidence, MissingData, Source

# Source ids used across Evidence.sourceId
SRC_ULDK = "uldk"
SRC_DEM = "dem"
SRC_HYDRO = "hydro"
SRC_LAND = "land_use"
SRC_METEO = "open_meteo"
SRC_SOIL = "soilgrids"
SRC_SAT = "sentinel2"
SRC_SAT_HIST = "sentinel2_history"
SRC_EDO = "edo"
SRC_ENGINE = "engine"
SRC_CROPS = "crop_table"
SRC_FAO = "fao_ky"
SRC_SMSR = "smsr_kbw"
SRC_IUNG_SOIL = "iung_soil"

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


def sm_rank_pl(pct: float) -> str:
    """How unusual the soil water is vs the last 10 years, in farmer language."""
    if pct <= 0:
        return "tak sucho nie było w żadnym z ostatnich 10 lat"
    if pct >= 100:
        return "tak mokro nie było w żadnym z ostatnich 10 lat"
    return f"bardziej sucho było w {fmt(pct, 0)}% z ostatnich 10 lat"


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
    kbw60: float | None = None
    kbw_pct: float | None = None
    dry_spell: float | None = None
    temp30: float | None = None
    et0_30d: float | None = None        # reference evapotranspiration, 30 days (FAO-56)
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
    awc_depth_cm: float | None = None
    # terrain / hydro
    slope: float | None = None
    slope_method: str | None = None     # "plane_fit" | "two_points"
    slope_points: int | None = None
    runoff: str | None = None
    # lowest NMT point of the plot (natural spot for a pond); drop is None when no spot suggested
    spot_drop: float | None = None
    spot_near_edge: bool | None = None
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
    ndvi_median: float | None = None
    ndmi: float | None = None
    bare_pct: float | None = None       # % of clear plot pixels with NDVI < 0.2 (bare soil / stubble)
    water_pct: float | None = None      # % of clear plot pixels classified as water by ESA (SCL)
    weak_pct: float | None = None       # % of plot clearly weaker than the plot median (NDVI − 0.15)
    ndmi_dry_pct: float | None = None   # % of green pixels with NDMI < 0
    hist_ndvi: float | None = None      # median NDVI, same 21-day window, previous years
    hist_ndmi: float | None = None
    hist_n: int = 0
    hist_years: list[int] = field(default_factory=list)
    cdi: int | None = None
    cdi_label: str | None = None
    # crop / SMSR / FAO
    crop_sens: float = 0.5
    crop_id: str | None = None
    crop_kc: float | None = None          # mid-season Kc (FAO-56)
    crop_kc_ini: float | None = None      # early-season Kc
    crop_season: tuple[int, ...] = ()
    crop_critical: tuple[int, ...] = ()
    crop_phase_pl: str | None = None
    fao_ky: float | None = None           # strictly FAO-33, else None
    ky_from_fao: bool = False
    effective_ky: float | None = None     # FAO or assumed
    fao_note: str | None = None
    analysis_date: date | None = None
    smsr: SmsrMatch | None = None
    month: int | None = None            # month of the analysis date (set by run_engine)
    area_ha: float | None = None
    # soil water from the reanalysis land model (Open-Meteo / ERA5-Land), 0–100 cm, % of volume
    sm_root: float | None = None
    sm_top: float | None = None
    sm_date: str | None = None
    sm_median: float | None = None
    sm_pct: float | None = None         # % of the last 10 years that were drier on the same days
    sm_note: str | None = None
    # IUNG SMSR soil category (map) + 10-year history of the SMSR windows
    iung_cat: int | None = None         # 1–4 from the IUNG map (None = not agricultural / no map)
    iung_cat_share: float | None = None
    iung_label: str | None = None       # what the map shows when there is no category (forest, organic…)
    iung_organic: bool = False
    soil_cat: int | None = None         # category actually used (IUNG map, else AWC proxy)
    soil_cat_source: str | None = None  # "iung_map" | "awc"
    crop_not_on_soil: bool = False      # regulation: crop not indicated on this soil category
    smsr_hist: list[SmsrWindowStat] = field(default_factory=list)
    kbw_monthly: list[dict[str, Any]] = field(default_factory=list)
    # runoff estimate inputs: daily rain ≥ 3 mm on non-frozen days, last 10 years
    rain_days: list[float] = field(default_factory=list)
    rain_years: int = 0
    precip_year: float | None = None
    # set by run_engine (derived, deterministic): risk period + runoff estimate
    risk: Any = None
    runoff_est: Any = None

    @property
    def in_season(self) -> bool | None:
        if self.month is None or not self.crop_season:
            return None
        return self.month in self.crop_season

    @property
    def in_critical_phase(self) -> bool | None:
        if self.month is None or not self.crop_critical:
            return None
        return self.month in self.crop_critical

    @property
    def crop_kc_effective(self) -> float | None:
        """Kc for the analysis month: mid in critical phase, ini early/late in season."""
        if self.crop_kc is None:
            return None
        if self.in_critical_phase:
            return self.crop_kc
        if self.in_season:
            ini = self.crop_kc_ini if self.crop_kc_ini is not None else self.crop_kc * 0.4
            # Development / late: midpoint between ini and mid (simple FAO-56 stage proxy).
            return round((ini + self.crop_kc) / 2, 2)
        return self.crop_kc_ini if self.crop_kc_ini is not None else self.crop_kc * 0.4

    @property
    def crop_water_need30(self) -> float | None:
        """Crop water need for the last 30 days ≈ ET0 × Kc_phase (FAO-56)."""
        kc = self.crop_kc_effective
        if self.et0_30d is None or kc is None:
            return None
        return self.et0_30d * kc

    @property
    def crop_deficit30(self) -> float | None:
        """Water the crop needed minus rain that fell, last 30 days (> 0 = shortage)."""
        need = self.crop_water_need30
        if need is None or self.precip30 is None:
            return None
        return need - self.precip30

    @property
    def scene_month(self) -> int | None:
        try:
            return int(self.ndvi_date[5:7]) if self.ndvi_date else None
        except ValueError:
            return None

    @property
    def has_history(self) -> bool:
        return self.hist_n >= MIN_HISTORY_YEARS

    @property
    def history_comparable(self) -> bool:
        """Past years are a fair baseline only if the canopy then looked like now.

        A big NDVI jump usually means a different crop (crop rotation) or a different
        growth stage, not a wetter/drier year -> NDMI anomaly is then not used.
        """
        if not self.has_history or self.ndvi is None or self.hist_ndvi is None:
            return False
        return self.hist_ndvi >= 0.3 and abs(self.ndvi - self.hist_ndvi) <= MAX_NDVI_GAP

    @property
    def ndmi_anomaly(self) -> float | None:
        """Current NDMI minus this plot's median for the same window in previous years."""
        if self.ndmi is None or self.hist_ndmi is None or not self.history_comparable:
            return None
        return self.ndmi - self.hist_ndmi

    @property
    def ndvi_anomaly(self) -> float | None:
        if self.ndvi is None or self.hist_ndvi is None or not self.has_history:
            return None
        return self.ndvi - self.hist_ndvi

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
# Satellite baseline needs at least this many previous years with a clear scene.
MIN_HISTORY_YEARS = 3
MAX_NDVI_GAP = 0.2  # |NDVI now − typical NDVI| above this = likely another crop → no NDMI comparison
# Pixel shares worth showing as evidence (below = noise / field edges).
SHOW_BARE_PCT = 10.0
SHOW_WATER_PCT = 2.0
SHOW_WEAK_PCT = 10.0
# Shown in limitations (not missingData) when the multi-year satellite baseline is unavailable:
# it is an optional refinement, so its absence must not flag the whole report as incomplete.
NO_SAT_HISTORY_NOTE = (
    "Nie porównaliśmy zdjęcia satelitarnego z poprzednimi latami (za mało czystych zdjęć z tego okresu "
    "lub są jeszcze pobierane). Ocena wilgotności i tak nie zależy od tego porównania – służy tylko "
    "jako dodatkowy komentarz, gdy dane już są w pamięci podręcznej."
)


def extract_facts(
    bundle: AdapterBundle,
    crop: CropEntry | None,
    analysis_date: date | None = None,
) -> Facts:
    """`crop=None` keeps crop facts neutral (crop_sens 0.5, no season / Kc)."""
    m = bundle.meteo.get("values") or {}
    s = bundle.soil.get("values") or {}
    sat = bundle.sat.get("values") or {}
    dr = bundle.drought.get("values") or {}
    hist = (bundle.sat_history or {}).get("values") or {}
    terrain = bundle.plot.get("terrain") or {}
    hydro = bundle.plot.get("hydro") or {}
    spot = terrain.get("retentionSpot") or {}
    lu = bundle.plot.get("landUse") or {}
    iung = (bundle.iung_soil or {}).get("values") or {}

    runoff = terrain.get("runoffRisk")
    cdi = dr.get("cdi_class")
    awc = _num(s.get("awc_mm"))
    kbw60 = _num(m.get("kbw_60d"))
    ad = analysis_date
    if ad is None and m.get("analysis_date"):
        try:
            ad = date.fromisoformat(str(m["analysis_date"]))
        except ValueError:
            ad = None
    iung_cat = iung.get("category") if iung.get("category") in (1, 2, 3, 4) else None
    iung_organic = iung_cat is None and iung.get("dominant_code") == 5
    # Organic soils have no SMSR thresholds → never replaced by the AWC proxy.
    soil_cat = iung_cat or (None if iung_organic else soil_category_from_awc(awc))
    soil_src = "iung_map" if iung_cat else ("awc" if soil_cat else None)
    smsr = (
        evaluate_smsr(crop_id=crop["id"], analysis_date=ad, kbw_60d=kbw60, awc_mm=awc, soil_cat=iung_cat)
        if crop and ad and not iung_organic else None
    )
    rain = m.get("rain_events_10y") or {}
    return Facts(
        precip30=_num(m.get("precip_30d")),
        precip30_normal=_num(m.get("precip_30d_median_10y")),
        kbw30=_num(m.get("kbw_30d")),
        kbw60=kbw60,
        kbw_pct=_num(m.get("kbw_10y_percentile")),
        dry_spell=_num(m.get("dry_spell_days")),
        temp30=_num(m.get("temp_mean_30d")),
        et0_30d=_num(m.get("et0_30d")),
        precip365=_num(m.get("precip_365d")),
        precip365_normal=_num(m.get("precip_365d_median_prev")),
        kbw_summer_mean=_num(m.get("kbw_summer_mean_10y")),
        summers=list(m.get("kbw_summer_by_year") or []),
        sand=_num(s.get("sand_pct")),
        clay=_num(s.get("clay_pct")),
        soc=_num(s.get("soc_pct")),
        awc=awc,
        awc_class=s.get("retention_class"),
        awc_depth_cm=_num(s.get("awc_depth_cm")),
        slope=_num(terrain.get("slopePct")),
        slope_method=terrain.get("slopeMethod"),
        slope_points=terrain.get("pointsSampled"),
        spot_drop=_num(spot.get("elevationDropM")) if spot.get("lat") is not None else None,
        spot_near_edge=spot.get("nearEdge") if spot.get("lat") is not None else None,
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
        ndvi_median=_num(sat.get("ndvi_median")),
        ndmi=_num(sat.get("ndmi_mean")),
        bare_pct=_num(sat.get("bare_soil_pct")),
        water_pct=_num(sat.get("water_pct")),
        weak_pct=_num(sat.get("weak_zone_pct")),
        ndmi_dry_pct=_num(sat.get("ndmi_dry_pct")),
        hist_ndvi=_num(hist.get("ndvi_median")),
        hist_ndmi=_num(hist.get("ndmi_median")),
        hist_n=int(hist.get("n_years") or 0),
        hist_years=[int(y["year"]) for y in hist.get("years") or [] if y.get("year")],
        cdi=int(cdi) if isinstance(cdi, (int, float)) else None,
        cdi_label=dr.get("cdi_label"),
        crop_sens=float(crop["droughtSensitivity"]) if crop else 0.5,
        crop_id=crop["id"] if crop else None,
        crop_kc=float(crop["kcMid"]) if crop else None,
        crop_kc_ini=float(crop["kcIni"]) if crop else None,
        crop_season=tuple(crop["seasonMonths"]) if crop else (),
        crop_critical=tuple(crop["criticalMonths"]) if crop else (),
        crop_phase_pl=crop["criticalPhasePl"] if crop else None,
        fao_ky=crop.get("faoKy") if crop else None,
        ky_from_fao=bool(crop.get("kyFromFao")) if crop else False,
        effective_ky=crop.get("effectiveKy") if crop else None,
        fao_note=fao_note(crop["id"]) if crop else None,
        analysis_date=ad,
        smsr=smsr,
        area_ha=_num(bundle.plot.get("areaHa")),
        sm_root=_num(m.get("soil_moisture_root_pct")),
        sm_top=_num(m.get("soil_moisture_top_pct")),
        sm_date=m.get("soil_moisture_date"),
        sm_median=_num(m.get("soil_moisture_root_median_10y")),
        sm_pct=_num(m.get("soil_moisture_percentile_10y")),
        sm_note=m.get("soil_moisture_note"),
        iung_cat=iung_cat,
        iung_cat_share=_num(iung.get("category_share_pct")),
        iung_label=iung.get("dominant_label"),
        iung_organic=iung_organic,
        soil_cat=soil_cat,
        soil_cat_source=soil_src,
        crop_not_on_soil=bool(crop and crop_not_indicated(crop["id"], soil_cat)),  # type: ignore[arg-type]
        smsr_hist=smsr_history(crop["id"], soil_cat, m.get("kbw_smsr_windows") or []) if crop else [],  # type: ignore[arg-type]
        kbw_monthly=list(m.get("kbw_monthly_10y") or []),
        rain_days=[float(x) for x in rain.get("days") or []],
        rain_years=int(rain.get("years") or 0),
        precip_year=_num(rain.get("precip_mean_year")),
    )


# --------------------------------------------------------------------------- evidence


def build_evidence(f: Facts, crop: CropEntry | None) -> list[Evidence]:
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
    add("ev_kbw_60d", "Bilans wodny 60 dni (okno SMSR)", f.kbw60, SRC_METEO, "mm",
        "opad minus parowanie; porównywany z progiem IUNG SMSR dla uprawy i gleby")
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
    depth = f.awc_depth_cm
    awc_unit = ("mm na 1 m gleby" if depth is None or depth >= 100
                else f"mm na {fmt(depth, 0)} cm gleby")
    add("ev_soil_awc", "Ile wody gleba może zatrzymać", f.awc, SRC_SOIL, awc_unit,
        f"{RETENTION_CLASS_PL.get(f.awc_class or '', 'szacunek')} (szacunek z tekstury gleby)")
    if f.soil_cat is not None:
        if f.soil_cat_source == "iung_map":
            share = f" (ok. {fmt(f.iung_cat_share, 0)}% powierzchni działki)" if f.iung_cat_share is not None \
                and f.iung_cat_share < 95 else ""
            add("ev_soil_category", "Kategoria gleby wg IUNG (podatność na suszę)",
                f"kat. {soil_cat_label(f.soil_cat)}", SRC_IUNG_SOIL,  # type: ignore[arg-type]
                comparison=f"mapa kategorii glebowych IUNG-PIB użyta w monitoringu suszy{share}; "
                           "I = bardzo podatna, IV = mało podatna")
        else:
            add("ev_soil_category", "Kategoria gleby (podatność na suszę) – oszacowana",
                f"kat. {soil_cat_label(f.soil_cat)}", SRC_SOIL,  # type: ignore[arg-type]
                comparison="brak mapy IUNG dla działki – przypisana z pojemności wodnej gleby wg granic IUNG "
                           "(I < 127,5 mm, II do 170 mm, III do 202,5 mm, IV więcej)")
    elif f.iung_organic:
        add("ev_soil_category", "Kategoria gleby wg IUNG", "gleba organiczna", SRC_IUNG_SOIL,
            comparison="torfy i gleby murszowe – IUNG nie podaje dla nich progów suszy")
    if f.sm_root is not None:
        parts = [f"stan na {f.sm_date} (średnia 7 dni, warstwa korzeni 0–100 cm)"]
        if f.sm_median is not None:
            parts.append(f"zwykle o tej porze: {fmt(f.sm_median)}%")
        if f.sm_pct is not None:
            parts.append(sm_rank_pl(f.sm_pct))
        parts.append("model reanalizy ERA5-Land (siatka ok. 9 km), nie pomiar w polu")
        add("ev_soil_moisture", "Wilgotność gleby (model)", f.sm_root, SRC_METEO, "% objętości", "; ".join(parts))

    slope_cmp = [f"ryzyko spływu: {RUNOFF_PL[f.runoff]}"] if f.runoff else []
    if f.slope_method == "plane_fit" and f.slope_points:
        slope_cmp.append(f"średni spadek całej działki z {f.slope_points} punktów wysokości")
    add("ev_slope", "Spadek terenu na działce", f.slope, SRC_DEM, "%", "; ".join(slope_cmp) or None)
    if f.spot_drop is not None:
        add("ev_low_spot", "Najniższe miejsce działki (zbiera wodę)", f.spot_drop, SRC_DEM, "m niżej",
            "niż najwyższy punkt działki; zaznaczone na mapie" + ("; leży przy granicy działki"
                                                                 if f.spot_near_edge else ""))
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

    def typical(x: float | None, check: bool = False) -> str:
        if x is None or not f.has_history:
            return ""
        out = f"; zwykle o tej porze roku na tej działce: {fmt(x, 2)} (mediana {f.hist_n} lat)"
        if check and not f.history_comparable:
            out += " – nie porównujemy, bo wtedy pole wyglądało inaczej (inna uprawa lub faza)"
        return out

    scene = f"zdjęcie z {f.ndvi_date}" if f.ndvi_date else "zdjęcie satelitarne"
    off_season = ""
    if f.crop_season and f.scene_month is not None and f.scene_month not in f.crop_season:
        off_season = ("; zdjęcie poza sezonem wzrostu wybranej uprawy – zieleń może pochodzić z innej rośliny "
                      "(np. międzyplonu lub oziminy), a jej brak jest wtedy normalny")
    add("ev_ndvi", "Kondycja roślin z satelity (NDVI)", f.ndvi, SRC_SAT,
        comparison=f"{scene}; 0 = goła gleba, >0,6 = gęsta zieleń{typical(f.hist_ndvi)}{off_season}")
    add("ev_ndmi", "Woda w roślinach z satelity (NDMI)", f.ndmi, SRC_SAT,
        comparison=f"{scene}; poniżej 0 = rośliny mają mało wody, powyżej 0,3 = dobrze nawodnione"
                   f"{typical(f.hist_ndmi, check=True)}")
    if f.bare_pct is not None and f.bare_pct >= SHOW_BARE_PCT:
        add("ev_bare_soil", "Goła gleba na działce (z satelity)", round(f.bare_pct), SRC_SAT, "% działki",
            f"{scene}; piksele 10×10 m bez zielonej okrywy (NDVI < 0,2)")
    if f.water_pct is not None and f.water_pct >= SHOW_WATER_PCT:
        add("ev_standing_water", "Woda stojąca na działce (z satelity)", round(f.water_pct), SRC_SAT, "% działki",
            f"{scene}; piksele sklasyfikowane przez ESA jako woda – zastoisko lub podmokłe miejsce")
    if f.weak_pct is not None and f.weak_pct >= SHOW_WEAK_PCT:
        add("ev_weak_zone", "Słabsza część pola (z satelity)", round(f.weak_pct), SRC_SAT, "% działki",
            f"{scene}; rośliny wyraźnie słabsze niż na reszcie pola (NDVI niższy o ponad 0,15)")
    if f.cdi is not None:
        add("ev_cdi", "Wskaźnik suszy w regionie (EDO)", f.cdi_label or str(f.cdi), SRC_EDO,
            comparison=f"klasa {f.cdi} w skali 0–3")

    if crop and crop["id"] != NO_CROP_ID:
        ky_cmp = f.fao_note or crop["criticalPhasePl"]
        if f.ky_from_fao and f.fao_ky is not None:
            add("ev_fao_ky", "Współczynnik odpowiedzi plonu na deficyt wody (FAO Ky)",
                f.fao_ky, SRC_FAO, comparison=ky_cmp)
        elif f.effective_ky is not None:
            add("ev_fao_ky", "Wrażliwość uprawy na niedobór wody (przyjęta)",
                f.effective_ky, SRC_CROPS, comparison=ky_cmp)
        add("ev_crop_sensitivity", "Wrażliwość uprawy na suszę",
            {"high": "wysoka", "medium": "średnia", "low": "niska"}[sensitivity_level(f.crop_sens)],
            SRC_FAO if f.ky_from_fao else SRC_CROPS,
            comparison=f"{ky_cmp}; {crop['criticalPhasePl']}")
        if f.smsr is not None:
            sm = f.smsr
            verdict = ("poniżej orientacyjnego progu IUNG (ok. 20% ryzyka spadku plonu w metodyce SMSR)"
                       if sm.below_threshold
                       else "powyżej orientacyjnego progu IUNG (bez sygnału suszy rolniczej w tym przybliżeniu)")
            soil_src = "z mapy IUNG" if sm.soil_source == "iung_map" else "oszacowana z pojemności wodnej"
            add("ev_smsr_threshold", "Orientacyjny próg bilansu wodnego (IUNG SMSR)",
                sm.threshold_mm, SRC_SMSR, "mm",
                f"okres {sm.period_label}, gleba kat. {soil_cat_label(sm.soil_cat)} ({soil_src}); "
                f"bilans 60 dni = {fmt(sm.kbw_60d_mm, 0)} mm → {verdict}. "
                "To przybliżenie (ET0 z Open-Meteo, gleba do 1 m) – nie oficjalne orzeczenie SMSR.")
        rw = f.risk
        if rw is not None and rw.peakLabel:
            if rw.method == "smsr":
                add("ev_risk_window", "Kiedy najczęściej brakuje wody (10 lat)", rw.peakLabel, SRC_SMSR,
                    comparison=f"w {rw.yearsHit} z {rw.yearsTotal} lat bilans wodny tego okresu spadł poniżej "
                               f"progu suszy IUNG dla tej uprawy na glebie kat. {soil_cat_label(f.soil_cat)}")  # type: ignore[arg-type]
        deficit, need = f.crop_deficit30, f.crop_water_need30
        kc_eff = f.crop_kc_effective
        if deficit is not None and need is not None and deficit > 0 and kc_eff is not None:
            phase = ("faza krytyczna" if f.in_critical_phase
                     else "wczesna/późna faza sezonu" if f.in_season else "poza szczytem zapotrzebowania")
            add("ev_crop_deficit", "Niedobór wody dla uprawy (30 dni)", round(deficit), SRC_ENGINE,
                "l/m² (= mm)",
                f"uprawa potrzebowała ok. {fmt(need, 0)} mm (parowanie {fmt(f.et0_30d, 0)} mm × współczynnik "
                f"uprawy {fmt(kc_eff, 2)} wg FAO-56, {phase}; ok. {fmt(need / 30)} mm dziennie), "
                f"a spadło {fmt(f.precip30, 0)} mm")
    rw = f.risk
    if rw is not None and rw.method == "kbw_monthly" and rw.peakLabel:
        add("ev_risk_window", "Kiedy najczęściej brakuje wody (10 lat)", rw.peakLabel, SRC_METEO,
            comparison="miesiące z najbardziej ujemnym bilansem wodnym (mediana z 10 lat)")
    ro = f.runoff_est
    if ro is not None:
        add("ev_runoff_volume", "Woda spływająca z działki po ulewach", ro.volume_year_m3, SRC_ENGINE, "m³ na rok",
            f"średnio {fmt(ro.runoff_year_mm)} mm z {fmt(ro.precip_year_mm, 0)} mm opadu rocznie; metoda SCS-CN "
            f"(USDA), CN = {ro.cn} ({ro.cover_pl}, gleba grupy {ro.hsg}); opady dzienne z 10 lat")
        if ro.pond_m3 is not None:
            add("ev_pond_volume", "Pojemność oczka na typową ulewę", ro.pond_m3, SRC_ENGINE, "m³",
                f"spływ z ulewy, która zdarza się średnio raz na 2 lata ({fmt(ro.storm_rain_mm, 0)} mm deszczu "
                f"→ {fmt(ro.storm_runoff_mm)} mm spływu z całej działki)")
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
    if bundle.sat_history is not None:  # None = not fetched (tests) → no row
        hv = bundle.sat_history.get("values") or {}
        yrs = sorted(int(y["year"]) for y in hv.get("years") or [] if y.get("year"))
        src = _from_resp(SRC_SAT_HIST, "Zdjęcia satelitarne z poprzednich lat (ten sam okres)", bundle.sat_history,
                         f"lata {', '.join(map(str, yrs))} – po 21 dni przed tym samym dniem" if yrs else None)
        if 0 < len(yrs) < MIN_HISTORY_YEARS:  # too few years to call it "normal" → not used
            src.status = "partial"
            src.error = (f"tylko {len(yrs)} lat z czystym zdjęciem (potrzeba {MIN_HISTORY_YEARS})"
                         + ("; " + src.error if src.error else ""))
        elif len(yrs) >= MIN_HISTORY_YEARS and src.status == "partial":
            # Enough years for a baseline: a cloudy year is a note, not missing data.
            skipped = int(hv.get("years_requested") or len(yrs)) - len(yrs)
            src.status, src.error = "ok", None
            if skipped:
                src.dataPeriod = (f"{src.dataPeriod} (brak czystego zdjęcia z {skipped} "
                                  f"{'roku' if skipped == 1 else 'lat'})")
        out.append(src)
    if bundle.iung_soil is not None:  # None = not fetched (tests) → no row
        out.append(_from_resp(SRC_IUNG_SOIL, "Kategoria gleby (mapa IUNG-PIB)", bundle.iung_soil,
                              "mapa kategorii podatności gleb na suszę (warstwa 2024), piksel ~10 m"))
    dv = bundle.drought.get("values") or {}
    out.append(_from_resp(SRC_EDO, "Susza w regionie (Europejskie Obserwatorium Suszy)", bundle.drought,
                          f"dekada od {dv['dekad_start']}" if dv.get("dekad_start") else None))

    out.append(Source(id=SRC_ENGINE, name="Obliczenia własne", provider="Retencja – silnik reguł (deterministyczny)",
                      mode="static", status="ok"))
    out.append(Source(
        id=SRC_FAO, name="Wrażliwość uprawy (FAO Ky)",
        provider=FAO_SOURCE_NAME, url=FAO_SOURCE_URL, mode="static", status="ok",
        license="FAO – publikacja otwarta; cytowanie FAO Irrigation & Drainage Paper 33",
        dataPeriod="Doorenbos & Kassam 1979 (sezonowe Ky)",
    ))
    out.append(Source(
        id=SRC_SMSR, name="Progi suszy rolniczej (IUNG SMSR)",
        provider=SMSR_SOURCE_NAME, url=SMSR_SOURCE_URL, mode="static", status="ok",
        license="MRiRW / IUNG-PIB – wartości z rozporządzenia Dz.U. 2019 poz. 739",
        dataPeriod="okna sześciodekadowe 21 III – 30 IX",
    ))
    out.append(Source(id=SRC_CROPS, name="Katalog upraw (grupy SMSR)",
                      provider="Retencja – mapowanie grup IUNG SMSR → FAO Ky",
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
    SRC_IUNG_SOIL: ("Kategoria gleby z mapy IUNG",
                    "Kategorię gleby do progów suszy oszacowaliśmy z modelu SoilGrids – jest mniej pewna."),
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
