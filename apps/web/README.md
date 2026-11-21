# apps/web — Retencja frontend (Person 1)

Next.js (App Router) + TypeScript. Polish UI for farmers: pick a działka → crop → date → water report → print/PDF.

## Run

```bash
cd apps/web
cp .env.example .env.local   # set NEXT_PUBLIC_API_URL
npm install
npm run dev                  # http://localhost:3000
```

Node ≥ 20.9 required. Needs the FastAPI backend at `NEXT_PUBLIC_API_URL`.

## Where things live

| Path | What |
|------|------|
| `lib/types.ts` | **Only place field names live.** Mirrors the Evidence/report shape in `AGENTS.md`. Keep in sync with `apps/api/app/schemas/evidence.py`. |
| `lib/api.ts` | All backend calls + error mapping (`not_found`, `timeout`, `api_down`, …). |
| `lib/labels.ts` | Polish labels for enums, error messages, date formatting. |
| `components/MapPicker.tsx` | Leaflet map: Geoportal aerial photo with place labels, Esri topo street map, GUGiK parcel boundaries (zoom ≥ 15), selected plot outline. |
| `components/ReportView.tsx` | Report in contest order: ocena → przyczyny → retencja → agrotechnika → nawadnianie, then sources / missing data / limitations. |
| `components/PipelineLoader.tsx` | Loading screen with pipeline steps. |
| `styles/print.css` | Print / "Zapisz jako PDF" (A4, evidence expanded). |

## Map layers (public, no API key)

- Geoportal ORTO WMTS StandardResolution + WMS HighResolution (zoom ≥ 15) — © GUGiK
- GUGiK Krajowa Integracja Ewidencji Gruntów WMS (`dzialki,numery_dzialek`) — parcel lines
- Esri World Topo Map + Esri Reference labels (places, roads over the aerial photo) — keyless ArcGIS Online tiles, attribution required; check Esri terms before commercial use
