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
# narrative.mode == "template"

# Ollama path (soft-fails to template if Ollama down)
set LLM_ENABLED=true
set OLLAMA_MODEL=qwen2.5:3b
```

`/analyze` must stay **200** either way.

## 3. Cause thresholds (engine constants)

In `apps/api/app/engine/assess.py` / `causes.py`:

| Signal | Rough trigger |
|--------|----------------|
| `precip_deficit` | 30d precip / climate &lt; ~0.70, or dry spell ≥10d, or current level deficit/severe |
| `low_soil_storage` | AWC proxy &lt; 60 mm or sand ≥ 55% |
| `runoff` | slope ≥ 3.5% or runoffRisk moderate/high |
| `crop_sensitivity` | crop sensitivity ≥ 0.65 and current ≠ ok |

Inspect `causes[].evidenceIds` and matching adapter `values` in the response / mock bundle.

## 4. Evidence IDs on the fixture

Open [`fixtures/mock_evidence_sample.json`](../fixtures/mock_evidence_sample.json):

- Every cause and recommendation lists `evidenceIds`.
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
