# Verification — how to spot-check Retencja numbers

Jury / teammates can confirm the engine is deterministic and honest without trusting the LLM.

## 1. Same request → identical scores

```bash
cd apps/api
curl -s -X POST http://127.0.0.1:8000/analyze -H "Content-Type: application/json" ^
  -d "{\"plotId\":\"141201_2.0001.123\",\"cropId\":\"kukurydza\",\"analysisDate\":\"2025-07-15\"}" > a.json
curl -s -X POST http://127.0.0.1:8000/analyze -H "Content-Type: application/json" ^
  -d "{\"plotId\":\"141201_2.0001.123\",\"cropId\":\"kukurydza\",\"analysisDate\":\"2025-07-15\"}" > b.json
```

Compare:

- `moistureAssessment.current.score0to100`
- `moistureAssessment.multiYearSusceptibility.score0to100`
- `causes[].id`
- recommendation IDs

They must match. Automated: `pytest apps/api/tests/test_engine_deterministic.py`.

## 2. Toggle LLM

```bash
# Template path (demo-safe)
set LLM_ENABLED=false
uvicorn app.main:app --port 8000
# narrative.generatedBy == "template"

# Ollama path (soft-fails to template if Ollama down)
set LLM_ENABLED=true
set OLLAMA_MODEL=qwen2.5:3b
```

`/analyze` must stay **200** either way.

## 3. Cause thresholds (engine constants)

In `apps/api/app/engine/assess.py` / `causes.py`:

| Signal | Rough trigger |
|--------|----------------|
| `precip_deficit` | 30-day precip / 10-year median of the same window < 0.70, or 30-day KBW (P − ET0) in the driest 25 % of the last 10 years, or ≥ 10 days without rain |
| `low_soil_storage` | AWC (0–100 cm, Saxton & Rawls on SoilGrids) < 110 mm or sand ≥ 55 % |
| `runoff` | slope ≥ 3.5 % or runoffRisk medium/high (GUGiK NMT) |
| `crop_sensitivity` | crop sensitivity ≥ 0.65 and (dry now or high multi-year susceptibility) |

Moisture level (now): point score from precip ratio, KBW percentile, dry spell, AWC, EDO CDI → `very_dry` < 32 ≤ `dry` < 55 ≤ `normal` < 80 ≤ `wet`.
Susceptibility (multi-year): mean summer (VI–VIII) KBW, share of summers with KBW < −150 mm, 12-month precip anomaly, soil storage, crop sensitivity → `low` < 40 ≤ `medium` < 62 ≤ `high`.
All constants live at the top of `apps/api/app/engine/assess.py`. Raw inputs for recomputation are in the adapter values (e.g. `kbw_30d_prev_years`, `kbw_summer_by_year`, soil `layers`).

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

## 6. Automated suite

```bash
cd apps/api
pytest -q
```

Expected: all green (health/crops/analyze, determinism, ranking, validator invent-reject, LLM-off fallback).
