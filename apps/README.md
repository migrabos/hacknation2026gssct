# apps/

Deployable application packages for Retencja (HackNation 2026 — KOWR).

| Path | Owner | Role |
|------|-------|------|
| [`api/`](api/) | Person 2 + 3 | FastAPI: plot/adapters contract, deterministic Evidence engine, Polish template narrative |
| `web/` | Person 1 | Next.js (App Router) Polish farmer UI — not in this package yet |

## API (shipped)

Core endpoints: `POST /analyze`, `GET /crops`, `GET /health`.

```bash
cd apps/api
python -m pip install -r requirements.txt
copy .env.example .env
uvicorn app.main:app --reload --port 8000
```

See the [root README](../README.md) for env vars, architecture, and verification notes.

## Layout inside `api/`

```text
app/
  adapters/    live GIS/meteo/soil/sat/drought bundle
  engine/      deterministic assess → causes → ranked actions
  narrative/   Polish template narrative
  schemas/     Evidence / Report / request models
  actions/     fixed action catalog
  crops/       crop drought-sensitivity table
tests/         pytest (deterministic engine + grounding)
```
