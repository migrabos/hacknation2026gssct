"""Meteo adapter: 10 years of daily precipitation / ET0 / temperature at the plot.

Sources (tried in order, all free, no key):
  1. Open-Meteo Historical Weather API (ERA5 / ERA5-Land reanalysis)   – primary
  2. NASA POWER daily point API (MERRA-2 + CERES)                       – fallback when
     Open-Meteo fails (e.g. "Daily API request limit exceeded" on a shared hackathon IP).
     ET0 is then computed here with FAO-56 Penman-Monteith (same method Open-Meteo uses).
  3. Open-Meteo Forecast API (past_days=10)                             – fills the last
     days that reanalysis archives have not published yet (ERA5 lag ≈ 2–5 days).

Outputs only simple, verifiable statistics (sums, a percentile, a dry-spell count).
Interpreting them ("is this drought?") belongs to the engine.

Set OPEN_METEO_API_KEY to use the paid customer endpoint instead of the free one.
"""

from __future__ import annotations

import math
from calendar import monthrange
import os
from datetime import date, datetime, timedelta
from statistics import median
from typing import Any
from zoneinfo import ZoneInfo

import httpx

from .base import PartialResult, run_adapter
from .dates import shift_years, today_pl  # noqa: F401 — re-exported for callers of this module

ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
POWER_URL = "https://power.larc.nasa.gov/api/temporal/daily/point"

_API_KEY = os.environ.get("OPEN_METEO_API_KEY")
if _API_KEY:  # paid tier: separate hosts, no shared daily limit
    ARCHIVE_URL = "https://customer-archive-api.open-meteo.com/v1/archive"
    FORECAST_URL = "https://customer-api.open-meteo.com/v1/forecast"

DAILY_VARS = "precipitation_sum,et0_fao_evapotranspiration,temperature_2m_mean"
# Volumetric soil water (m³/m³) of the reanalysis land model, daily means of three layers.
SOIL_VARS = "soil_moisture_0_to_7cm_mean,soil_moisture_7_to_28cm_mean,soil_moisture_28_to_100cm_mean"
SOIL_LAYERS_CM = (7.0, 21.0, 72.0)  # thickness of 0–7, 7–28, 28–100 cm
POWER_PARAMS = "PRECTOTCORR,T2M,T2M_MAX,T2M_MIN,ALLSKY_SFC_SW_DWN,RH2M,WS2M"
TZ = ZoneInfo("Europe/Warsaw")

YEARS_BACK = 10
WINDOW_30 = 30
WINDOW_60 = 60
DRY_DAY_MM = 1.0
RECENT_DAYS = 7  # analysis dates this close to today get a short cache TTL
FORECAST_PAST_DAYS = 10

SOIL_WINDOW = 7          # days averaged for the soil-moisture reading (smooths single rain days)
SOIL_MAX_LAG = 10        # reanalysis lag: use the latest day up to this many days before the analysis date
RAIN_EVENT_MIN_MM = 3.0  # daily rain listed for the runoff (SCS-CN) estimate – smaller never runs off

# IUNG SMSR six-dekad windows (start, end) as (month, day) – same as app/crops/smsr.PERIODS.
SMSR_WINDOWS: tuple[tuple[tuple[int, int], tuple[int, int]], ...] = (
    ((3, 21), (5, 20)), ((4, 1), (5, 31)), ((4, 11), (6, 10)), ((4, 21), (6, 20)),
    ((5, 1), (6, 30)), ((5, 11), (7, 10)), ((5, 21), (7, 20)), ((6, 1), (7, 31)),
    ((6, 11), (8, 10)), ((6, 21), (8, 20)), ((7, 1), (8, 31)), ((7, 11), (9, 10)),
    ((7, 21), (9, 20)), ((8, 1), (9, 30)),
)

HTTP_TIMEOUT = httpx.Timeout(15.0, connect=5.0)

# One day of data: (precipitation mm, ET0 mm, mean temperature °C); None = missing.
Day = list  # [p, et0, t]
# One day of soil water: (0–28 cm, 0–100 cm) volumetric m³/m³; None = missing.
SoilDay = tuple


# --------------------------------------------------------------------------- dates


def parse_date(value: date | str) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value).strip()[:10])


# --------------------------------------------------------------------------- FAO-56 ET0


def et0_fao56(
    tmax: float, tmin: float, tmean: float, rs_mj: float, rh: float, u2: float,
    elevation_m: float, lat_deg: float, doy: int,
) -> float:
    """Daily reference evapotranspiration, FAO-56 Penman-Monteith (Allen et al. 1998), mm/day."""
    p = 101.3 * ((293.0 - 0.0065 * elevation_m) / 293.0) ** 5.26
    gamma = 0.000665 * p

    def e0(t: float) -> float:
        return 0.6108 * math.exp(17.27 * t / (t + 237.3))

    es = (e0(tmax) + e0(tmin)) / 2
    ea = max(0.0, min(rh, 100.0)) / 100.0 * es
    delta = 4098 * e0(tmean) / (tmean + 237.3) ** 2

    phi = math.radians(lat_deg)
    dr = 1 + 0.033 * math.cos(2 * math.pi * doy / 365)
    dec = 0.409 * math.sin(2 * math.pi * doy / 365 - 1.39)
    ws = math.acos(max(-1.0, min(1.0, -math.tan(phi) * math.tan(dec))))
    ra = 24 * 60 / math.pi * 0.0820 * dr * (
        ws * math.sin(phi) * math.sin(dec) + math.cos(phi) * math.cos(dec) * math.sin(ws)
    )
    rso = (0.75 + 2e-5 * elevation_m) * ra
    rns = 0.77 * rs_mj
    ratio = min(rs_mj / rso, 1.0) if rso > 0 else 0.5
    rnl = 4.903e-9 * ((tmax + 273.16) ** 4 + (tmin + 273.16) ** 4) / 2 * (
        0.34 - 0.14 * math.sqrt(ea)
    ) * (1.35 * ratio - 0.35)
    rn = rns - rnl
    et0 = (0.408 * delta * rn + gamma * 900 / (tmean + 273) * u2 * (es - ea)) / (
        delta + gamma * (1 + 0.34 * u2)
    )
    return max(0.0, et0)


# --------------------------------------------------------------------------- fetchers


def _om_error(r: httpx.Response) -> str:
    try:
        reason = r.json().get("reason")
    except Exception:
        reason = None
    return f"HTTP {r.status_code}" + (f": {reason}" if reason else "")


def _parse_om_daily(body: dict[str, Any]) -> dict[date, Day]:
    d = body["daily"]
    return {
        date.fromisoformat(t): [p, e, tm]
        for t, p, e, tm in zip(
            d["time"], d["precipitation_sum"], d["et0_fao_evapotranspiration"], d["temperature_2m_mean"]
        )
    }


def _layer_mean(vals: tuple[float | None, ...], thick: tuple[float, ...]) -> float | None:
    if any(v is None for v in vals):
        return None
    return sum(v * t for v, t in zip(vals, thick)) / sum(thick)


def _parse_om_soil(body: dict[str, Any]) -> dict[date, SoilDay]:
    """Thickness-weighted soil water of 0–28 cm (topsoil) and 0–100 cm (root zone)."""
    d = body.get("daily") or {}
    cols = [d.get(v) for v in SOIL_VARS.split(",")]
    if not d.get("time") or any(c is None for c in cols):
        return {}
    out: dict[date, SoilDay] = {}
    for t, a, b, c in zip(d["time"], *cols):
        out[date.fromisoformat(t)] = (_layer_mean((a, b), SOIL_LAYERS_CM[:2]),
                                      _layer_mean((a, b, c), SOIL_LAYERS_CM))
    return out


# Pin the reanalysis so the 10-year baseline compares the same model family across years
# (default best_match can splice different models). era5_seamless = ERA5 + ERA5-Land.
ARCHIVE_MODEL = "era5_seamless"


async def _fetch_archive(client: httpx.AsyncClient, lat: float, lng: float, start: date, end: date
                         ) -> tuple[dict[date, Day], dict[date, SoilDay]]:
    params: dict[str, Any] = {
        "latitude": lat, "longitude": lng, "start_date": start.isoformat(), "end_date": end.isoformat(),
        "daily": f"{DAILY_VARS},{SOIL_VARS}", "timezone": "Europe/Warsaw",
        "models": ARCHIVE_MODEL,
    }
    if _API_KEY:
        params["apikey"] = _API_KEY
    r = await client.get(ARCHIVE_URL, params=params)
    if r.status_code != 200:
        raise RuntimeError(f"Open-Meteo Archive {_om_error(r)}")
    body = r.json()
    return _parse_om_daily(body), _parse_om_soil(body)


async def _fetch_forecast_recent(client: httpx.AsyncClient, lat: float, lng: float) -> dict[date, Day]:
    params: dict[str, Any] = {
        "latitude": lat, "longitude": lng, "daily": DAILY_VARS,
        "past_days": FORECAST_PAST_DAYS, "forecast_days": 1, "timezone": "Europe/Warsaw",
    }
    if _API_KEY:
        params["apikey"] = _API_KEY
    r = await client.get(FORECAST_URL, params=params)
    if r.status_code != 200:
        raise RuntimeError(f"Open-Meteo Forecast {_om_error(r)}")
    return _parse_om_daily(r.json())


async def _fetch_power(client: httpx.AsyncClient, lat: float, lng: float, start: date, end: date) -> dict[date, Day]:
    r = await client.get(POWER_URL, params={
        "parameters": POWER_PARAMS, "community": "AG", "latitude": lat, "longitude": lng,
        "start": start.strftime("%Y%m%d"), "end": end.strftime("%Y%m%d"), "format": "JSON",
    })
    if r.status_code != 200:
        raise RuntimeError(f"NASA POWER HTTP {r.status_code}")
    body = r.json()
    fill = body.get("header", {}).get("fill_value", -999.0)
    elev = float(body["geometry"]["coordinates"][2])
    par = body["properties"]["parameter"]

    def val(name: str, key: str) -> float | None:
        v = par[name].get(key)
        return None if v is None or v == fill else float(v)

    out: dict[date, Day] = {}
    for key in par["PRECTOTCORR"]:
        d = datetime.strptime(key, "%Y%m%d").date()
        p, t = val("PRECTOTCORR", key), val("T2M", key)
        tx, tn, rs, rh, u2 = (val(n, key) for n in ("T2M_MAX", "T2M_MIN", "ALLSKY_SFC_SW_DWN", "RH2M", "WS2M"))
        et0 = None
        if None not in (tx, tn, t, rs, rh, u2):
            et0 = round(et0_fao56(tx, tn, t, rs, rh, u2, elev, lat, d.timetuple().tm_yday), 2)
        out[d] = [p, et0, t]
    return out


# --------------------------------------------------------------------------- metrics


def _window(series: dict[date, Day], end: date, days: int) -> list[Day | None]:
    return [series.get(end - timedelta(days=i)) for i in range(days)]


def _sum(rows: list[Day | None], idx: int) -> float | None:
    vals = [r[idx] if r else None for r in rows]
    return None if any(v is None for v in vals) else sum(vals)


def _kbw(series: dict[date, Day], end: date, days: int) -> float | None:
    rows = _window(series, end, days)
    p, e = _sum(rows, 0), _sum(rows, 1)
    return None if p is None or e is None else round(p - e, 1)


def compute_metrics(series: dict[date, Day], d: date,
                    soil: dict[date, SoilDay] | None = None) -> tuple[dict[str, Any], list[str]]:
    """Pure function: daily series (+ soil water) + analysis date -> metrics and honest warnings."""
    errors: list[str] = []
    w30 = _window(series, d, WINDOW_30)

    p30, e30 = _sum(w30, 0), _sum(w30, 1)
    temps = [r[2] if r else None for r in w30]
    t30 = None if any(t is None for t in temps) else round(sum(temps) / len(temps), 1)
    kbw30 = _kbw(series, d, WINDOW_30)
    kbw60 = _kbw(series, d, WINDOW_60)
    missing30 = sum(1 for r in w30 if not r or None in r[:2])
    if missing30:
        errors.append(f"Brak kompletnych danych meteo dla {missing30} z ostatnich 30 dni – "
                      "sumy 30-dniowe nie zostały policzone (bez zgadywania).")
    elif kbw60 is None:
        errors.append("Brak kompletnych danych dla okna 60 dni – KBW 60 dni niepoliczony.")

    # Dry spell: consecutive days with P < 1 mm going back from the analysis date.
    dry, cursor = 0, d
    while True:
        row = series.get(cursor)
        if row is None or row[0] is None:
            dry = None if dry == 0 else dry
            if dry is not None:
                errors.append(f"Seria dni bez opadu przerwana brakiem danych – co najmniej {dry} dni.")
            break
        if row[0] >= DRY_DAY_MM:
            break
        dry += 1
        cursor -= timedelta(days=1)

    # Same 30-day calendar window in each of the previous 10 years.
    prev: list[dict[str, Any]] = []
    for k in range(1, YEARS_BACK + 1):
        end_k = shift_years(d, -k)
        p_k = _sum(_window(series, end_k, WINDOW_30), 0)
        prev.append({
            "year": end_k.year,
            "kbw30": _kbw(series, end_k, WINDOW_30),
            "precip30": None if p_k is None else round(p_k, 1),
        })
    prev_vals = [y["kbw30"] for y in prev if y["kbw30"] is not None]
    prev_p30 = [y["precip30"] for y in prev if y["precip30"] is not None]

    # 12-month precipitation vs the same 12 months in earlier years (fully inside the series).
    p365 = _sum(_window(series, d, 365), 0)
    prev_p365 = [
        v for k in range(1, YEARS_BACK)
        if (v := _sum(_window(series, shift_years(d, -k), 365), 0)) is not None
    ]

    # Summer (Jun–Aug) climatic water balance for every complete summer before the analysis date.
    summers: list[dict[str, Any]] = []
    for year in range(d.year - YEARS_BACK, d.year + 1):
        aug31 = date(year, 8, 31)
        if aug31 > d:
            continue
        rows = _window(series, aug31, 92)  # 1 Jun – 31 Aug
        p, e = _sum(rows, 0), _sum(rows, 1)
        if p is not None and e is not None:
            summers.append({"year": year, "kbw": round(p - e, 1), "precip": round(p, 1)})
    summers = summers[-YEARS_BACK:]
    pct = None
    if kbw30 is not None and len(prev_vals) >= 5:
        pct = round(100.0 * sum(v <= kbw30 for v in prev_vals) / len(prev_vals), 1)
    elif kbw30 is not None:
        errors.append("Za mało lat porównawczych (<5) do wyznaczenia percentyla KBW.")

    values = {
        "analysis_date": d.isoformat(),
        "precip_monthly": monthly_precip(series, d),
        "precip_30d": None if p30 is None else round(p30, 1),
        "et0_30d": None if e30 is None else round(e30, 1),
        "kbw_30d": kbw30,
        "kbw_60d": kbw60,
        "kbw_10y_percentile": pct,
        "kbw_30d_median_10y": round(median(prev_vals), 1) if prev_vals else None,
        "kbw_30d_prev_years": prev,  # transparency: lets the jury recompute the percentile
        "precip_30d_median_10y": round(median(prev_p30), 1) if prev_p30 else None,
        "precip_365d": None if p365 is None else round(p365, 1),
        "precip_365d_median_prev": round(median(prev_p365), 1) if len(prev_p365) >= 5 else None,
        "kbw_summer_by_year": summers,  # Jun–Aug P − ET0 per year
        "kbw_summer_mean_10y": round(sum(s["kbw"] for s in summers) / len(summers), 1) if summers else None,
        "dry_spell_days": dry,
        "temp_mean_30d": t30,
        "kbw_monthly_10y": monthly_kbw_climatology(series, d),
        "kbw_smsr_windows": smsr_window_kbw(series, d),
        "rain_events_10y": rain_events(series, d),
    }
    # Soil water is an extra signal: its absence is reported by the engine, not as a meteo error.
    sm, sm_err = soil_moisture_metrics(soil or {}, d)
    values.update(sm)
    values["soil_moisture_note"] = " ".join(sm_err) or None
    return values, errors


# --------------------------------------------------------------------------- soil water


def _mean_window(soil: dict[date, SoilDay], end: date, idx: int, days: int = SOIL_WINDOW) -> float | None:
    vals = [v[idx] for i in range(days) if (v := soil.get(end - timedelta(days=i))) and v[idx] is not None]
    return sum(vals) / len(vals) if len(vals) >= days - 2 else None


def soil_moisture_metrics(soil: dict[date, SoilDay], d: date) -> tuple[dict[str, Any], list[str]]:
    """Root-zone soil water (0–100 cm, 7-day mean) at the analysis date vs the same days in 10 years.

    Reanalysis output (model), published with a few days' delay: the latest day with data
    up to SOIL_MAX_LAG days before `d` is used and its date is reported.
    """
    if not soil:
        return {}, ["Brak wilgotności gleby z reanalizy (Open-Meteo nie zwróciło tych zmiennych "
                    "lub użyto zapasowego źródła NASA POWER)."]
    # Latest day that actually has data (so the reported date is a real reading, not a gap).
    end = next((day for i in range(SOIL_MAX_LAG + 1)
                if (v := soil.get(day := d - timedelta(days=i))) and v[1] is not None), None)
    if end is None or _mean_window(soil, end, 1) is None:
        return {}, [f"Brak wilgotności gleby z ostatnich {SOIL_MAX_LAG} dni przed dniem oceny."]
    root, top = _mean_window(soil, end, 1), _mean_window(soil, end, 0)
    prev = []
    for k in range(1, YEARS_BACK + 1):
        e = shift_years(end, -k)
        v = _mean_window(soil, e, 1)
        if v is not None:
            prev.append({"year": e.year, "root_pct": round(v * 100, 1)})
    vals = [p["root_pct"] for p in prev]
    now = round(root * 100, 1)
    pct = round(100.0 * sum(v <= now for v in vals) / len(vals), 1) if len(vals) >= 5 else None
    errs = [] if pct is not None else ["Za mało lat (<5) do porównania wilgotności gleby."]
    return {
        "soil_moisture_date": end.isoformat(),
        "soil_moisture_root_pct": now,            # % objętości, 0–100 cm, średnia 7 dni
        "soil_moisture_top_pct": None if top is None else round(top * 100, 1),  # 0–28 cm
        "soil_moisture_root_median_10y": round(median(vals), 1) if vals else None,
        "soil_moisture_root_min_10y": min(vals) if vals else None,
        "soil_moisture_root_max_10y": max(vals) if vals else None,
        "soil_moisture_percentile_10y": pct,
        "soil_moisture_prev_years": prev,
    }, errs


# --------------------------------------------------------------------------- multi-year windows


def _kbw_range(series: dict[date, Day], first: date, last: date) -> float | None:
    return _kbw(series, last, (last - first).days + 1)


def monthly_kbw_climatology(series: dict[date, Day], d: date) -> list[dict[str, Any]]:
    """KBW (P − ET0) of each calendar month in its last YEARS_BACK complete occurrences before `d`."""
    out = []
    for month in range(1, 13):
        rows = []
        year = d.year if date(d.year, month, monthrange(d.year, month)[1]) <= d else d.year - 1
        for y in range(year, year - YEARS_BACK, -1):
            v = _kbw_range(series, date(y, month, 1), date(y, month, monthrange(y, month)[1]))
            if v is not None:
                rows.append({"year": y, "kbw": v})
        vals = [r["kbw"] for r in rows]
        out.append({
            "month": month,
            "kbw_median": round(median(vals), 1) if vals else None,
            "kbw_mean": round(sum(vals) / len(vals), 1) if vals else None,
            "years": len(vals),
            "by_year": rows,
        })
    return out


def smsr_window_kbw(series: dict[date, Day], d: date) -> list[dict[str, Any]]:
    """KBW of each IUNG SMSR 60-day window in its last YEARS_BACK occurrences that ended by `d`."""
    out = []
    for i, (start_md, end_md) in enumerate(SMSR_WINDOWS):
        year = d.year if date(d.year, *end_md) <= d else d.year - 1
        rows = []
        for y in range(year, year - YEARS_BACK, -1):
            v = _kbw_range(series, date(y, *start_md), date(y, *end_md))
            if v is not None:
                rows.append({"year": y, "kbw": v})
        out.append({"index": i, "by_year": rows})
    return out


def rain_events(series: dict[date, Day], d: date) -> dict[str, Any]:
    """Daily rain ≥ RAIN_EVENT_MIN_MM on non-frozen days in the last 10 years (input for SCS-CN runoff).

    Days with mean temperature ≤ 0 °C are left out: precipitation is then mostly snow and
    its runoff comes later with the thaw, which this simple estimate does not model.
    """
    first = shift_years(d, -YEARS_BACK) + timedelta(days=1)
    days = [series.get(first + timedelta(days=i)) for i in range((d - first).days + 1)]
    known = [r for r in days if r and r[0] is not None]
    if len(known) < 0.9 * len(days):
        return {}
    return {
        "years": YEARS_BACK,
        "min_mm": RAIN_EVENT_MIN_MM,
        "precip_mean_year": round(sum(r[0] for r in known) / YEARS_BACK, 1),
        "days": [round(r[0], 1) for r in known
                 if r[0] >= RAIN_EVENT_MIN_MM and (r[2] is None or r[2] > 0.0)],
    }


def _month_start(d: date, back: int) -> date:
    m = d.year * 12 + d.month - 1 - back
    return date(m // 12, m % 12 + 1, 1)


def monthly_precip(series: dict[date, Day], d: date, months: int = 12) -> list[dict[str, Any]]:
    """Precipitation per calendar month for the last `months` months ending at `d`
    (the analysis month is partial: 1st..d), each next to the mean of the same
    day-range in up to YEARS_BACK previous years (only complete years count)."""
    out: list[dict[str, Any]] = []
    for back in range(months - 1, -1, -1):
        first = _month_start(d, back)
        last = d if back == 0 else _month_start(d, back - 1) - timedelta(days=1)
        n = (last - first).days + 1
        p = _sum(_window(series, last, n), 0)
        partial = last.day < monthrange(first.year, first.month)[1]
        prev = []
        for k in range(1, YEARS_BACK + 1):
            year = first.year - k
            days = last.day if partial else monthrange(year, first.month)[1]
            total = _sum(_window(series, date(year, first.month, days), days), 0)
            if total is not None:
                prev.append(total)
        out.append({
            "month": first.strftime("%Y-%m"),
            "precip": None if p is None else round(p, 1),
            "normal": round(sum(prev) / len(prev), 1) if len(prev) >= 5 else None,
            "years": len(prev),
            "partial": partial,
        })
    return out


# --------------------------------------------------------------------------- public API


async def fetch_meteo(centroid: list[float], analysis_date: date | str) -> dict[str, Any]:
    """Meteo stats for a plot centroid [lat, lng] as of `analysis_date`. Never raises."""
    try:
        lat, lng = round(float(centroid[0]), 3), round(float(centroid[1]), 3)
        d = parse_date(analysis_date)
        bad_input = None
    except Exception as exc:  # report through the normal adapter shape
        lat = lng = 0.0
        d = today_pl()
        bad_input = f"Niepoprawne dane wejściowe meteo: {exc}"

    today = today_pl()
    recent = (today - d).days <= RECENT_DAYS
    # Start 10 years back *minus* one window so the oldest comparison year is complete.
    # One extra year so the 12-month histogram has 10 comparison years for every month.
    start = shift_years(d, -YEARS_BACK - 1) - timedelta(days=WINDOW_60)
    end = min(d, today)

    async def fetch() -> dict[str, Any] | PartialResult:
        if bad_input:
            return PartialResult({}, [bad_input])
        if d > today:
            return PartialResult({}, [f"Data analizy {d} jest z przyszłości (dziś {today})."])

        notes: list[str] = []
        used: list[dict[str, str]] = []
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
            soil: dict[date, SoilDay] = {}
            try:
                series, soil = await _fetch_archive(client, lat, lng, start, end)
                used.append({"name": f"Open-Meteo Historical Weather API ({ARCHIVE_MODEL} – opady, "
                                     "parowanie, wilgotność gleby)", "url": ARCHIVE_URL})
            except Exception as exc:
                series = await _fetch_power(client, lat, lng, start, end)  # raises -> coverage none
                used.append({"name": "NASA POWER Daily API (MERRA-2/CERES; ET0 wg FAO-56 liczone lokalnie)",
                             "url": POWER_URL})
                notes.append(f"Główne źródło Open-Meteo niedostępne ({exc}); użyto NASA POWER "
                             "(rozdzielczość ok. 50 km).")

            # Archive lag: fill missing recent days from the forecast model.
            lag_start = today - timedelta(days=FORECAST_PAST_DAYS)
            gaps = [day for day in (d - timedelta(days=i) for i in range(WINDOW_60))
                    if day >= lag_start and (day not in series or None in series[day])]
            forecast_err = None
            if gaps:
                try:
                    fc = await _fetch_forecast_recent(client, lat, lng)
                    filled = 0
                    for day in gaps:
                        if day in fc:
                            row = series.setdefault(day, [None, None, None])
                            for i in range(3):
                                if row[i] is None and fc[day][i] is not None:
                                    row[i] = fc[day][i]
                                    filled += 1
                    if filled:
                        used.append({"name": "Open-Meteo Forecast API (ostatnie dni)", "url": FORECAST_URL})
                        notes.append(f"Ostatnie {len(gaps)} dni uzupełniono danymi modelu prognostycznego "
                                     "(archiwum reanaliz publikuje dane z opóźnieniem).")
                except Exception as exc:
                    forecast_err = f"Nie udało się uzupełnić ostatnich dni (archiwum ma opóźnienie): {exc}"

        if d == today:
            notes.append("Analiza na dziś: opad z bieżącego dnia jest częściowo prognozą.")

        values, errors = compute_metrics(series, d, soil)
        values["location"] = [lat, lng]
        values["notes"] = notes
        values["data_sources"] = used
        if forecast_err:
            errors.insert(0, forecast_err)
        return PartialResult(values, errors) if errors else values

    res = await run_adapter(
        "Open-Meteo",
        ARCHIVE_URL,
        {"lat": lat, "lng": lng, "analysis_date": d.isoformat(), "v": 6, "models": ARCHIVE_MODEL},
        fetch,
        cache_ttl_sec=3600 if recent else None,
    )

    # Report the sources actually used (stored inside values so cache hits keep them).
    used = res["values"].pop("data_sources", None)
    if used:
        fetched = res["sources"][0]["fetchedAt"] if res["sources"] else res["fetchedAt"]
        res["sources"] = [{**u, "fetchedAt": fetched} for u in used]
    return res


# --------------------------------------------------------------------------- live test

if __name__ == "__main__":
    import asyncio
    import json
    import time

    async def _main() -> None:
        point = [53.05, 18.25]
        for day in ("2019-07-15", "2026-07-15", today_pl().isoformat()):
            for attempt in (1, 2):
                t0 = time.perf_counter()
                r = await fetch_meteo(point, day)
                dt = time.perf_counter() - t0
                print(f"\n=== {day} call {attempt}: {dt:.2f}s fromCache={r['fromCache']} coverage={r['coverage']}")
                if attempt == 1:
                    v = dict(r["values"])
                    prev = v.pop("kbw_30d_prev_years", [])
                    print(json.dumps(v, ensure_ascii=False, indent=1))
                    print(" prev years KBW30:", [(y["year"], y["kbw30"]) for y in prev])
                    print(" sources:", [s["name"] for s in r["sources"]])
                    print(" errors:", r["errors"])

    asyncio.run(_main())
