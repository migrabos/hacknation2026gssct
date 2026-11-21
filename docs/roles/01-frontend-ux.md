# Person 1 — Frontend + UX (Next.js)

**You own:** Polish UI, map integration, forms, report UX, print/PDF, loading & error states, live demo UI walkthrough  
**You do not own:** GIS math, data adapters, engine thresholds, LLM prompts, README/slides package  
**Pair with:** **3** early on report / Evidence field names; **2** on map GeoJSON

**Stack:** Next.js App Router, TypeScript — `apps/web/`

---

## Goal

A farmer with no GIS skills opens the browser, picks a działka + crop, waits, and gets a clear Polish report they can print. You also drive the live UI in the demo film and finals.

---

## Must ship

1. **Landing** — brand + one short sentence + CTA “Sprawdź działkę”
2. **Input screen**
   - Plot ID **or** map click
   - Crop select
   - Analysis date (default today; allow any date in last 10 years)
3. **Loading** — show pipeline steps: ocena → przyczyny → retencja → nawadnianie
4. **Report view** (contest order)
   - Plain Polish, large type, no GIS jargon
   - Moisture assessment
   - Causes with confidence
   - Retention → agrotech → optional irrigation
   - Each recommendation shows “dlaczego” from evidence refs
5. **Sources + limitations + missing-data** banners (never hide gaps)
6. **Print / Save PDF** — browser print stylesheet is enough for MVP
7. **Error states** — plot not found, partial data, timeout, API down
8. **Demo readiness** — warm path for film with Person 3 (you click; they script/edit)

**Stretch (only if core done):** mobile polish (bonus, not required).

---

## Hour-by-hour focus

| Hours | What you do |
|-------|-------------|
| 0–2 | Agree Evidence/report JSON with 3; scaffold Next.js pages; deploy empty Vercel shell |
| 2–8 | Landing + form + **mock report** driven by fake Evidence JSON (don’t block on API) |
| 8–14 | Wire real `POST /analyze`; pipeline loading; print CSS |
| 14–20 | UX pass — farmer language, contrast, one-column report; record film walkthrough with 3 |
| 20–24 | Bugfixes only; drive UI for pitch rehearsal |

---

## Files / surfaces to create

```
apps/web/
  app/page.tsx              # landing
  app/analizuj/page.tsx     # form + map
  app/raport/[id]/page.tsx  # or client state report view
  components/MapPicker.tsx  # consumes Person 2’s GeoJSON
  components/ReportView.tsx
  components/PipelineLoader.tsx
  styles/print.css
```

Call FastAPI: `POST /analyze`, `GET /crops`, `GET /health`.

---

## Acceptance checks

- [ ] Works in Chrome / Edge / Firefox on Windows desktop (no install)
- [ ] Farmer can finish flow without knowing what ULDK/NDVI means
- [ ] Report sections follow mandatory order
- [ ] Print produces a readable PDF
- [ ] If API returns partial data, UI says so plainly
- [ ] Demo path warm-start &lt;30s feels snappy
- [ ] You can run the film click-path without improvising

---

## Pitch role

Drive the live UI in finals (2–3 min). Hand science / AI grounding questions to Person 3.
