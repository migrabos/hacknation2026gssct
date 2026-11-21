# Person 1 — Frontend + UX (Next.js) + satellite/drought adapters

**You own:** Polish UI, map integration (basemap + parcel overlay), forms, report UX, print/PDF, loading & error states, **Sentinel-2 NDVI adapter**, **IUNG/EDO drought adapter**, rehearsal-plot smoke tests + cache warm-up script, live demo UI walkthrough
**You do not own:** ULDK / geometry, `adapters/base.py`, meteo/soil/DEM/hydro adapters, engine thresholds, README/slides package
**Pair with:** **3** early on report / Evidence field names; **2** on map GeoJSON + `adapters/base.py` contract

**Stack:** Next.js App Router, TypeScript — `apps/web/` · Python adapters in `apps/api/adapters/`

---

## Goal

A farmer with no GIS skills opens the browser, picks a działka + crop, waits, and gets a clear Polish report they can print. You also deliver the satellite + drought signals to the engine and keep the 5 demo plots warm. You drive the live UI in the demo film and finals.

---

## Must ship

### Frontend

1. **Landing** — brand + one short sentence + CTA "Sprawdź działkę"
2. **Input screen**
   - Plot ID **or** map click
   - Map: basemap + Geoportal parcel WMS overlay; highlight selected plot from Person 2's GeoJSON
   - Crop select
   - Analysis date (default today; allow any date in last 10 years)
3. **Loading** — show pipeline steps: ocena → przyczyny → retencja → nawadnianie
4. **Report view** (contest order)
   - Plain Polish, large type, no GIS jargon
   - Moisture assessment
   - Causes with confidence
   - Retention → agrotech → optional irrigation
   - Each recommendation shows "dlaczego" from evidence refs
5. **Sources + limitations + missing-data** banners (never hide gaps)
6. **Print / Save PDF** — browser print stylesheet is enough for MVP
7. **Error states** — plot not found, partial data, timeout, API down

### Data adapters (moved from Person 2)

Build on Person 2's `adapters/base.py` (shipped by hour 2) — same return shape `{ values, sources, fetchedAt, coverage, errors }`, same cache + 20s timeout wrapper. Use `open_meteo.py` as the reference. **No forecasting / ML** — fetch + simple stats only.

8. **Sentinel-2 via Earth Search STAC** (`sentinel_stac.py`)
   - Input: plot bbox + date range
   - Cloud-filtered scenes → NDVI time series (mean over plot) + current vs same-season multi-year mean
   - Fail soft if cloudy / slow → `errors` + `missingData`, never crash `/analyze`
9. **IUNG Monitoring Suszy / EDO** (`drought_iung.py` or `edo_wms.py`) — best-effort drought class at centroid; WMS sample OK if documented
10. Hand source URLs + licenses for both to Person 2 (license list) / Person 3 (README)

### Demo readiness

11. **Smoke tests for the 5 rehearsal plots** (full `/analyze`, different regions) + **cache warm-up script** run before film/pitch
12. Warm path for film with Person 3 (you click; they script/edit)

**Stretch (only if core done):** mobile polish (bonus, not required).

---

## Hour-by-hour focus

| Hours | What you do |
|-------|-------------|
| 0–2 | Agree Evidence/report JSON with 3; get `base.py` from 2; scaffold Next.js pages; deploy empty Vercel shell; pick 5 rehearsal plots with 2 |
| 2–8 | Landing + form + map + **mock report** from fake Evidence JSON (don't block on API); **Sentinel NDVI adapter** |
| 8–14 | Wire real `POST /analyze`; pipeline loading; print CSS; **drought adapter** (best-effort) |
| 14–20 | UX pass — farmer language, contrast, one-column report; smoke tests + warm-up script; record film walkthrough with 3 |
| 20–24 | Bugfixes only; run cache warm-up; drive UI for pitch rehearsal |

Priority if time runs out: **UI flow + report → Satellite → Drought**.

---

## Files / surfaces to create

```
apps/web/
  app/page.tsx              # landing
  app/analizuj/page.tsx     # form + map
  app/raport/[id]/page.tsx  # or client state report view
  components/MapPicker.tsx  # consumes Person 2's GeoJSON
  components/ReportView.tsx
  components/PipelineLoader.tsx
  styles/print.css

apps/api/adapters/
  sentinel_stac.py
  drought_iung.py           # or edo_wms.py

scripts/
  warm_cache.py             # or .sh — hits /analyze for the 5 rehearsal plots
```

Call FastAPI: `POST /analyze`, `GET /crops`, `GET /health`.

---

## Acceptance checks

- [ ] Works in Chrome / Edge / Firefox on Windows desktop (no install)
- [ ] Farmer can finish flow without knowing what ULDK/NDVI means
- [ ] Report sections follow mandatory order
- [ ] Print produces a readable PDF
- [ ] If API returns partial data, UI says so plainly
- [ ] NDVI adapter returns real values for rehearsal plots or an honest error; Sentinel failure does not crash `/analyze`
- [ ] Drought adapter returns a class or explicit `missingData`
- [ ] Smoke tests pass for all 5 rehearsal plots; warm-start &lt;30s feels snappy
- [ ] You can run the film click-path without improvising

---

## Pitch role

Drive the live UI in finals (2–3 min). Hand science / engine questions to Person 3; data-source questions to Person 2.
