# Person 3 — Engine + narrative templates + docs / demo package

**You own:** Evidence/Report schema, scores, causes, ranked actions, Polish template narrative, README, slides, demo film edit, sample reports, license table, verification notes  
**You do not own:** Map basemap polish, adapter HTTP details, frontend layout  
**Pair with:** **1** on UI field names + film walkthrough; **2** on adapter values / schema lock

**Stack:** FastAPI + Pydantic — `apps/api/engine/` + `apps/api/narrative/`; docs in `README.md` + `docs/pitch/`

---

## Goal

Turn raw adapter outputs into a **deterministic**, contest-ordered report (assess → causes → retention/agrotech → irrigation last), fill short Polish template prose from Evidence, and ship a submission package the jury can run and trust.

---

## Must ship

### Engine (truth layer)

1. Pydantic models: `Evidence`, `Report`, causes, recommendations, sources, limitations
2. **Moisture assessment**
   - Current situation
   - Multi-year susceptibility (separate fields — don’t mix them)
3. **Cause labels** (multi-label OK):
   - `precip_deficit`
   - `low_soil_storage`
   - `runoff`
   - `crop_sensitivity`
4. **Ranked actions** from a **fixed catalog**
   - Order: retencja krajobrazowa → gleba/agrotechnika → nawadnianie (optional/last)
5. **Crop table** — kukurydza, ziemniak, warzywa, zboża, etc. + drought sensitivity weights
6. Confidence + missing-data propagation into the report
7. Orchestrate `POST /analyze`: Person 2 plot → adapters in parallel (Person 2: meteo/soil/terrain/hydro · Person 1: NDVI/drought) → your engine → template narrative
8. `docs/verify.md` — how jury can spot-check numbers against sources

### Fixed action catalog examples (IDs stable)

| ID | Type | Idea |
|----|------|------|
| `residues` | agrotech | leave crop residues |
| `cover_crops` | agrotech | międzyplony |
| `reduce_tillage` | agrotech | less intensive tillage |
| `small_pond` | retention | oczka / małe zbiorniki |
| `buffer_strips` | retention | strefy buforowe |
| `ditch_retention` | retention | rowy melioracyjne as retention |
| `irrigation_timing` | irrigation | only if deficit + crop need |

### Template narrative + docs

9. **Template narrative** — Polish sentences built only from Evidence fields / action catalog titles
10. **README** with launch, architecture, sources, live vs cached + dates, AI disclosure, licenses, limits, verification
11. **≤10 slide PDF** + **≤3 min demo film** + script (Person 1 drives UI)
12. **2–3 sample report PDFs** from the real prototype
13. **License table** (OSS + data) — must allow KOWR use if you win IP transfer

---

## Grounding rules (non-negotiable)

**Pipeline:**
1. Engine builds Evidence (truth)
2. Template → `narrative.sections[]` from those fields only
3. UI shows structured cards first, narrative second

---

## Scientific sequence (do not skip)

```
ocena sytuacji wodnej
  → identyfikacja przyczyn
    → rekomendacje retencyjne
      → działania agrotechniczne
        → ewentualne nawadnianie
```

Align with KOWR appendix: water balance thinking, not rainfall-only; retention before irrigation; show uncertainty.

---

## Hour-by-hour focus

| Hours | What you do |
|-------|-------------|
| 0–2 | Draft schema / Pydantic; team locks it; mock Evidence for 1; README outline; license list start |
| 2–8 | Engine vs **mocked** adapters; real plot+meteo+soil by checkpoint; action catalog PL copy |
| 8–14 | Full cause→action ranking; template narrative polish; first sample reports; NDVI when 2 delivers sat |
| 14–20 | Tune thresholds; verify notes; slides; record film with 1; freeze license table |
| 20–24 | Freeze rules; package submission; science Q&A support |

---

## Report JSON you own (truth layer)

```
plot, crop, analysisDate
moistureAssessment
causes[]
recommendations.retention[]
recommendations.agrotech[]
recommendations.irrigation?   # optional
sources[]
limitations[]
missingData[]
narrative?                     # template prose from Evidence
```

---

## Suggested files

```
apps/api/engine/             # schema, scores, ranking
apps/api/narrative/
  templates_pl.py
  run.py
README.md
docs/verify.md
docs/pitch/
  slides.pdf                 # ≤10 slides
  demo-script.md
  sample-reports/
licenses.md                  # or section inside README
```

---

## Demo film script (≤3 min)

1. Open site → one-line value prop (15s)
2. Enter plot ID or map click + crop + date (30s)
3. Show pipeline loading steps (15s)
4. Walk report: ocena → przyczyny → retencja/agrotech → optional nawadnianie (90s)
5. Show sources / uncertainty / PDF print (30s)
6. Close on “retention first” (15s)

---

## Acceptance checks

- [ ] Same inputs → same structured scores (deterministic)
- [ ] Current drought ≠ chronic risk (two fields)
- [ ] No recommendation without plot conditions recognized
- [ ] Irrigation never appears as the only/first advice when retention applies
- [ ] Missing adapter data lowers confidence / fills `missingData` — no fake precision
- [ ] Person 1 can render report from your JSON (structured Evidence is enough)
- [ ] Action IDs only from the fixed catalog
- [ ] Template narrative only restates Evidence fields
- [ ] README lists every data source + live vs cached + dates + AI disclosure
- [ ] Slides ≤10; film ≤3:00; ≥2 sample reports; license table complete

---

## Pitch role

Answer science / methodology / “why this recommendation?” and grounding (“engine owns numbers”); own docs/licenses submission checklist.
