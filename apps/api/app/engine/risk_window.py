"""When in the season does this plot most often run short of water? (last 10 years)

Primary method (`smsr`): for each of the 14 official IUNG SMSR six-dekad windows, count in how
many of the last 10 years the climatic water balance (P − ET0) fell below the drought threshold
for *this crop on this soil category* (MRiRW 2019). A window crossed in ≥ RISK_MIN_YEARS years is
a risk period. Thresholds are the regulation's numbers – nothing tuned here.

Fallback (`kbw_monthly`, crops without SMSR thresholds, „Brak uprawy”, organic soils, unknown
soil): the months with the most negative median monthly water balance. This states facts only
(where evaporation exceeds rain most) and never claims a drought threshold.
"""

from __future__ import annotations

from app.crops.catalog import MONTH_PL
from app.crops.smsr import RISK_MIN_YEARS, SmsrWindowStat
from app.engine.facts import Facts, fmt
from app.schemas.evidence import RiskBar, RiskWindow

ROMAN = ("I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII")
MONTHLY_TOP = 3          # fallback: name the 3 driest months
MIN_YEARS_COMPARED = 5   # fewer comparable years → no statement


def _md(md: tuple[int, int]) -> str:
    return f"{md[1]}.{ROMAN[md[0] - 1]}"


def _months(start: tuple[int, int], end: tuple[int, int]) -> set[int]:
    return set(range(start[0], end[0] + 1))


def _runs(stats: list[SmsrWindowStat]) -> list[list[SmsrWindowStat]]:
    """Group risky windows into runs of consecutive window indices (e.g. rapeseed spring + autumn)."""
    runs: list[list[SmsrWindowStat]] = []
    for s in stats:
        if runs and s.index == runs[-1][-1].index + 1:
            runs[-1].append(s)
        else:
            runs.append([s])
    return runs


def _month_list_pl(months: list[int]) -> str:
    names = [MONTH_PL[m - 1] for m in months]
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + " i " + names[-1]


def _smsr_window(f: Facts) -> RiskWindow | None:
    stats = [s for s in f.smsr_hist if s.threshold_mm is not None and s.years_total >= MIN_YEARS_COMPARED]
    if not stats:
        return None
    critical = set(f.crop_critical)
    risky = [s for s in stats if s.years_below >= RISK_MIN_YEARS]
    peak = max(stats, key=lambda s: (s.years_below, -s.index))
    months: set[int] = set()
    for s in risky:
        months |= _months(s.start_md, s.end_md)
    bars = [RiskBar(label=s.label, value=s.years_below, of=s.years_total, thresholdMm=s.threshold_mm,
                    risky=s.years_below >= RISK_MIN_YEARS,
                    critical=bool(_months(s.start_md, s.end_md) & critical)) for s in stats]
    overlap = sorted(months & critical)

    if risky:
        spans = [f"od {_md(r[0].start_md)} do {_md(r[-1].end_md)}" for r in _runs(risky)]
        text = (f"Największe ryzyko suszy rolniczej dla tej uprawy na tej glebie: {' oraz '.join(spans)}. "
                f"Najczęściej w okresie {peak.label} – w {peak.years_below} z {peak.years_total} ostatnich lat "
                f"bilans wodny spadł tu poniżej progu IUNG ({fmt(peak.threshold_mm, 0)} mm).")
        if overlap:
            text += (f" To pokrywa się z najbardziej wrażliwą fazą uprawy ({_month_list_pl(overlap)}) – "
                     "wtedy szczególnie pilnuj stanu roślin i zapasu wody.")
    elif peak.years_below == 0:
        text = ("W ostatnich 10 latach bilans wodny ani razu nie spadł tu poniżej progu suszy IUNG dla tej uprawy "
                "na tej glebie.")
    else:
        text = ("W ostatnich 10 latach bilans wodny rzadko spadał tu poniżej progu suszy IUNG dla tej uprawy "
                f"(najczęściej w okresie {peak.label}: {peak.years_below} z {peak.years_total} lat).")
    return RiskWindow(method="smsr", text=text, months=sorted(months), criticalOverlap=overlap,
                      yearsHit=peak.years_below, yearsTotal=peak.years_total,
                      peakLabel=peak.label if risky else None,
                      unit="lata (z 10) z bilansem wodnym poniżej progu suszy IUNG",
                      bars=bars, evidenceRefs=["ev_risk_window", "ev_soil_category", "ev_smsr_threshold"])


def _monthly_window(f: Facts) -> RiskWindow | None:
    rows = [r for r in f.kbw_monthly if r.get("kbw_median") is not None and r.get("years", 0) >= MIN_YEARS_COMPARED]
    if len(rows) < 12:
        return None
    neg = sorted((r for r in rows if r["kbw_median"] < 0), key=lambda r: r["kbw_median"])[:MONTHLY_TOP]
    months = sorted(int(r["month"]) for r in neg)
    critical = set(f.crop_critical)
    overlap = sorted(set(months) & critical)
    bars = [RiskBar(label=MONTH_PL[int(r["month"]) - 1][:3], value=r["kbw_median"], of=int(r["years"]),
                    risky=int(r["month"]) in months, critical=int(r["month"]) in critical)
            for r in sorted(rows, key=lambda r: int(r["month"]))]
    if not months:
        return RiskWindow(method="kbw_monthly", unit="mediana bilansu wodnego miesiąca (mm)", bars=bars,
                          text="W ostatnich 10 latach w żadnym miesiącu parowanie nie przewyższało zwykle opadów.")
    worst = neg[0]
    text = (f"Najwięcej wody ucieka tu w miesiącach: {_month_list_pl(months)} – wtedy parowanie zwykle przewyższa "
            f"opady (najbardziej w miesiącu {MONTH_PL[int(worst['month']) - 1]}: mediana {fmt(worst['kbw_median'], 0)} mm "
            f"w {worst['years']} latach).")
    if overlap:
        text += f" To pokrywa się z najbardziej wrażliwą fazą uprawy ({_month_list_pl(overlap)})."
    label = (f"{ROMAN[months[0] - 1]}–{ROMAN[months[-1] - 1]}" if months == list(range(months[0], months[-1] + 1))
             else ", ".join(ROMAN[m - 1] for m in months))
    return RiskWindow(method="kbw_monthly", text=text, months=months, criticalOverlap=overlap,
                      peakLabel=label, unit="mediana bilansu wodnego miesiąca (mm)", bars=bars,
                      evidenceRefs=["ev_risk_window"])


def compute_risk_window(f: Facts) -> RiskWindow | None:
    return _smsr_window(f) or _monthly_window(f)
