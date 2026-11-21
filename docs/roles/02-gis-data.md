# Person 2 — GIS + Data adapters

**You own:** ULDK plot resolve, geometry, map GeoJSON, DEM/slope, hydro nearby flags, external data fetchers, disk cache, timeouts, source metadata  
**You do not own:** Final UX polish, cause/action business rules, LLM prompts, pitch slides/film edit  
**Pair with:** **1** on map component; **3** on adapter → engine contract + bbox/centroid helpers

**Stack:** FastAPI — `apps/api/` plot/terrain/hydro + `apps/api/adapters/` + local cache dir

---

## Goal

Any Polish działka (by ID or map click) becomes clean geometry + centroid + terrain/hydro context, then multi-year meteo/soil/satellite/drought signals — fast, cached, and honest about failures.

---

## Must ship

### Plot / GIS

1. `resolve_plot(id)` → geometry, area, centroid, voivodeship (or best available attrs)
2. `resolve_point(lat, lng)` → containing plot (same shape as above)
3. GeoJSON for Person 1’s map (`GET /plot/{id}` or include in analyze response)
4. **Slope / runoff risk** from DEM sample (coarse is OK)
5. **Nearby water** flag (distance classes) if public API allows — else honest `missingData: "brak danych hydro"`
6. Smoke tests for **≥3 known plot IDs** in different regions (jury rehearsal set)

### Data adapters

7. **Open-Meteo** — ~10y daily precip/temp at centroid; dry-spell stats
8. **SoilGrids** — texture (sand/clay) + organic carbon → storage proxy inputs
9. **Sentinel-2 via Earth Search STAC** — cloud-filtered NDVI time series; fail soft if cloudy
10. **IUNG Monitoring Suszy / EDO** — drought context (best-effort; WMS OK if documented)
11. **Uniform adapter interface** every source returns:
    ```
    { values, sources, fetchedAt, coverage, errors }
    ```
12. **Disk cache** keyed by `(bbox|point, dateRange, source)` + **20s hard timeout** per source  
    Partial results OK — never block the whole analyze on one dead API

---

## Hour-by-hour focus

| Hours | What you do |
|-------|-------------|
| 0–2 | Confirm ULDK + adapter interface with 3; pick 5 rehearsal plots; set cache dir; list licenses for 3’s README |
| 2–8 | Plot resolve by ID + click + GeoJSON; **Open-Meteo + SoilGrids** first (hour-8 checkpoint) |
| 8–14 | DEM slope / runoff proxy; hydro best-effort; Sentinel NDVI + cache warming; IUNG/EDO best-effort |
| 14–20 | Fail soft; tighten timeouts; never invent hydro or fake precision |
| 20–24 | Freeze; pre-warm cache for 5 rehearsal plots before film/pitch |

Priority if time runs out: **Plot resolve → Meteo → Soil → Satellite → Drought → Hydro**.

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
    base.py          # protocol + timeout + cache wrapper
    open_meteo.py
    soilgrids.py
    sentinel_stac.py
    drought_iung.py  # or edo_wms.py
  cache/             # gitignored data files
```

Shared helpers used by adapters: `bbox_from_geometry()`, `centroid()`.

---

## Data sources

| Need | Source | Notes |
|------|--------|-------|
| Cadastral plot | ULDK GUGiK | national coverage |
| Basemap (frontend) | Geoportal / OSM tiles via Person 1’s map | |
| Terrain | DEM NMT/NMPT WCS or public elevation API | coarse OK |
| Hydro | ISOK Hydroportal / Wody Polskie | best-effort |
| Meteo | Open-Meteo Historical + recent | precip, temp, dry spells |
| Soil | ISRIC SoilGrids | storage capacity inputs |
| Satellite | earth-search.aws.element84.com/v1 | no account preferred |
| Drought | susza.iung.pulawy.pl / EDO WMS | document if layer-only |

All free/legal; document URLs + fetch time for Person 3’s README. No paid APIs unless team pre-approves and you disclose a free alternative.

---

## Acceptance checks

- [ ] Known plot IDs resolve across Poland (not just one województwo)
- [ ] Map click returns a plot or a clear “nie znaleziono działki”
- [ ] Geometry + centroid always present when resolve succeeds
- [ ] Slope/runoff either computed or explicitly missing; hydro never faked
- [ ] Meteo + soil return real numbers for rehearsal plots
- [ ] Second call for same plot hits cache and is clearly faster
- [ ] Sentinel failure does not crash `/analyze`
- [ ] Every payload includes `fetchedAt` + source URL/name
- [ ] Person 3 can run engine with live plot+meteo+soil by hour 8 (sat stub OK)

---

## Pitch role

Answer “how do you find the działka?”, “which open data?”, and “live vs cached?” — keep fetch-date list ready for Person 3’s README.
