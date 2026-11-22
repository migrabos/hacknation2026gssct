# Retencja — KOWR Water Retention DSS (HackNation 2026)

Browser-facing decision support for Polish farmers: for *this* cadastral plot and *this* crop, produce a live, evidence-grounded water report — **ocena → przyczyny → retencja/agrotech → nawadnianie (optional)**.

Integrated stack: Next.js UI (`apps/web`) → one FastAPI app (`apps/api`) → **live public data adapters** (ULDK, GUGiK NMT, OpenStreetMap, Open-Meteo/ERA5, SoilGrids, Sentinel-2, EDO) → deterministic Evidence engine → Polish template narrative.

**Demo na żywo:** web `TODO: wpisz URL` · API `TODO: wpisz URL/health` (uzupełnij po deployu).

## Co robi aplikacja (dla jury)

Rolnik wpisuje identyfikator działki TERYT, wyszukuje ją po miejscowości i numerze albo klika na mapie. Potem wybiera uprawę i datę analizy (dziś lub dowolny dzień z ostatnich 10 lat). Aplikacja pobiera dane publiczne **na żywo** i w ok. 15–25 s (bez cache) układa raport w stałej kolejności:

1. **Ocena wilgotności** – sytuacja w dniu analizy (bilans wodny 30 dni na tle 10 lat, dni bez deszczu, gleba, satelita) oraz osobno podatność wieloletnia (letni bilans wodny z 10 lat).
2. **Przyczyny** – niedobór opadów, mała pojemność wodna gleby, spływ po spadku terenu, wrażliwość uprawy, goła gleba.
3. **Retencja i agrotechnika** – działania ze stałego katalogu, każde z uzasadnieniem z danych działki: najniższe miejsce z NMT jako lokalizacja oczka, rów w pobliżu, spadek terenu, piasek i próchnica.
4. **Nawadnianie (na końcu, opcjonalnie)** – tylko gdy jest sucho, uprawa jest wrażliwa i trwa jej sezon wzrostu. Zawiera termin (faza krytyczna uprawy), szacowany niedobór wody (ET0 × Kc wg FAO-56 minus opad) i orientacyjną dawkę jednorazową zależną od gleby.

Każda liczba wskazuje źródło (`evidence[] → sources[]`). Raport zawsze pokazuje ograniczenia i brakujące dane. Wydruk lub PDF otwiera się z przeglądarki.

**Shared contract:** [`apps/web/lib/types.ts`](apps/web/lib/types.ts) ⇄ [`apps/api/app/schemas/evidence.py`](apps/api/app/schemas/evidence.py) (same field names). `apps/api/tests/test_contract_web.py` validates `fixtures/evidence_sample.json` against the API schema, so drift fails the tests.

---

## Quick start

Wymagania: **Python 3.11+** i **Node.js 20+** (z npm). Resztę skrypt instaluje sam.

### Uruchomienie jednym poleceniem

| System | Polecenie (z katalogu głównego repo) |
|--------|--------------------------------------|
| Linux / macOS / WSL | `./start.sh` |
| Windows | dwuklik na `start.bat` (albo `start.bat` w CMD/PowerShell) |
| Windows z Git Bash | `bash start.sh` |

Skrypt:

1. sprawdza wersje Pythona i Node.js,
2. tworzy `apps/api/.env` i `apps/web/.env.local` z plików `.env.example`, jeśli ich nie ma,
3. tworzy środowisko Python `apps/api/.venv` i instaluje zależności (pierwszy raz trwa kilka minut, potem tylko gdy zmieni się `requirements.txt`),
4. uruchamia `npm install` przy pierwszym starcie albo po zmianie `package-lock.json`,
5. startuje API (http://localhost:8000/docs) i frontend (http://localhost:3000), po czym otwiera przeglądarkę.

Logi trafiają do `api.log` i `web.log` w katalogu głównym (na Windows dodatkowo `api.err.log`, `web.err.log`).
Zatrzymanie: **Ctrl+C** (Linux/macOS) albo **Enter** w oknie skryptu (Windows).

Najczęstsze problemy:

- **„Port 8000 niedostępny — API wystartuje na 8001”** — to nie błąd. Skrypt sam wybiera wolny port i przekazuje go frontendowi. Na Windowsie port 8000 często blokuje Hyper-V/WSL (lista zablokowanych: `netsh int ipv4 show excludedportrange protocol=tcp`). Jeśli to poprzednie API, zamknij je: Linux/macOS `pkill -f "uvicorn app.main"`, Windows `netstat -ano | findstr :8000`, potem `taskkill /PID <pid> /F`.
- **„.venv pochodzi z innego systemu”** — repo było uruchamiane raz na Windows, raz w WSL. Usuń `apps/api/.venv` i uruchom ponownie.
- **PowerShell blokuje skrypt** — uruchamiaj przez `start.bat`, który omija tę blokadę tylko dla tego uruchomienia.

### Ręcznie (dwa terminale)

```bash
cd apps/api
python -m pip install -r requirements.txt
copy .env.example .env   # Windows; or: cp .env.example .env

uvicorn app.main:app --reload --port 8000   # or: uvicorn main:app
```

Web (second terminal):

```bash
cd apps/web
npm install
```

```bash
# Linux / macOS / Git Bash
NEXT_PUBLIC_API_URL=http://localhost:8000 npm run dev
```

```powershell
# Windows PowerShell
$env:NEXT_PUBLIC_API_URL="http://localhost:8000"; npm run dev
```

```bat
REM Windows cmd
set NEXT_PUBLIC_API_URL=http://localhost:8000 && npm run dev
```

Wymagania: **Python 3.11+**, **Node.js 20+**.

- Plot pick: `GET /plot/by-point?lat=..&lng=..`, `GET /plot/by-id?id=..` (add `&context=true` for slope + water)
- Health: `GET http://127.0.0.1:8000/health`
- Crops: `GET http://127.0.0.1:8000/crops`
- Analyze: `POST http://127.0.0.1:8000/analyze`

```bash
curl -X POST http://127.0.0.1:8000/analyze \
  -H "Content-Type: application/json" \
  -d '{"plotId":"040308_5.0004.17220","cropId":"kukurydza_ziarno","analysisDate":"2026-07-15"}'
```

Windows (cmd) — ten sam `cropId` (`kukurydza` też działa jako alias):

```bat
curl -X POST http://127.0.0.1:8000/analyze ^
  -H "Content-Type: application/json" ^
  -d "{\"plotId\":\"040308_5.0004.17220\",\"cropId\":\"kukurydza_ziarno\",\"analysisDate\":\"2026-07-15\"}"
```

### Tests

```bash
cd apps/api
pytest -q          # offline fixtures; no network
python -m warm_cache   # pre-warm cache for rehearsal plots (live network)
```

---

## Architecture

```text
Farmer / Next.js
  → POST /analyze
  → Live adapters (plot, meteo, soil, sat, drought, hydro)
  → Deterministic engine → Evidence / Report (truth)
  → Polish template narrative (restates Evidence fields)
  → JSON report
```

**Grounding rule:** the engine owns numbers and action IDs. Section prose is a deterministic Polish template over those fields — no generative LLM in the product path.

Sample report from a real live run (plot 040308_5.0004.17220, kukurydza_ziarno, 2026-07-15): [`fixtures/evidence_sample.json`](fixtures/evidence_sample.json).

---

## Environment

| Variable | Default | Meaning |
|----------|---------|---------|
| `CORS_ORIGINS` | `http://localhost:3000,http://127.0.0.1:3000` | Allowed browser origins (`*` = any) |
| `ADAPTER_CACHE_DIR` | `apps/api/cache` | Disk cache for adapter responses |
| `ENGINE_VERSION` | `0.4.0` | Report meta |

---

## Data flow (live)

`POST /analyze` → `app/adapters/live.py`: ULDK resolves the plot, then in parallel: terrain + hydro (`plot/resolver.add_plot_context`), `fetch_meteo`, `fetch_soil`, `fetch_sentinel`, `fetch_drought_context`. Every adapter returns the `run_adapter` envelope (`values`, `sources`, `coverage`, `errors`, `fromCache`), is timeout-bounded and disk-cached.

`app/engine/facts.py` copies adapter values into flat facts and builds `evidence[]`, `sources[]` (status ok/partial/failed, live/cached) and `missingData[]`. Rules in `assess.py` / `causes.py` / `rank.py` cite evidence ids only. Typical timing: ~15–22 s cold (measured 2026-11-22, all sources live), <1 s warm. All adapters share one 25 s data budget (`DATA_BUDGET_S`), so a slow source is cut off and reported in `missingData` instead of blocking the report.

### Live vs precomputed data

| Data | Mode | Range / date |
|------|------|--------------|
| Plot geometry (ULDK), land use (KIEG/EGiB), NMT heights, OSM water | live per request | current state of the public service |
| Meteo (Open-Meteo archive `era5_seamless`; NASA POWER fallback) | live | 10 years + 1 year back from the analysis date; the forecast model fills only the last ~10 days before *today* |
| Hydro (OSM Overpass + OpenFreeMap tiles) | live | nearest ditch/stream ≤ 500 m; not MPHP / ISOK |
| SoilGrids 2.0 | live | static global model (0–100 cm) |
| Sentinel-2 L2A (Earth Search STAC) | live | clear scene within 21 days before the analysis date; same window in the 5 previous years for the baseline |
| EDO CDI | live | latest 10-day map at the analysis date |
| Soil moisture (ERA5-Land via Open-Meteo archive, 0–100 cm) | live, same request as meteo | 7-day mean at the analysis date (latest day with data, ≤ 10 days lag) vs the same days in 10 previous years |
| IUNG soil drought category (WMS `Susza:katgl_landuse2024`) | live per plot | IUNG-PIB SMSR map, layer 2024; pixels inside the parcel, ~10 m |
| IUNG SMSR KBW thresholds | static table in code | `apps/api/app/crops/smsr.py`, MRiRW regulation of 11.04.2019 (Dz.U. 2019 poz. 739) |
| Village (obręb) search index `apps/api/plot/data/regions_pl.json.gz` | **precomputed** | PRG GUGiK WFS, built 2026-11-21 (`scripts/build_region_index.py`) |
| Fallback index `apps/api/plot/data/obreby.json.gz` | **precomputed** | PRG GUGiK WFS, fetched 2026-11-21 (`plot/build_obreby_index.py`) |
| Crop table (sensitivity, season months, critical months, Kc) | static table in code | `apps/api/app/crops/catalog.py` (FAO-33 Ky, FAO-56 Kc, IUNG crop groups) |

Responses are disk-cached (`ADAPTER_CACHE_DIR`). The cache only speeds up repeated runs and never replaces live computation for a new plot or date. `warm_cache.py` pre-fetches the rehearsal plots.

---

## AI disclosure

- No generative LLM in the runtime product path. No ML model is trained or run.
- Structured Report is authoritative; Polish narrative sections are template-filled from Evidence.
- AI tools used while writing code: **Cursor** (Composer / Agent), Claude Code (Anthropic) – scaffolding, engine, adapters, audit fixes. No generative LLM in the product path.

---

## Libraries

| Layer | Libraries |
|-------|-----------|
| Web (`apps/web`) | Next.js 16, React 19, Leaflet 1.9 + react-leaflet 5, maplibre-gl + @maplibre/maplibre-gl-leaflet, TypeScript |
| API (`apps/api`) | FastAPI, Uvicorn, Pydantic + pydantic-settings, httpx, Shapely, pyproj, rasterio (COG reads), NumPy, Pillow (EDO WMS colours), mapbox-vector-tile (OpenFreeMap hydro fallback), tzdata |
| Tests | pytest, pytest-asyncio |

Licenses of libraries and data sources: [`docs/licenses.md`](docs/licenses.md).

---

## Scalability and costs

- **Stateless API:** no database and no accounts, so it scales horizontally by adding instances. The disk cache can be moved to a shared volume or object storage.
- **Bottleneck = external APIs, not compute.** One analysis does about 10 HTTP calls and takes under 1 s of CPU. The free Open-Meteo tier is non-commercial and rate-limited. An 11-year daily request with several variables is billed as many “calls” (order of ~150–200 per cold analysis) — roughly tens of new plot+date pairs per day per IP before the free cap. Demo: warm the cache (`python -m warm_cache`) for rehearsal plots. Production (KOWR): paid key (`OPEN_METEO_API_KEY`) or self-hosted Open-Meteo (ERA5 from Copernicus).
- **Costs:** all other sources are free (GUGiK, Copernicus, ISRIC, NASA, OSM). Hosting: one small container (~1 vCPU / 1 GB RAM) plus a static frontend (Vercel/Netlify free tier).
- **Nationwide coverage:** every source covers all of Poland. No per-plot precomputation, so a new plot works the same as a rehearsal plot.

---

## Security and privacy

- No user accounts or personal data. Cadastral plot IDs are public register data. Reports live only in the browser (`sessionStorage`).
- No secrets in the repo: only `.env.example` files are tracked, and `.env` is git-ignored. The optional `OPEN_METEO_API_KEY` is read from the environment.
- External responses are size-capped and timeout-bounded. Plot IDs are regex-validated before calling ULDK.
- Deploy: set `CORS_ORIGINS` to the web domain (never leave it empty = `*`). Put `/analyze` behind a reverse-proxy rate limit to protect upstream quotas.

---

## Limits (honest)

- Thresholds are simple water-balance proxies, not a calibrated hydrological model.
- Satellite (NDVI/NDMI) only corrects the weather-based score within −10/+6 points. It shows leaves, not soil moisture, and the multi-year baseline is used only with ≥ 3 clear years. EDO CDI is a regional indicator.
- Water features come from OpenStreetMap (Overpass mirrors, fallback OpenFreeMap vector tiles – needs `mapbox-vector-tile`), **not** from MPHP / Hydroportal ISOK. When both fail, hydro is reported as missing. Unmapped ditches are not visible.
- Crop season months, phase Kc (ini/mid) and irrigation doses are group-level orientation values (FAO-56 / FAO-33 / IUNG groups), not variety-level agronomy. Ky without a FAO-33 row is labelled „przyjęte”, not „FAO”. The irrigation dose is a guide, not an irrigation schedule.
- Basemaps in the UI: OpenStreetMap tiles + Geoportal ORTO (GUGiK).
- Slope = least-squares plane through ~25–40 GUGiK NMT points inside the plot (mean slope). Local gullies are not modelled.
- Irrigation is never first advice when retention applies.

Verification notes for jury: [`docs/verify.md`](docs/verify.md). Licenses: [`docs/licenses.md`](docs/licenses.md).

---

## Repo layout (core)

```text
apps/api/          FastAPI + engine + narrative + tests
fixtures/          evidence_sample.json — real /analyze output
docs/roles/        per-person playbooks
docs/verify.md
docs/licenses.md
AGENTS.md          contest big picture
```
