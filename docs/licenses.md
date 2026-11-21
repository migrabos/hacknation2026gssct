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

No generative LLM runtime. Polish narrative sections are deterministic templates over Evidence JSON.

## Data sources

Live adapters fetch these public sources:

| Source | Use | License / access (verify) |
|--------|-----|---------------------------|
| ULDK GUGiK | Cadastral plot geometry | Public GUGiK service terms |
| Open-Meteo | Precipitation / climate | Open-Meteo API terms / CC-ish attribution |
| SoilGrids (ISRIC) | Texture / SOC / AWC proxy | ISRIC data policy |
| Sentinel-2 via Earth Search STAC | NDVI | ESA / AWS Open Data + STAC provider terms |
| IUNG / EDO | Drought class context | Best-effort; agency terms |
| ISOK / Wody Polskie | Nearby water / hydro | Best-effort public layers |

Update this table when Person 2 lands real fetch dates, cache TTLs, and exact attribution strings in `sources[]`.

## Disclosure checklist

- [x] AI disclosure: no generative LLM in product path
- [x] Live adapters documented in README
- [ ] Final license grant language for KOWR (team legal / contest rules)
- [ ] Person 2 fills live source fetch dates in README
