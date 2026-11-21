# Person 2 — GIS + core data adapters

**You own:** ULDK plot resolve, geometry, map GeoJSON, `adapters/base.py` (interface + disk cache + timeouts), Open-Meteo, SoilGrids, DEM/slope, hydro nearby flags, source metadata + license list
**You do not own:** Sentinel-2 NDVI + IUNG/EDO drought adapters (→ **Person 1**), final UX, cause/action business rules, pitch slides/film edit
**Pair with:** **1** on map GeoJSON + `base.py` contract (1 builds NDVI/drought adapters on it); **3** on adapter → engine contract + bbox/centroid helpers

**Stack:** FastAPI — `apps/api/plot/` + `apps/api/adapters/` + local cache dir

---

## Goal

Any Polish działka (by ID or map click) becomes clean geometry + centroid + terrain/hydro context, then multi-year meteo + soil signals — fast, cached, and honest about failures.

**No forecasting / ML.** You fetch data and compute simple stats (sums, averages, dry spells, slope). Interpreting them ("is it dry?", "why?", "what to do?") is Person 3's engine.

---

## Must ship

### Plot / GIS

1. `resolve_plot(id)` → geometry, area, centroid, bbox, voivodeship (or best available attrs)
   - ULDK returns EPSG:2180 → reproject to WGS84 (`pyproj`)
2. `resolve_point(lat, lng)` → containing plot (same shape as above)
3. GeoJSON for Person 1's map (`GET /plot/{id}` or include in analyze response)
4. **Slope / runoff risk** from DEM sample — a few elevation points inside the plot → slope % → `runoffRisk: low|medium|high` (coarse is OK)
5. **Nearby water** flag (distance classes), e.g. OSM Overpass / ISOK — else honest `missingData: "brak danych hydro"`
6. Smoke tests that ULDK resolves the 5 rehearsal plot IDs (end-to-end demo smoke tests → Person 1)

### Data adapters

7. **`adapters/base.py` — ship by hour 2** (Person 1 depends on it)
   - Uniform return shape for every source:
     ```
     { values, sources, fetchedAt, coverage, errors }
     ```
   - Disk cache keyed by `(bbox|point, dateRange, source)` + **20s hard timeout** per source
   - Partial results OK — never block the whole analyze on one dead API
   - `open_meteo.py` doubles as the reference adapter for Person 1
8. **Open-Meteo** — ~10y daily precip/temp at centroid; simple stats:
   - precip sum last 30/60/90 days vs multi-year mean for the same window
   - longest dry spell, recent temperature anomaly
9. **SoilGrids** — sand / clay / organic carbon at centroid (raw values; storage-capacity math is Person 3's)
10. **Sources + licenses** — every payload has source URL/name + `fetchedAt`; collect license table for Person 3's README (incl. Person 1's sources)

---

## Hour-by-hour focus

| Hours | What you do |
|-------|-------------|
| 0–2 | Confirm ULDK + adapter interface with 3; **ship `base.py` + cache dir** to 1; pick 5 rehearsal plots with 1 |
| 2–8 | Plot resolve by ID + click + GeoJSON; **Open-Meteo + SoilGrids** (hour-8 checkpoint) |
| 8–14 | DEM slope / runoff proxy; hydro best-effort; help 1 if NDVI adapter is stuck |
| 14–20 | Fail soft; tighten timeouts; never invent hydro or fake precision; license list to 3 |
| 20–24 | Freeze; support 1's cache pre-warm for 5 rehearsal plots |

Priority if time runs out: **Plot resolve → Meteo → Soil → Slope → Hydro**.

---

## Suggested API / modules

```
GET  /plot/by-id?id=...
GET  /plot/by-point?lat=...&lng=...
# returns:
# { plotId, geometry, centroid, areaHa, bbox, voivodeship?,
#   terrain: { slopePct?, runoffRisk? },
#   hydro: { nearbyWater?, distanceClass?, missing? },
#   sources: [...], fetchedAt }

apps/api/
  plot/              # resolve, geometry helpers
  adapters/
    base.py          # protocol + timeout + cache wrapper   (you)
    open_meteo.py    # reference adapter                    (you)
    soilgrids.py     #                                      (you)
    terrain_dem.py   #                                      (you)
    hydro.py         #                                      (you)
    sentinel_stac.py #                                      (Person 1)
    drought_iung.py  # or edo_wms.py                        (Person 1)
  cache/             # gitignored data files
```

Shared helpers used by adapters: `bbox_from_geometry()`, `centroid()`.

---

## Data sources

| Need | Source | Owner | Notes |
|------|--------|-------|-------|
| Cadastral plot | ULDK GUGiK | 2 | national coverage |
| Basemap + parcel overlay | Geoportal WMS / OSM tiles | 1 | frontend only |
| Terrain | DEM NMT WCS or public elevation API | 2 | coarse OK |
| Hydro | OSM Overpass / ISOK / Wody Polskie | 2 | best-effort |
| Meteo | Open-Meteo Historical + recent | 2 | precip, temp, dry spells |
| Soil | ISRIC SoilGrids | 2 | storage capacity inputs |
| Satellite | earth-search.aws.element84.com/v1 | 1 | no account preferred |
| Drought | susza.iung.pulawy.pl / EDO WMS | 1 | document if layer-only |

All free/legal; document URLs + fetch time for Person 3's README. No paid APIs unless team pre-approves and you disclose a free alternative.

---

## Acceptance checks

- [ ] Known plot IDs resolve across Poland (not just one województwo)
- [ ] Map click returns a plot or a clear "nie znaleziono działki"
- [ ] Geometry + centroid always present when resolve succeeds
- [ ] `base.py` available to Person 1 by hour 2
- [ ] Slope/runoff either computed or explicitly missing; hydro never faked
- [ ] Meteo + soil return real numbers for rehearsal plots
- [ ] Second call for same plot hits cache and is clearly faster
- [ ] Every payload includes `fetchedAt` + source URL/name
- [ ] Person 3 can run engine with live plot+meteo+soil by hour 8 (sat stub OK)

---

## Pitch role

Answer "how do you find the działka?", "which open data?", and "live vs cached?" — keep fetch-date list ready for Person 3's README.
