# Licenses — Retencja (HackNation 2026 / KOWR)

Intent: every component allows KOWR to use the tool if IP transfers after the contest. The exact attribution string per data source is also emitted at runtime in `sources[].license` (`apps/api/adapters/licenses.py`).

## Software — API (`apps/api`)

| Component | License | Use |
|-----------|---------|-----|
| FastAPI | MIT | Web framework |
| Pydantic / pydantic-settings | MIT | Schemas + config |
| Uvicorn | BSD-3-Clause | ASGI server |
| httpx | BSD-3-Clause | HTTP client for adapters |
| Shapely | BSD-3-Clause | Plot geometry, sampling points |
| pyproj | MIT | EPSG:2180 ⇄ WGS84 |
| rasterio | BSD-3-Clause | Windowed reads of Sentinel-2 COGs (bundles GDAL, MIT/X) |
| NumPy | BSD-3-Clause | Band arithmetic (NDVI/NDMI) |
| Pillow | MIT-CMU (HPND) | Reading EDO WMS PNG colours |
| mapbox-vector-tile | MIT | OpenFreeMap vector tiles (hydro fallback) |
| tzdata | Apache-2.0 | Time zone data |
| pytest / pytest-asyncio | MIT / Apache-2.0 | Tests |

## Software — Web (`apps/web`)

| Component | License | Use |
|-----------|---------|-----|
| Next.js | MIT | App framework |
| React / react-dom | MIT | UI |
| Leaflet | BSD-2-Clause | Map |
| react-leaflet | Hippocratic License 2.1 | React bindings for Leaflet. **Check before KOWR transfer:** HL 2.1 is not an OSI license and adds ethical-use conditions. Replacing it with plain Leaflet is a small change if needed. |
| TypeScript | Apache-2.0 | Build only |

## This repository

| Item | License |
|------|---------|
| Repository code | `TODO: zespół` – choose before submission (e.g. MIT, or full transfer of rights to KOWR per contest rules) |

## AI / models

No generative LLM and no ML model in the runtime. Polish narrative sections are deterministic templates over Evidence JSON. AI coding tools used during development are listed in the README ("AI disclosure").

## Data sources (all fetched live, except the PRG indexes)

| Source | Use | License / terms |
|--------|-----|-----------------|
| ULDK GUGiK | Plot geometry, TERYT ID, plot by click | GUGiK data free of charge – Prawo geodezyjne i kartograficzne, art. 40a |
| KIEG GUGiK (EGiB) | Land use, soil valuation classes | as above |
| GUGiK NMT | Heights → slope, lowest point | as above |
| PRG GUGiK (precomputed 2026-11-21) | Village (obręb) search index | as above |
| Geoportal ORTO (WMS/WMTS) | Orthophoto basemap in the web map | as above |
| Open-Meteo Historical / Forecast / Elevation | Precipitation, ET0, temperature; DEM fallback | Data CC BY 4.0 (ERA5 / Copernicus C3S, Copernicus DEM). **The free API is non-commercial only.** KOWR production needs a paid key or a self-hosted Open-Meteo instance. |
| NASA POWER | Meteo fallback | NASA Earth Science Data Policy – public, citation requested |
| ISRIC SoilGrids 2.0 | Sand / clay / SOC → water capacity (Saxton & Rawls 2006) | CC BY 4.0 |
| Sentinel-2 L2A via Element84 Earth Search STAC (AWS Open Data) | NDVI, NDMI, bare soil, standing water | Copernicus Sentinel data – full, free and open (EU Reg. 1159/2013) |
| Copernicus EMS – European Drought Observatory | Regional drought indicator (CDI) | CC BY 4.0 |
| OpenStreetMap (Overpass API) | Rivers, streams, ditches, ponds near the plot | © OpenStreetMap contributors – ODbL 1.0 |
| OpenFreeMap vector tiles | Hydro fallback (OSM-derived) | OSM data ODbL 1.0; OpenFreeMap free, no key |
| OpenStreetMap tiles | Basemap in the web map | ODbL 1.0 data, OSM Tile Usage Policy (light use only; self-host or use a provider for production) |

## Disclosure checklist

- [x] AI disclosure: no generative LLM or ML in the product path
- [x] Live vs precomputed data documented in README (with dates)
- [x] Per-source license strings in the API response (`sources[].license`)
- [ ] Repository license / grant language for KOWR (team decision)
- [ ] Decide on react-leaflet (Hippocratic License) before IP transfer
- [ ] Open-Meteo key or self-hosting for any commercial / institutional use
