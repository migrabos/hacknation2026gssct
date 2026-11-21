# AGENTS.md — KOWR Water Retention DSS (HackNation 2026)

> **Read this first.** Big-picture plan for any AI (or human) joining this hackathon build.
> Role detail lives in [`docs/roles/`](docs/roles/). Do not invent scope outside this doc.

---

## Mission

Build a **browser web app for Polish farmers** that, for *this* cadastral plot (`działka`) and *this* crop, produces a **live, evidence-grounded water report**:

1. Moisture assessment  
2. Causes  
3. Retention / agrotech recommendations  
4. Optional irrigation **last**

**Working name:** *Retencja* (finalize in hour 0).

**Contest:** HackNation 2026 — KOWR challenge (water retention decision support).

---

## Non-negotiable rules

| Rule | Detail |
|------|--------|
| Live computation | No pre-baked answers for a fixed plot set |
| National coverage | Any Polish działka ewidencyjna |
| Report order | ocena → przyczyny → retencja/agrotech → nawadnianie (optional) |
| Evidence first | Deterministic engine owns truth; template narrative only restates it |
| No hallucinations | Engine / templates cannot invent numbers, action IDs, or measures |
| Honesty | Sources + uncertainty + `missingData` always visible |
| Speed | Prefer &lt;30s (warm cache OK for demo plots) |
| Polish UI | Farmer language, no GIS jargon |
| Deliverables | Private repo, README, ≤10 slides, ≤3 min film, PDF/print |
| Scoring focus | Practical value 25% + data credibility 25% |

**Out of scope:** accounts, custom ML training, paid APIs without disclosure, irrigation-as-hero, national load testing.

---

## Stack

| Layer | Choice |
|-------|--------|
| Frontend | Next.js (App Router) + TypeScript — `apps/web/` |
| Backend | Python FastAPI — `apps/api/` |
| Deploy | Web → Vercel · API → Railway / Fly / Render |
| Infra | Docker Compose locally |
| Narrative | Polish template prose over Evidence JSON (no generative LLM) |

**Core API:** `POST /analyze` · `GET /crops` · `GET /health`

---

## Architecture

```text
Farmer browser
  → Next.js (PL UI)
    → FastAPI
      → Plot resolver (ULDK)          [Person 2]
      → Adapters: meteo/soil/DEM/hydro [Person 2]
      → Adapters: NDVI/drought        [Person 1, on Person 2's base.py]
      → Deterministic engine          [Person 3]  → Evidence JSON (truth)
      → Polish template narrative     [Person 3]  → short section prose
    → Report UI + print/PDF           [Person 1]
```

**Grounding pipeline:** Engine computes Evidence → template fills Polish section prose from those fields → UI always renders structured Evidence.

---

## Repo layout (target)

```text
/
  AGENTS.md                 # this file — AI big picture
  apps/web/                 # Person 1 — Next.js
  apps/api/                 # Person 2 + 3 (+ 1 for sat/drought adapters) — FastAPI
  docker-compose.yml
  README.md                 # Person 3 owns
  docs/
    roles/                  # per-person playbooks (3 roles)
    pitch/                  # slides, demo script, samples
    verify.md               # how jury spot-checks numbers
```

---

## Team of 3 — who owns what

| Person | Role | Playbook |
|--------|------|----------|
| **1** | Frontend + UX + sat/drought adapters | [docs/roles/01-frontend-ux.md](docs/roles/01-frontend-ux.md) |
| **2** | GIS + core data adapters (plot, meteo, soil, terrain, hydro) | [docs/roles/02-gis-data.md](docs/roles/02-gis-data.md) |
| **3** | Engine + template narrative + docs/demo | [docs/roles/03-engine-ai-docs.md](docs/roles/03-engine-ai-docs.md) |

**Pairing (soft deps, not blockers):**

- **1 ↔ 3** — lock report / Evidence field names early; film walkthrough  
- **2 ↔ 3** — adapter → engine contract; Evidence schema before ranking  
- **1 ↔ 2** — map GeoJSON / plot pick; `adapters/base.py` contract (2 ships it by hour 2, 1 builds NDVI + drought on it)  

Roles run **in parallel** after hour 2. Mock what you depend on; do not wait.

---

## Shared 24h schedule

| Hours | Mode | Checkpoint |
|-------|------|------------|
| **0–2** | Kickoff together | Schema locked, empty deploys, 5 rehearsal plots picked |
| **2–8** | Parallel build | `/analyze` = real plot + meteo + soil + engine (sat stub OK) |
| **8–14** | Fusion + narrative | E2E on ≥3 plots, honest partial data, &lt;30s warm |
| **14–20** | Polish | UX + slides + film + license freeze |
| **20–24** | Freeze + submit | Bugfixes only; package uploaded; repo stays private |

---

## Evidence / report shape (source of truth)

Owned by **Person 3**. Template fills narrative prose; UI always renders structured Evidence.

```text
plot, crop, analysisDate
moistureAssessment          # current situation ≠ multi-year susceptibility
causes[]                    # precip_deficit | low_soil_storage | runoff | crop_sensitivity
recommendations.retention[]
recommendations.agrotech[]
recommendations.irrigation? # optional, last
sources[]
limitations[]
missingData[]
narrative?                  # filled by Person 3
```

**Action IDs** come from a **fixed catalog**, e.g. `residues`, `cover_crops`, `reduce_tillage`, `small_pond`, `buffer_strips`, `ditch_retention`, `irrigation_timing`.

---

## Data sources (open / documented)

| Need | Source | Owner |
|------|--------|-------|
| Cadastral plot | ULDK GUGiK | 2 |
| Terrain / slope | DEM / public elevation | 2 |
| Hydro nearby | ISOK / Wody Polskie (best-effort) | 2 |
| Meteo (~10y) | Open-Meteo | 2 |
| Soil | SoilGrids | 2 |
| Satellite NDVI | Sentinel-2 via Earth Search STAC | 1 |
| Drought context | IUNG / EDO (best-effort) | 1 |

Priority if time runs out — Person 2: **Plot resolve → Meteo → Soil → Slope → Hydro**; Person 1: **UI → Satellite → Drought**. Fail soft; never fake precision.

No forecasting / ML anywhere in the data layer: adapters fetch data and compute simple stats (sums, averages, dry spells, slope). Interpretation belongs to the engine (Person 3).

---

## AI coding guidelines

When implementing in this repo:

1. Prefer the owner’s folder (`apps/web` vs `apps/api/...`); don’t cross-own without need.  
2. Keep adapters timeout-bounded (~20s) with disk cache; partial results OK.  
3. Engine output must be **deterministic** for the same inputs.  
4. Narrative templates may only restate Evidence fields; never invent numbers or action IDs.  
5. Surface `missingData` / sources in API and UI — hiding gaps is a contest fail.  
6. Polish copy for farmers; English OK in code/comments.  
7. Secrets only in env templates — never commit keys.  
8. Before expanding scope, check **Out of scope** above.

---

## Submit checklist

- [ ] Live URL (web + API) warm for 5 rehearsal plots  
- [ ] README: launch, architecture, sources, live vs cached + dates, AI tools, licenses, limits, verification  
- [ ] ≤10 slide PDF · ≤3 min demo film · ≥2 sample reports from real runs  
- [ ] Private repo · license table allows KOWR use if IP transfers  
- [ ] Finals roles: **1** drives UI · **3** science + engine · **2** data/coverage backup  

---

## Quick start for a new AI session

1. Read this file end-to-end.  
2. Open the relevant [`docs/roles/*.md`](docs/roles/) for the task you were assigned.  
3. Check repo state (`apps/`, schema, `/analyze`) before scaffolding duplicates.  
4. Ship the hour-band checkpoint for the current clock — prefer demo-ready over perfect science.
