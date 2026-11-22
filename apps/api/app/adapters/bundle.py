"""AdapterBundle — what the engine receives from the data layer.

Every part uses Person 2's `run_adapter` response shape (see adapters/base.py):
    {"values": {...}, "sources": [{name,url,fetchedAt}], "fetchedAt": str,
     "coverage": "full"|"partial"|"none", "errors": [str], "fromCache": bool}

`plot` is the resolver dict (plot/resolver.py) *with* context:
    plotId, geometry, centroid [lat, lng], areaHa, bbox, voivodeship, county, commune,
    terrain {slopePct, runoffRisk, ...}, hydro {nearbyWater, distanceClass, missing, ...},
    sources [...], missingData [str], limitations [str], fetchedAt

Value keys the engine reads (all nullable):
    meteo:   precip_30d, precip_30d_median_10y, kbw_30d, kbw_10y_percentile, dry_spell_days,
             temp_mean_30d, precip_365d, precip_365d_median_prev,
             kbw_summer_mean_10y, kbw_summer_by_year[{year,kbw}]
    soil:    sand_pct, clay_pct, soc_pct, awc_mm, awc_depth_cm, retention_class
    sat:     ndvi_mean, ndvi_std, ndvi_median, ndmi_mean, scene_date,
             bare_soil_pct, water_pct, weak_zone_pct, ndmi_dry_pct
    sat_history (optional): years[{year, scene_date, ndvi_mean, ndmi_mean}], n_years,
             ndvi_median, ndmi_median  (same 21-day window, previous years)
    drought: cdi_class (0–3), cdi_label, dekad_start
    meteo (extra): soil_moisture_* (ERA5-Land, % vol.), kbw_monthly_10y, kbw_smsr_windows,
             rain_events_10y {years, days[mm], precip_mean_year}
    iung_soil (optional): category (1–4), category_share_pct, dominant_code, dominant_label
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


@dataclass
class AdapterBundle:
    plot: dict[str, Any]
    meteo: dict[str, Any]
    soil: dict[str, Any]
    sat: dict[str, Any]
    drought: dict[str, Any]
    mode: Literal["live"] = "live"
    # None = not fetched (tests / old callers) -> no source row, no missingData
    sat_history: dict[str, Any] | None = field(default=None)
    # IUNG soil drought category map (adapters/iung_soil.py); None = not fetched
    iung_soil: dict[str, Any] | None = field(default=None)
