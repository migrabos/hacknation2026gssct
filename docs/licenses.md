# Licenses — Retencja (HackNation 2026 / KOWR)

Intent: all listed components allow KOWR use if IP transfers after the contest. Confirm upstream terms before commercial redistribution.

## Software (this API)

| Component | License (typical) | Notes |
|-----------|-------------------|-------|
| FastAPI | MIT | Web framework |
| Pydantic / pydantic-settings | MIT | Schemas + config |
| Uvicorn | BSD-3-Clause | ASGI server |
| httpx | BSD-3-Clause | Adapter HTTP client |
| pytest / pytest-asyncio | MIT | Tests |
| This repository code | TBD by team | Keep private until submit; grant KOWR rights if required |

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
| IUNG SMSR / MRiRW 2019 (Dz.U. 2019 poz. 739) | Crop×soil KBW drought thresholds | Regulation tables; https://susza.iung.pulawy.pl/progi/ |
| IUNG-PIB SMSR soil category map (WMS `sgeo.iung.pl/geoserver/Susza/wms`, layer `katgl_landuse2024`) | Soil drought category I–IV per plot | Public WMS of IUNG-PIB (prepared for MRiRW); no explicit licence published – used with attribution, https://susza.iung.pulawy.pl/mapa-kategorii/ |
| ERA5-Land soil moisture (Copernicus C3S) via Open-Meteo | Root-zone soil water vs 10 years | CC BY 4.0 (Open-Meteo / Copernicus) |
| USDA NRCS TR-55 (1986), NEH 630 ch. 7 & 10 | SCS Curve Number runoff, hydrologic soil groups | US Government work, public domain |
| FAO Irrigation & Drainage Paper 33 | Seasonal crop Ky (yield response) | FAO open publication; cite Doorenbos & Kassam 1979 |
| FAO-56 (Allen et al. 1998) | Mid-season Kc for crop water need | FAO open publication |

## Disclosure checklist

- [x] AI disclosure: no generative LLM or ML in the product path
- [x] Live vs precomputed data documented in README (with dates)
- [x] Per-source license strings in the API response (`sources[].license`)
- [ ] Repository license / grant language for KOWR (team decision)
- [ ] Decide on react-leaflet (Hippocratic License) before IP transfer
- [ ] Open-Meteo key or self-hosting for any commercial / institutional use
