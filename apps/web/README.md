# apps/web — Retencja frontend (Person 1)

Next.js (App Router) + TypeScript. Polish UI for farmers: pick a działka → crop → date → water report → print/PDF.

## Run

```bash
cd apps/web
cp .env.example .env.local   # optional; defaults to mock mode
npm install
npm run dev                  # http://localhost:3000
```

Node ≥ 20.9 required.

## Mock vs real backend

| Env | Effect |
|-----|--------|
| `NEXT_PUBLIC_API_MODE=mock` (default) | Sample data from `mocks/`. A yellow "Tryb demonstracyjny" strip is always shown. |
| `NEXT_PUBLIC_API_MODE=real` | Calls FastAPI at `NEXT_PUBLIC_API_URL` (`/health`, `/crops`, `/plot/by-id`, `/plot/by-point`, `POST /analyze`). |

In mock mode, typing plot ID `000000_0.0000.0` shows the "działka nie znaleziona" state. Clicking the map creates a demo plot around the click.

## Where things live

| Path | What |
|------|------|
| `lib/types.ts` | **Only place field names live.** Mirrors the Evidence/report shape in `AGENTS.md`. When Person 3 locks the schema, update this file and `mocks/*.json`. |
| `lib/api.ts` | All backend calls + mock/real switch + error mapping (`not_found`, `timeout`, `api_down`, …). |
| `lib/labels.ts` | Polish labels for enums, error messages, date formatting. |
| `mocks/` | `report.json` (partial report: Sentinel-2 + hydro failed, IUNG missing), `plot.json`, `crops.json`. |
| `components/MapPicker.tsx` | Leaflet map: Geoportal aerial photo, OSM street map, GUGiK parcel boundaries (zoom ≥ 15), selected plot outline. |
| `components/ReportView.tsx` | Report in contest order: ocena → przyczyny → retencja → agrotechnika → nawadnianie, then sources / missing data / limitations. |
| `components/PipelineLoader.tsx` | Loading screen with pipeline steps. |
| `styles/print.css` | Print / "Zapisz jako PDF" (A4, evidence expanded). |

## Map layers (public, no API key)

- Geoportal ORTO WMTS StandardResolution + WMS HighResolution (zoom ≥ 15) — © GUGiK
- GUGiK Krajowa Integracja Ewidencji Gruntów WMS (`dzialki,numery_dzialek`) — parcel lines
- OpenStreetMap standard tiles — © OpenStreetMap contributors (tile usage policy: light use only; switch to a hosted provider for production)
