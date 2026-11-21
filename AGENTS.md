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
| Evidence first | Deterministic engine owns truth; LLM only narrates |
| No hallucinations | LLM cannot invent numbers, action IDs, or measures |
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
| AI | LLM **only** for grounded Polish narrative over Evidence JSON |

**Core API:** `POST /analyze` · `GET /crops` · `GET /health`

---

## Architecture

```text
Farmer browser
  → Next.js (PL UI)
    → FastAPI
      → Plot resolver (ULDK)          [Person 2]
      → Adapters (meteo/soil/sat/…)   [Person 2]
      → Deterministic engine          [Person 3]  → Evidence JSON (truth)
      → Grounded LLM narrator         [Person 3]  → Polish narrative (optional)
    → Report UI + print/PDF           [Person 1]
```

**Grounding pipeline:** Engine computes Evidence → LLM narrates only those facts → UI renders structured fields even if LLM fails (template fallback).

---

## Repo layout (target)

```text
/
  AGENTS.md                 # this file — AI big picture
  apps/web/                 # Person 1 — Next.js
  apps/api/                 # Person 2 + 3 — FastAPI
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
| **1** | Frontend + UX | [docs/roles/01-frontend-ux.md](docs/roles/01-frontend-ux.md) |
| **2** | GIS + Data adapters | [docs/roles/02-gis-data.md](docs/roles/02-gis-data.md) |
| **3** | Engine + grounded AI + docs/demo | [docs/roles/03-engine-ai-docs.md](docs/roles/03-engine-ai-docs.md) |

**Pairing (soft deps, not blockers):**

- **1 ↔ 3** — lock report / Evidence field names early; film walkthrough  
- **2 ↔ 3** — adapter → engine contract; schema before LLM prompts  
- **1 ↔ 2** — map GeoJSON / plot pick  

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

Owned by **Person 3**. LLM fills narrative only; UI must work without it.

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

**Action IDs** come from a **fixed catalog** (never invented by the LLM), e.g. `residues`, `cover_crops`, `reduce_tillage`, `small_pond`, `buffer_strips`, `ditch_retention`, `irrigation_timing`.

---

## Data sources (open / documented)

| Need | Source | Owner |
|------|--------|-------|
| Cadastral plot | ULDK GUGiK | 2 |
| Terrain / slope | DEM / public elevation | 2 |
| Hydro nearby | ISOK / Wody Polskie (best-effort) | 2 |
| Meteo (~10y) | Open-Meteo | 2 |
| Soil | SoilGrids | 2 |
| Satellite NDVI | Sentinel-2 via Earth Search STAC | 2 |
| Drought context | IUNG / EDO (best-effort) | 2 |

Priority if time runs out (Person 2): **Plot resolve → Meteo → Soil → Satellite → Drought → Hydro**. Fail soft; never fake precision.

---

## AI coding guidelines

When implementing in this repo:

1. Prefer the owner’s folder (`apps/web` vs `apps/api/...`); don’t cross-own without need.  
2. Keep adapters timeout-bounded (~20s) with disk cache; partial results OK.  
3. Engine output must be **deterministic** for the same inputs.  
4. Never let the LLM invent facts — validate against Evidence; ship template fallback.  
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
- [ ] Finals roles: **1** drives UI · **3** science + AI grounding · **2** data/coverage backup  

---

## Quick start for a new AI session

1. Read this file end-to-end.  
2. Open the relevant [`docs/roles/*.md`](docs/roles/) for the task you were assigned.  
3. Check repo state (`apps/`, schema, `/analyze`) before scaffolding duplicates.  
4. Ship the hour-band checkpoint for the current clock — prefer demo-ready over perfect science.
