# Retencja — KOWR Water Retention DSS (HackNation 2026)

Browser-facing decision support for Polish farmers: for *this* cadastral plot and *this* crop, produce a live, evidence-grounded water report — **ocena → przyczyny → retencja/agrotech → nawadnianie (optional)**.

This repo currently ships the **Role 3 core**: FastAPI + deterministic Evidence engine + grounded Ollama narrator (template fallback). Mock adapters stand in until Person 2 wires live GIS/meteo/soil sources. No web UI in this package yet.

---

## Quick start

```bash
cd apps/api
python -m pip install -r requirements.txt
copy .env.example .env   # Windows; or: cp .env.example .env

# Optional LLM (local Ollama)
ollama pull qwen2.5:3b

uvicorn app.main:app --reload --port 8000
```

- Health: `GET http://127.0.0.1:8000/health`
- Crops: `GET http://127.0.0.1:8000/crops`
- Analyze: `POST http://127.0.0.1:8000/analyze`

```bash
curl -X POST http://127.0.0.1:8000/analyze ^
  -H "Content-Type: application/json" ^
  -d "{\"plotId\":\"141201_2.0001.123\",\"cropId\":\"kukurydza\",\"analysisDate\":\"2025-07-15\"}"
```

### Tests

```bash
cd apps/api
pytest -q
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

Sample Evidence for frontend wiring: [`fixtures/mock_evidence_sample.json`](fixtures/mock_evidence_sample.json).

---

## Environment

| Variable | Default | Meaning |
|----------|---------|---------|
| `LLM_ENABLED` | `true` | Use Ollama; `false` → template narrative |
| `OLLAMA_BASE_URL` | `http://127.0.0.1:11434` | Local Ollama |
| `OLLAMA_MODEL` | `qwen2.5:3b` | Fast small model (override OK) |
| `OLLAMA_TIMEOUT_S` | `12` | Soft-fail to template on timeout |
| `OLLAMA_MAX_TOKENS` | `700` | Cap |
| `OLLAMA_TEMPERATURE` | `0.2` | Low creativity |
| `ENGINE_VERSION` | `0.1.0` | Report meta |

If Ollama is down or validation fails, `/analyze` still returns **200** with `narrative.mode = "template"`.

---

## Mock vs live adapters

Adapters implement `AdapterProtocol` and return `AdapterResult` (`values`, `sources`, `fetchedAt`, `coverage`, `errors`). Current implementations in `apps/api/app/adapters/mocks.py` are **deterministic mocks** seeded from `plotId` / lat-lng / date — plot-specific demos without live GIS.

Person 2 should replace mocks with ULDK, Open-Meteo, SoilGrids, Sentinel-2 STAC, IUNG/EDO, ISOK — same envelope, no engine changes.

---

## AI disclosure

- **Narrator only:** local [Ollama](https://ollama.com/) + model `qwen2.5:3b` (override via `OLLAMA_MODEL`; fallback install already present: `qwen3:8b`).
- No cloud LLM keys required.
- Structured Report is authoritative; narrative is optional polish.

---

## Limits (honest)

- Thresholds are simple water-balance proxies, not a calibrated hydrological model.
- Satellite NDVI / IUNG drought are stubs in the mock layer.
- National live coverage depends on Person 2 adapters.
- Irrigation is never first advice when retention applies.

Verification notes for jury: [`docs/verify.md`](docs/verify.md). Licenses: [`docs/licenses.md`](docs/licenses.md).

---

## Repo layout (core)

```text
apps/api/          FastAPI + engine + narrative + tests
fixtures/          mock_evidence_sample.json for Person 1
docs/roles/        per-person playbooks
docs/verify.md
docs/licenses.md
AGENTS.md          contest big picture
```
