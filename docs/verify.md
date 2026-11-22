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
Susceptibility (multi-year): mean summer (VI–VIII) KBW, share of summers with KBW < −150 mm, 12-month precip anomaly, soil storage, and a small FAO Ky crop modifier (`CROP_SENS_SUS_WEIGHT` = 5, max ≈ +5) → `low` < 40 ≤ `medium` < 62 ≤ `high`. Climate and soil dominate; crop is secondary.

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

## 6. Crop fit (which crop copes best with the water on this plot)

A **separate report**, chosen in the form instead of the water report: `POST /crop-fit` (body: `plotId`
or `lat`+`lng`, `analysisDate`; no crop) → `CropFitReport` with `cropFit.ranking`. It is not part of
`/analyze` and does not change the moisture assessment or the retention recommendations.
Only multi-year inputs are used (no satellite / regional drought / last 30 days).

`cropFit.ranking` — 17 crops (finer than the IUNG groups: rye ≠ wheat, lupin ≠ pea,
strawberries ≠ raspberries), each linked to a catalog group (`groupId`). Profiles:
`apps/api/app/crops/fit_profiles.py` (root depth from FAO-56 Table 22, sensitivity after FAO-33 Ky,
soil needs after Polish soil valuation / IUNG suitability complexes). Scoring:
`apps/api/app/engine/crop_fit.py`, all constants at the top. Score = 100 minus:

| Penalty | Rule |
|---------|------|
| water | 55 × sensitivity × (0.6 × dry summers + 0.4 × little water in root zone). Dry summers: mean summer KBW −100 mm → 0, −250 mm → 1, averaged with the share of summers < −150 mm. Root-zone water = AWC × min(root depth, 1 m): ≥ 100 mm → 0, ≤ 20 mm → 1. Roots ≥ 1.2 m and sensitivity ≤ 0.6: +5 |
| soil | needs good soil on poor −30, on medium −12; needs medium soil on poor −15; undemanding crop on good soil −6. Soil level = median EGiB class (I–IIIa good, IIIb–IVa medium, IVb–VI poor), else SoilGrids (sand ≥ 65 % or AWC < 100 mm poor; AWC ≥ 150 mm and sand < 45 % good) |
| slope | row crops −20 at ≥ 6 %, −10 at ≥ 3 %; medium-risk crops −6 at ≥ 6 % |
| wet | clay ≥ 45 %, or clay ≥ 35 % with water ≤ 100 m: waterlogging-intolerant −18, medium −6 |
| land | EGiB meadow/pasture: every crop except grassland −30 (TUZ ploughing protection) |

`good` ≥ 75 > `medium` ≥ 55 > `poor`. Ties → more drought-tolerant crop first. Confidence is at most
`medium` (profiles are orientation values). Not considered: prices, rotation, pH, varieties, machinery, subsidies.

Alignment with the KOWR material "Podstawy naukowe oceny sytuacji wodnej…": only multi-year conditions
are used (current drought ≠ multi-year susceptibility); soil storage includes organic matter
(Saxton & Rawls AWC); slope/runoff is a factor; every reason cites Evidence; the uncertainty is stated in
the report (`cropFit.notConsidered`). The material itself has **no crop-level numbers** — profile values
come from its bibliography (FAO-56, IUNG-PIB SMSR crop groups) plus an explicit expert classification
(soil needs, waterlogging, erosion) that is not yet checked against IUNG tables.
Test: `pytest apps/api/tests/test_crop_fit.py`.

## 7. Automated suite

```bash
cd apps/api
pytest -q
```

Expected: all green (health/crops/analyze, determinism, ranking, template narrative).
