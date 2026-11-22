# Verification — how to spot-check Retencja numbers

Jury / teammates can confirm the engine is deterministic and honest from Evidence alone.

## 1. Same request → identical scores

```bash
cd apps/api
curl -s -X POST http://127.0.0.1:8000/analyze -H "Content-Type: application/json" ^
  -d "{\"plotId\":\"141201_2.0001.123\",\"cropId\":\"kukurydza_ziarno\",\"analysisDate\":\"2025-07-15\"}" > a.json
curl -s -X POST http://127.0.0.1:8000/analyze -H "Content-Type: application/json" ^
  -d "{\"plotId\":\"141201_2.0001.123\",\"cropId\":\"kukurydza_ziarno\",\"analysisDate\":\"2025-07-15\"}" > b.json
```

Compare:

- `moistureAssessment.current.score0to100`
- `moistureAssessment.susceptibility.score0to100`
- `causes[].id`
- recommendation IDs

They must match. Automated: `pytest apps/api/tests/test_engine_deterministic.py`.

## 2. Narrative is template-only

`/analyze` always returns Polish section prose from the Evidence template (`apps/api/app/narrative/templates_pl.py`). There is no generative LLM in the product path.

## 3. Cause thresholds (engine constants)

In `apps/api/app/engine/assess.py` / `causes.py`:

| Signal | Rough trigger |
|--------|----------------|
| `precip_deficit` | 30-day precip / 10-year median of the same window < 0.70, or 30-day KBW (P − ET0) in the driest 25 % of the last 10 years, or ≥ 10 days without rain |
| `low_soil_storage` | AWC (0–100 cm, Saxton & Rawls on SoilGrids) < 110 mm or sand ≥ 55 % |
| `runoff` | slope ≥ 3.5 % or runoffRisk medium/high (GUGiK NMT) |
| `crop_sensitivity` | FAO-derived sensitivity ≥ 0.65 and (dry now or high multi-year susceptibility), **or** 60-day KBW below the IUNG SMSR threshold for crop×soil×period |
| `bare_soil` | Sentinel-2: ≥ 50 % of clear plot pixels with NDVI < 0.2, scene in VIII–III (not for winter cereals / rapeseed in VIII–XI = fresh sowing), agricultural land |

Moisture level (now): point score from precip ratio, KBW percentile, dry spell, AWC, EDO CDI, SMSR 60-day threshold breach → `very_dry` < 32 ≤ `dry` < 55 ≤ `normal` < 80 ≤ `wet`.
<<<<<<< Updated upstream
Susceptibility (multi-year): mean summer (VI–VIII) KBW, share of summers with KBW < −150 mm, 12-month precip anomaly, soil storage, and a small FAO Ky crop modifier (`CROP_SENS_SUS_WEIGHT` = 5, max ≈ +5) → `low` < 40 ≤ `medium` < 62 ≤ `high`. Climate and soil dominate; crop is secondary.
=======
Susceptibility (multi-year) = weighted mean of 0–100 sub-scores (missing parts drop out, weights rescaled, confidence lowered): IUNG drought line crossed in the worst SMSR window (share of 10 years; 5/10 = 100) × 0,35 · summer (VI–VIII) KBW on the Polish range (−50 mm = 0, −200 mm = 100) × 0,25 · share of dry summers (KBW < −150 mm) × 0,15 · soil (100 − storage score) × 0,25 · crop sensitivity × 0,15 only when the crop has no IUNG thresholds → `low` < 30 ≤ `medium` < 55 ≤ `high`. Calibration check on 14 locations across Poland (2025-07-15): Kujawy/Wielkopolska high, loess and Żuławy low–medium, Podhale low. The 12-month precipitation anomaly is not part of it (it is the current year, not a property of the plot).
>>>>>>> Stashed changes

### Crop weights are not hand-tuned

| Layer | Source | Role |
|-------|--------|------|
| Crop groups | IUNG SMSR (exact 14 categories) | Same buckets as agricultural-drought monitoring |
| `droughtSensitivity` 0–1 | FAO-33 seasonal Ky → linear map `[0.85, 1.25] → [0.25, 1.00]` in `app/crops/fao.py` | Structural yield response |
| Situational drought flag | MRiRW 2019 / IUNG SMSR KBW thresholds (`app/crops/smsr.py`) vs Open-Meteo `kbw_60d` | ~20% yield-loss line for crop×soil×period |

Spot-check: for `kukurydza_ziarno` on 2025-07-15, evidence should include `ev_fao_ky` (1.25) and, when soil AWC + `kbw_60d` are present, `ev_smsr_threshold`.

### Season, irrigation dose, slope, pond spot (engine 0.3.0)

| Value | Rule | Where |
|-------|------|-------|
| Crop season / critical months / Kc | static table per SMSR crop (`seasonMonths`, `criticalMonths`, `kcMid` from FAO-56 Table 12) | `apps/api/app/crops/catalog.py` |
| `ev_crop_deficit` | `et0_30d × kcMid − precip_30d` (mm), shown only when > 0 | `facts.py` (`crop_deficit30`) |
| Irrigation | only when current level is dry/very_dry, crop sensitivity ≥ 0.65, **analysis month in `seasonMonths`**, and retention was already offered. Outside the season: no recommendation and `irrigationNote` explains why | `rank.py` |
| Irrigation timeframe | month in `criticalMonths` → "teraz"; otherwise "w okresie krytycznym (…)" | `rank.py` |
| Single dose | AWC < 110 mm → 15–20 mm; otherwise 25–30 mm; AWC unknown → 20–25 mm (orientation ranges) | `rank.py` (`DOSE_*`) |
| Interval between doses | daily use = `et0_30d × kcMid / 30`; interval = ⌊dose / daily use⌋ for both ends of the dose range, clamped to 2–14 days. Rain ≥ lower dose bound replaces one watering | `rank.py` (`irrigation_interval`) |
| `slopePct` | least-squares plane z = a·x + b·y + c through all NMT samples inside the plot, slope = √(a²+b²)·100. Falls back to (max − min) / distance only for < 3 or collinear points (`slopeMethod`) | `plot/resolver.py` (`_plane_slope_pct`) |
| `ev_low_spot` | elevation drop of the lowest NMT sample vs the highest one. Cited by `small_pond` | `plot/resolver.py` (`_retention_spot`) |

Check: `et0_30d` and `precip_30d` are in the meteo adapter values; heights are reproducible with `GetHByPointList` on the GUGiK NMT service.

All constants live at the top of `apps/api/app/engine/assess.py`. Raw inputs for recomputation are in the adapter values (e.g. `kbw_30d_prev_years`, `kbw_summer_by_year`, soil `layers`).

### Satellite (Sentinel-2 L2A, `apps/api/adapters/sentinel_stac.py`)

No ML – band arithmetic on the plot's 10 m pixels after SCL cloud/snow masking:

| Value | Formula / rule |
|-------|----------------|
| `ndvi_mean`, `ndvi_median` | (B08 − B04) / (B08 + B04) |
| `ndmi_mean` | (B08 − B11) / (B08 + B11) – water in leaves, not soil moisture |
| `bare_soil_pct` | % pixels NDVI < 0.2 (excluding water) → evidence `ev_bare_soil` if ≥ 10 % |
| `water_pct` | % pixels SCL = 6 (ESA "water") → `ev_standing_water` if ≥ 2 %, adds `small_pond` |
| `weak_zone_pct` | % pixels with NDVI < plot median − 0.15 (only if median ≥ 0.3) → `ev_weak_zone` if ≥ 10 % |
| history (`fetch_sentinel_history`) | same 21-day window in each of the previous 5 years → median NDVI / NDMI; used only with ≥ 3 clear years |

Effect on the current moisture score (`satellite_moisture_signal` in `assess.py`), bounded to −10 / +6 so weather stays primary:

- only when NDVI ≥ 0.3 (green cover);
- NDVI ≥ 0.5 and NDMI < 0 → −6; NDMI ≥ 0.4 → +4;
- NDMI − plot's historical median ≤ −0.10 → −6, ≥ +0.10 → +4 – **only if** the historical NDVI is ≥ 0.3 and within ±0.2 of today's (otherwise it is probably another crop in the rotation and the comparison is skipped and said so in `ev_ndmi`).

A negative satellite signal also raises `precip_deficit` confidence by 0.1 and adds `ev_ndmi` to it.

Inspect `causes[].evidenceRefs` and matching adapter `values` in the response.

### Soil moisture, IUNG soil category, risk period, runoff (engine 0.4)

| Value | Rule | Where |
|-------|------|-------|
| `ev_soil_moisture` | ERA5-Land daily soil water (Open-Meteo archive `soil_moisture_0_to_7cm_mean`, `7_to_28cm`, `28_to_100cm`), thickness-weighted 0–100 cm, 7-day mean ending at the latest day with data (≤ 10 days before the analysis date). Percentile = % of the same 7 days in the 10 previous years that were ≤ now (raw list: `soil_moisture_prev_years`) | `adapters/open_meteo.py` (`soil_moisture_metrics`) |
| Current score | percentile ≤ 10 → −12, ≤ 25 → −6, ≥ 75 → +6; ≤ 25 also triggers / confirms `precip_deficit` | `assess.py` (`SM_PCT_*`), `causes.py` |
| `ev_soil_category` | IUNG map `Susza:katgl_landuse2024` (GetMap PNG over the parcel, colours = official legend; dominant category 1–4 among pixels inside the parcel). Fallback only if the map gives no category: AWC with IUNG WOD limits (127,5 / 170 / 202,5 mm). Organic soils: no SMSR threshold, no fallback | `adapters/iung_soil.py`, `facts.py` |
| SMSR thresholds | regulation table, checked cell-by-cell against https://susza.iung.pulawy.pl/progi/ on 2026-11-22. "-" (sugar beet, soil I) = crop not indicated → no threshold, warning in limitations | `app/crops/smsr.py` |
| Current SMSR check | rolling 60-day KBW vs the window ending nearest the analysis date, only if it ends within ±10 days | `smsr.pick_period_index` |
| `ev_risk_window` / `riskWindow` | KBW (P − ET0) summed over each of the 14 exact SMSR windows in the last 10 years in which the window had ended (`kbw_smsr_windows`); window is a risk period if KBW < threshold(crop, soil) in ≥ 3 of 10 years. Peak = most years (tie → earliest). Fallback for crops without thresholds: 3 months with the most negative median monthly KBW (`kbw_monthly_10y`) | `engine/risk_window.py` |
| Susceptibility | + 16 × (years below threshold in the worst window / years compared) | `assess.py` (`SMSR_HIST_WEIGHT`) |
| `ev_runoff_volume` | SCS-CN: Q = (P − 0,2S)² / (P + 0,8S), S = 25400/CN − 254, for each day with ≥ 3 mm rain and mean T > 0 °C in the last 10 years; CN from TR-55 tables 2-2b/2-2c (condition "good") by crop cover and soil group (NEH 630 ch. 7 texture rules on SoilGrids topsoil). Volume = mm × ha × 10 | `engine/runoff.py` |
| `ev_pond_volume` | runoff of the 5th-largest daily rain in 10 years (≈ once in 2 years) over the whole plot; example area at 1,5 m depth | `engine/runoff.py` |

## 4. Evidence IDs on the fixture

Open [`fixtures/evidence_sample.json`](../fixtures/evidence_sample.json):

- Every cause and recommendation lists `evidenceRefs`.
- UI should surface these as “dlaczego”.
- Current vs multi-year blocks use **different** summaries and mostly different evidence ids.

## 5. Ranking order

If `recommendations.irrigation` is non-empty:

1. `recommendations.retention` is non-empty.
2. Irrigation id is only `irrigation_timing`.
3. Report order is retention → agrotech → irrigation.

Test: `pytest apps/api/tests/test_ranking_order.py`.

## 6. Automated suite

```bash
cd apps/api
pytest -q
```

Expected: all green (health/crops/analyze, determinism, ranking, template narrative).
