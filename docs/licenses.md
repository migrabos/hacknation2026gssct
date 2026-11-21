# Licenses — Retencja (HackNation 2026 / KOWR)

Intent: all listed components allow KOWR use if IP transfers after the contest. Confirm upstream terms before commercial redistribution.

## Software (this API)

| Component | License (typical) | Notes |
|-----------|-------------------|-------|
| FastAPI | MIT | Web framework |
| Pydantic / pydantic-settings | MIT | Schemas + config |
| Uvicorn | BSD-3-Clause | ASGI server |
| httpx | BSD-3-Clause | Ollama HTTP client |
| pytest / pytest-asyncio | MIT | Tests |
| This repository code | TBD by team | Keep private until submit; grant KOWR rights if required |

## AI / models

| Component | License / terms | Notes |
|-----------|-----------------|-------|
| Ollama runtime | MIT (project) | Local inference host |
| `qwen2.5:3b` (Qwen2.5) | Apache-2.0 (Qwen weights terms) | Default narrator; verify card on Hugging Face / Ollama library |
| `qwen3:8b` (fallback) | Model card terms | Already installed fallback if 3b pull fails |

Narrator is optional; Evidence JSON does not depend on model weights.

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

- [x] AI tools named (Ollama + model id)
- [x] Live adapters documented in README
- [ ] Final license grant language for KOWR (team legal / contest rules)
- [ ] Person 2 fills live source fetch dates in README
