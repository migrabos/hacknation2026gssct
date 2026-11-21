# Retencja — KOWR Water Retention DSS (HackNation 2026)

Browser-facing decision support for Polish farmers: for *this* cadastral plot and *this* crop, produce a live, evidence-grounded water report — **ocena → przyczyny → retencja/agrotech → nawadnianie (optional)**.

Integrated stack: Next.js UI (`apps/web`) → one FastAPI app (`apps/api`) → **live public data adapters** (ULDK, GUGiK NMT, OpenStreetMap, Open-Meteo/ERA5, SoilGrids, Sentinel-2, EDO) → deterministic Evidence engine → grounded Ollama narrator (template fallback).

**Shared contract:** [`apps/web/lib/types.ts`](apps/web/lib/types.ts) ⇄ [`apps/api/app/schemas/evidence.py`](apps/api/app/schemas/evidence.py) (same field names). `apps/api/tests/test_contract_web.py` validates the web's `mocks/*.json` against the API schema, so drift fails the tests.

---

## Quick start

```bash
cd apps/api
python -m pip install -r requirements.txt
copy .env.example .env   # Windows; or: cp .env.example .env

# Optional LLM (local Ollama)
ollama pull qwen2.5:3b

uvicorn app.main:app --reload --port 8000   # or: uvicorn main:app
```

Web (second terminal):

```bash
cd apps/web
npm install
NEXT_PUBLIC_API_MODE=real NEXT_PUBLIC_API_URL=http://localhost:8000 npm run dev
```

- Plot pick: `GET /plot/by-point?lat=..&lng=..`, `GET /plot/by-id?id=..` (add `&context=true` for slope + water)
- Health: `GET http://127.0.0.1:8000/health`
- Crops: `GET http://127.0.0.1:8000/crops`
- Analyze: `POST http://127.0.0.1:8000/analyze`

```bash
curl -X POST http://127.0.0.1:8000/analyze ^
  -H "Content-Type: application/json" ^
  -d "{\"plotId\":\"040308_5.0004.17220\",\"cropId\":\"kukurydza\",\"analysisDate\":\"2026-07-15\"}"
```

### Tests

```bash
cd apps/api
pytest -q          # runs on ADAPTERS=mock, no network
python -m warm_cache   # pre-warm cache for rehearsal plots (live network)
```

---

## Architecture

```text
Farmer / Next.js (Person 1, later)
  → POST /analyze
  → Mock adapters (plot, meteo, soil, sat, drought, hydro)  [Person 2 swaps live]
  → Deterministic engine → Evidence / Report (truth)
  → Grounded narrator (Ollama) OR Polish template fallback
  → JSON report (UI renders structured fields even if LLM fails)
```

**Grounding rule:** the engine owns numbers and action IDs. The LLM may only restate Evidence; a validator rejects invented facts; demo works with `LLM_ENABLED=false`.

Sample report from a real live run (plot 040308_5.0004.17220, kukurydza, 2026-07-15): [`fixtures/mock_evidence_sample.json`](fixtures/mock_evidence_sample.json).

---

## Environment

| Variable | Default | Meaning |
|----------|---------|---------|
| `ADAPTERS` | `live` | `live` = real public APIs; `mock` = deterministic DEMO data (offline; UI shows a DEMO banner) |
| `CORS_ORIGINS` | `http://localhost:3000,http://127.0.0.1:3000` | Allowed browser origins (`*` = any) |
| `ADAPTER_CACHE_DIR` | `apps/api/cache` | Disk cache for adapter responses |
| `LLM_ENABLED` | `true` | Use Ollama; `false` → template narrative |
| `OLLAMA_BASE_URL` | `http://127.0.0.1:11434` | Local Ollama |
| `OLLAMA_MODEL` | `qwen2.5:3b` | Fast small model (override OK) |
| `OLLAMA_TIMEOUT_S` | `12` | Soft-fail to template on timeout |
| `OLLAMA_MAX_TOKENS` | `700` | Cap |
| `OLLAMA_TEMPERATURE` | `0.2` | Low creativity |
| `ENGINE_VERSION` | `0.2.0` | Report meta |

If Ollama is down or validation fails, `/analyze` still returns **200** with `narrative.generatedBy = "template"`.

---

## Data flow (live)

`POST /analyze` → `app/adapters/live.py`: ULDK resolves the plot, then in parallel: terrain + hydro (`plot/resolver.add_plot_context`), `fetch_meteo`, `fetch_soil`, `fetch_sentinel`, `fetch_drought_context`. Every adapter returns the `run_adapter` envelope (`values`, `sources`, `coverage`, `errors`, `fromCache`), is timeout-bounded and disk-cached.

`app/engine/facts.py` copies adapter values into flat facts and builds `evidence[]`, `sources[]` (status ok/partial/failed, live/cached) and `missingData[]`. Rules in `assess.py` / `causes.py` / `rank.py` cite evidence ids only. Typical timing: ~10 s cold, <1 s warm.

`ADAPTERS=mock` swaps in `app/adapters/mocks.py` (same value keys, every source named "DEMO – …").

---

## AI disclosure

- **Narrator only:** local [Ollama](https://ollama.com/) + model `qwen2.5:3b` (override via `OLLAMA_MODEL`; fallback install already present: `qwen3:8b`).
- No cloud LLM keys required.
- Structured Report is authoritative; narrative is optional polish.

---

## Limits (honest)

- Thresholds are simple water-balance proxies, not a calibrated hydrological model.
- NDVI is shown as context only (no multi-year NDVI baseline yet); EDO CDI is a regional indicator.
- Water features come from OpenStreetMap (Overpass); when Overpass is unreachable, hydro is reported as missing.
- Irrigation is never first advice when retention applies.

Verification notes for jury: [`docs/verify.md`](docs/verify.md). Licenses: [`docs/licenses.md`](docs/licenses.md).

---

## Repo layout (core)

```text
apps/api/          FastAPI + engine + narrative + tests
fixtures/          mock_evidence_sample.json — real /analyze output
docs/roles/        per-person playbooks
docs/verify.md
docs/licenses.md
AGENTS.md          contest big picture
```
