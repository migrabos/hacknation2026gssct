"""Pre-warm the disk cache for the rehearsal / finals plots and log data provenance.

Run from apps/api:
    python -m warm_cache                       # 5 default plots × 3 default dates
    python -m warm_cache --dates 2026-11-21    # custom dates
    python -m warm_cache --plots 040308_5.0004.17220 --points 54.15,19.05

Outputs:
    * summary table on stdout (coverage per source, timings)
    * docs/data_sources_log.json – every API used, licence, example URL, fetchedAt range
      (paste-ready for README "live vs cached data" section)
"""

from __future__ import annotations

import argparse
import asyncio
import json
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from adapters.base import utc_now_iso
from adapters.drought_edo import fetch_drought_context
from adapters.open_meteo import fetch_meteo
from adapters.sentinel_stac import fetch_sentinel
from adapters.soilgrids import fetch_soil
from plot.resolver import PlotError, add_plot_context, resolve_plot, resolve_point

DEFAULT_PLOT_IDS = [
    "040308_5.0004.17220",   # kujawsko-pomorskie, Solec Kujawski – sandy, 28 ha
    "302108_5.0021.431/68",  # wielkopolskie, Kostrzyn – sandy, small plot
    "061703_5.0017.176/2",   # lubelskie, Piaski – loess
]
DEFAULT_POINTS = [
    (54.15, 19.05),  # pomorskie, Żuławy – delta lowland, dense ditch network
    (50.15, 20.35),  # małopolskie, Nowe Brzesko – Proszowice loess plateau (49.95,20.45 hit a 272 m² town plot)
]
DEFAULT_DATES = ["2019-07-15", "2026-07-15", "2026-11-21"]

LOG_PATH = Path(__file__).resolve().parents[2] / "docs" / "data_sources_log.json"

# Licence / terms per source name prefix (as reported in `sources[].name`).
LICENSES: dict[str, str] = {
    "ULDK GUGiK": "Dane GUGiK (EGiB) udostępniane bezpłatnie – ustawa Prawo geodezyjne i kartograficzne, art. 40a",
    "GUGiK NMT": "Dane GUGiK (NMT) udostępniane bezpłatnie – ustawa Prawo geodezyjne i kartograficzne, art. 40a",
    "Open-Meteo Elevation": "Open-Meteo, dane CC BY 4.0 (Copernicus DEM GLO-90); API bezpłatne do użytku niekomercyjnego",
    "Open-Meteo Historical": "Open-Meteo, dane CC BY 4.0 (ERA5/ERA5-Land, Copernicus C3S); API bezpłatne do użytku niekomercyjnego (<10 000 zapytań/dzień)",
    "Open-Meteo Forecast": "Open-Meteo, dane CC BY 4.0; API bezpłatne do użytku niekomercyjnego",
    "NASA POWER": "NASA POWER – dane publiczne bez ograniczeń (NASA Earth Science Data Policy), prośba o cytowanie",
    "ISRIC SoilGrids": "ISRIC SoilGrids 2.0 – CC BY 4.0",
    "Sentinel-2": "Copernicus Sentinel data – licencja pełna, otwarta i bezpłatna (Rozp. UE 1159/2013); katalog STAC Element84 Earth Search",
    "OpenStreetMap": "© OpenStreetMap contributors – ODbL 1.0",
    "EDO": "Copernicus Emergency Management Service – EDO, CC BY 4.0",
}


def _license(name: str) -> str:
    for prefix, lic in LICENSES.items():
        if name.startswith(prefix) or prefix in name:
            return lic
    return "DO UZUPEŁNIENIA"


def _endpoint(url: str) -> str:
    p = urlsplit(url)
    return f"{p.scheme}://{p.netloc}{p.path}"


# --------------------------------------------------------------------------- run


async def _plot(plot_id: str | None, point: tuple[float, float] | None) -> dict[str, Any] | str:
    try:
        if plot_id:
            return await resolve_plot(plot_id, with_context=False)
        return await resolve_point(*point, with_context=False)  # type: ignore[misc]
    except PlotError as exc:
        return str(exc)


async def warm(plot_ids: list[str], points: list[tuple[float, float]], dates: list[str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    all_sources: list[dict[str, Any]] = []

    targets = [(pid, None) for pid in plot_ids] + [(None, pt) for pt in points]
    for pid, pt in targets:
        label = pid or f"punkt {pt[0]},{pt[1]}"
        t0 = time.perf_counter()
        plot = await _plot(pid, pt)
        t_plot = time.perf_counter() - t0
        if isinstance(plot, str):
            rows.append({"plot": label, "error": plot})
            print(f"✗ {label}: {plot}")
            continue
        print(f"✓ {plot['plotId']} ({plot['voivodeship']}, {plot['areaHa']} ha) resolved in {t_plot:.1f}s")
        base = plot

        for d in dates:
            # Same pattern /analyze should use: terrain+hydro run in parallel with adapters.
            t1 = time.perf_counter()
            plot, meteo, soil, sat, edo = await asyncio.gather(
                add_plot_context(base),
                fetch_meteo(base["centroid"], d),
                fetch_soil(base["centroid"]),
                fetch_sentinel(base["bbox"], d, base["geometry"]),
                fetch_drought_context(base["centroid"], d),
            )
            dt = time.perf_counter() - t1
            all_sources += plot["sources"]
            for r in (meteo, soil, sat, edo):
                all_sources += r["sources"]
            rows.append({
                "plot": plot["plotId"],
                "voivodeship": plot["voivodeship"],
                "areaHa": plot["areaHa"],
                "date": d,
                "seconds": round(t_plot + dt, 1),
                "plotSrc": "full",
                "terrain": "none" if plot["terrain"].get("slopePct") is None else "full",
                "hydro": "none" if plot["hydro"].get("missing") else "full",
                "meteo": meteo["coverage"] + ("*" if meteo["fromCache"] else ""),
                "soil": soil["coverage"] + ("*" if soil["fromCache"] else ""),
                "sentinel": sat["coverage"] + ("*" if sat["fromCache"] else ""),
                "edo": edo["coverage"] + ("*" if edo["fromCache"] else ""),
                "errors": [e for r in (meteo, soil, sat, edo) for e in r["errors"]] + plot["missingData"],
            })
            t_plot = 0.0  # count plot resolve time only once per plot

    _write_log(all_sources)
    return rows


def _write_log(sources: list[dict[str, Any]]) -> None:
    by_name: dict[str, dict[str, Any]] = {}
    for s in sources:
        e = by_name.setdefault(s["name"], {
            "name": s["name"],
            "endpoint": _endpoint(s["url"]),
            "exampleUrl": s["url"],
            "license": _license(s["name"]),
            "firstFetchedAt": s["fetchedAt"],
            "lastFetchedAt": s["fetchedAt"],
            "requests": 0,
        })
        e["requests"] += 1
        e["firstFetchedAt"] = min(e["firstFetchedAt"], s["fetchedAt"])
        e["lastFetchedAt"] = max(e["lastFetchedAt"], s["fetchedAt"])

    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    LOG_PATH.write_text(json.dumps({
        "generatedAt": utc_now_iso(),
        "note": "Wszystkie dane pobierane na żywo z API w momencie analizy; cache dyskowy tylko przyspiesza "
                "ponowne zapytania. fetchedAt = moment faktycznego pobrania z API.",
        "sources": sorted(by_name.values(), key=lambda e: e["name"]),
    }, ensure_ascii=False, indent=2), encoding="utf-8")


def _print_table(rows: list[dict[str, Any]]) -> None:
    cols = ["plot", "voivodeship", "areaHa", "date", "seconds",
            "terrain", "hydro", "meteo", "soil", "sentinel", "edo"]
    ok_rows = [r for r in rows if "error" not in r]
    widths = {c: max(len(c), *(len(str(r.get(c, ""))) for r in ok_rows)) if ok_rows else len(c) for c in cols}
    line = "  ".join(c.ljust(widths[c]) for c in cols)
    print("\n" + line + "\n" + "-" * len(line))
    for r in rows:
        if "error" in r:
            print(f"{r['plot']}: BŁĄD – {r['error']}")
            continue
        print("  ".join(str(r.get(c, "")).ljust(widths[c]) for c in cols))
    print("\n* = z cache dyskowego")

    problems = {(r["plot"], e) for r in ok_rows for e in r["errors"]}
    if problems:
        print("\nBraki / ostrzeżenia:")
        for plot, e in sorted(problems):
            print(f"  [{plot}] {e}")
    print(f"\nLog źródeł: {LOG_PATH}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Pre-warm cache for rehearsal plots.")
    ap.add_argument("--plots", nargs="*", default=DEFAULT_PLOT_IDS, help="plot IDs")
    ap.add_argument("--points", nargs="*", default=[f"{a},{b}" for a, b in DEFAULT_POINTS], help="lat,lng")
    ap.add_argument("--dates", nargs="*", default=DEFAULT_DATES)
    args = ap.parse_args()
    points = [tuple(float(x) for x in p.split(",")) for p in args.points]

    t0 = time.perf_counter()
    rows = asyncio.run(warm(args.plots, points, args.dates))  # type: ignore[arg-type]
    _print_table(rows)
    print(f"Łączny czas: {time.perf_counter() - t0:.0f}s")


if __name__ == "__main__":
    main()
