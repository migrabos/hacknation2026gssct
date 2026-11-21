/**
 * Single entry point for all backend calls.
 *
 * NEXT_PUBLIC_API_MODE=mock (default) → local sample data from mocks/
 * NEXT_PUBLIC_API_MODE=real           → FastAPI at NEXT_PUBLIC_API_URL
 *
 * Endpoints (see AGENTS.md + docs/roles/02-gis-data.md):
 *   GET  /health
 *   GET  /crops
 *   GET  /plot/by-id?id=...
 *   GET  /plot/by-point?lat=...&lng=...
 *   GET  /plot/regions?q=...            (obręby / villages by exact name)
 *   GET  /plot/by-region?regionId=...&nr=...
 *   POST /analyze
 */
import type {
  AnalyzeRequest,
  ApiErrorKind,
  Crop,
  HealthResponse,
  Plot,
  Position,
  Region,
  Report,
} from "./types";
import mockCrops from "@/mocks/crops.json";
import mockPlot from "@/mocks/plot.json";
import mockReport from "@/mocks/report.json";

export const API_MODE: "mock" | "real" =
  process.env.NEXT_PUBLIC_API_MODE === "real" ? "real" : "mock";

const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(/\/$/, "");

/** Analyze target is <30 s; give slow cold runs some slack before failing. */
const ANALYZE_TIMEOUT_MS = 60_000;
const DEFAULT_TIMEOUT_MS = 20_000;

export class ApiError extends Error {
  constructor(
    public kind: ApiErrorKind,
    message?: string,
  ) {
    super(message ?? kind);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, init: RequestInit = {}, timeoutMs = DEFAULT_TIMEOUT_MS): Promise<T> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, {
      ...init,
      signal: controller.signal,
      headers: { "Content-Type": "application/json", ...(init.headers ?? {}) },
    });
  } catch (err) {
    if (err instanceof DOMException && err.name === "AbortError") throw new ApiError("timeout");
    throw new ApiError("api_down");
  } finally {
    clearTimeout(timer);
  }

  if (res.ok) return (await res.json()) as T;

  let detail: string | undefined;
  try {
    const body = await res.json();
    detail = typeof body?.detail === "string" ? body.detail : undefined;
  } catch {
    /* non-JSON error body */
  }
  if (res.status === 404) throw new ApiError("not_found", detail);
  if (res.status === 400 || res.status === 422) throw new ApiError("bad_request", detail);
  // 503 = an upstream public service (e.g. ULDK) is down; 504 = gateway timeout
  if (res.status === 503 || res.status === 504) throw new ApiError("timeout", detail);
  throw new ApiError("server", detail);
}

// ---------------------------------------------------------------------------
// Mock implementation — clearly labelled sample data, never presented as real.
// ---------------------------------------------------------------------------

/** Typing this plot ID in mock mode simulates "działka nie znaleziona". */
export const MOCK_NOT_FOUND_ID = "000000_0.0000.0";

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

/** Builds a plausible field-shaped polygon around a clicked point (mock only). */
function mockPlotAround(lat: number, lng: number): Plot {
  const pts: [number, number][] = [
    [-140, -48],
    [132, -62],
    [141, 41],
    [-128, 58],
  ];
  const a = (8 * Math.PI) / 180;
  const mPerDegLat = 111_320;
  const mPerDegLng = 111_320 * Math.cos((lat * Math.PI) / 180);
  const ring: Position[] = pts.map(([x, y]) => {
    const xr = x * Math.cos(a) - y * Math.sin(a);
    const yr = x * Math.sin(a) + y * Math.cos(a);
    return [+(lng + xr / mPerDegLng).toFixed(6), +(lat + yr / mPerDegLat).toFixed(6)];
  });
  ring.push(ring[0]);
  const lngs = ring.map((p) => p[0]);
  const lats = ring.map((p) => p[1]);
  return {
    ...(mockPlot as Plot),
    plotId: `DEMO_${lat.toFixed(4)}_${lng.toFixed(4)}`,
    geometry: { type: "Polygon", coordinates: [ring] },
    centroid: [lng, lat],
    bbox: [Math.min(...lngs), Math.min(...lats), Math.max(...lngs), Math.max(...lats)],
    voivodeship: undefined,
    county: undefined,
    commune: undefined,
  };
}

const mockApi = {
  async health(): Promise<HealthResponse> {
    return { status: "ok", version: "mock" };
  },
  async getCrops(): Promise<Crop[]> {
    return mockCrops as Crop[];
  },
  async plotById(id: string): Promise<Plot> {
    await sleep(500);
    if (id.trim() === MOCK_NOT_FOUND_ID) throw new ApiError("not_found");
    return { ...(mockPlot as Plot), plotId: id.trim() };
  },
  async searchRegions(q: string): Promise<Region[]> {
    await sleep(300);
    const name = q.trim();
    if (name.length < 2) return [];
    const p = mockPlot as Plot;
    return [
      { regionId: "141201_1.0001", region: name, commune: p.commune ?? "Gmina demo", county: p.county, voivodeship: p.voivodeship, bbox: p.bbox },
      { regionId: "022503_5.0003", region: name, commune: "Bogatynia", county: "powiat zgorzelecki", voivodeship: "dolnośląskie", bbox: [14.935, 51.009, 14.971, 51.034] },
    ];
  },
  async plotByRegion(regionId: string, nr: string): Promise<Plot> {
    return mockApi.plotById(`${regionId}.${nr.trim()}`);
  },
  async plotByPoint(lat: number, lng: number): Promise<Plot> {
    await sleep(400);
    return mockPlotAround(lat, lng);
  },
  async analyze(req: AnalyzeRequest, plot?: Plot): Promise<Report> {
    await sleep(4200);
    const base = mockReport as Report;
    const crops = mockCrops as Crop[];
    return {
      ...base,
      plot: plot ?? base.plot,
      crop: crops.find((c) => c.id === req.cropId) ?? base.crop,
      analysisDate: req.analysisDate,
      generatedAt: new Date().toISOString(),
    };
  },
};

// ---------------------------------------------------------------------------
// Real implementation
// ---------------------------------------------------------------------------

const realApi = {
  health: () => request<HealthResponse>("/health", {}, 5_000),
  getCrops: () => request<Crop[]>("/crops"),
  plotById: (id: string) => request<Plot>(`/plot/by-id?id=${encodeURIComponent(id.trim())}`),
  plotByPoint: (lat: number, lng: number) =>
    request<Plot>(`/plot/by-point?lat=${lat}&lng=${lng}`),
  searchRegions: (q: string) => request<Region[]>(`/plot/regions?q=${encodeURIComponent(q.trim())}`),
  plotByRegion: (regionId: string, nr: string) =>
    request<Plot>(
      `/plot/by-region?regionId=${encodeURIComponent(regionId)}&nr=${encodeURIComponent(nr.trim().replace(/\s+/g, ""))}`,
    ),
  // The backend re-resolves the plot itself (ULDK is cached), so `_plot` is unused here.
  // plotId wins over lat/lng; coords are only sent when there is no plotId.
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  analyze: (req: AnalyzeRequest, _plot?: Plot) => {
    const body: AnalyzeRequest = req.plotId
      ? { plotId: req.plotId, cropId: req.cropId, analysisDate: req.analysisDate }
      : req;
    return request<Report>("/analyze", { method: "POST", body: JSON.stringify(body) }, ANALYZE_TIMEOUT_MS);
  },
};

const _baseApi = API_MODE === "real" ? realApi : mockApi;

// #region agent log
function _dbgPlot(p: Plot | null | undefined) {
  if (!p) return null;
  const ring =
    p.geometry?.type === "Polygon"
      ? p.geometry.coordinates?.[0]
      : p.geometry?.type === "MultiPolygon"
        ? p.geometry.coordinates?.[0]?.[0]
        : undefined;
  const first = ring?.[0];
  const last = ring && ring.length > 0 ? ring[ring.length - 1] : undefined;
  return {
    plotId: p.plotId,
    geomType: p.geometry?.type,
    ringLen: ring?.length,
    first,
    last,
    closed: first && last ? first[0] === last[0] && first[1] === last[1] : null,
    centroid: p.centroid,
    bbox: p.bbox,
    firstLooksLikeLngLat:
      Array.isArray(first) && first[0] >= 14 && first[0] <= 25 && first[1] >= 48 && first[1] <= 56,
    bboxLooksLikeLngLat:
      Array.isArray(p.bbox) && p.bbox[0] >= 14 && p.bbox[0] <= 25 && p.bbox[1] >= 48 && p.bbox[1] <= 56,
  };
}
function _agentLog(location: string, message: string, data: Record<string, unknown>, hypothesisId: string) {
  fetch("http://127.0.0.1:7469/ingest/78fee146-1b5b-4d90-8bb6-2bc46ba8b822", {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-Debug-Session-Id": "68e619" },
    body: JSON.stringify({
      sessionId: "68e619",
      runId: "pre-fix",
      hypothesisId,
      location,
      message,
      data: { apiMode: API_MODE, apiUrl: API_URL, ...data },
      timestamp: Date.now(),
    }),
  }).catch(() => {});
}
// #endregion

export const api = {
  health: async () => {
    try {
      const h = await _baseApi.health();
      // #region agent log
      _agentLog("api.ts:health", "health ok", { health: h }, "H1");
      // #endregion
      return h;
    } catch (e) {
      // #region agent log
      _agentLog("api.ts:health", "health failed", { err: String(e) }, "H1");
      // #endregion
      throw e;
    }
  },
  getCrops: () => _baseApi.getCrops(),
  searchRegions: (q: string) => _baseApi.searchRegions(q),
  plotByRegion: (regionId: string, nr: string) => _baseApi.plotByRegion(regionId, nr),
  plotById: async (id: string) => {
    const p = await _baseApi.plotById(id);
    // #region agent log
    _agentLog("api.ts:plotById", "plot resolved by id", { inputId: id.trim(), plot: _dbgPlot(p) }, "H2");
    // #endregion
    return p;
  },
  plotByPoint: async (lat: number, lng: number) => {
    const p = await _baseApi.plotByPoint(lat, lng);
    // #region agent log
    _agentLog(
      "api.ts:plotByPoint",
      "plot resolved by point",
      {
        click: { lat, lng },
        plot: _dbgPlot(p),
        clickInsideBbox: p.bbox
          ? lng >= p.bbox[0] && lng <= p.bbox[2] && lat >= p.bbox[1] && lat <= p.bbox[3]
          : null,
      },
      "H3",
    );
    // #endregion
    return p;
  },
  analyze: async (req: AnalyzeRequest, plot?: Plot) => {
    const report = await _baseApi.analyze(req, plot);
    // #region agent log
    const statuses = Object.fromEntries(
      (report.sources ?? []).map((s) => [s.id, { status: s.status, mode: s.mode, error: s.error ?? null }]),
    );
    const failed = (report.sources ?? []).filter((s) => s.status !== "ok").map((s) => s.id);
    _agentLog(
      "api.ts:analyze",
      "analyze finished",
      {
        req,
        inputPlot: _dbgPlot(plot),
        reportPlot: _dbgPlot(report.plot),
        reportMeta: report.meta ?? null,
        sourceStatuses: statuses,
        failedOrPartial: failed,
        missingDataIds: (report.missingData ?? []).map((m) => m.id),
      },
      "H1",
    );
    // #endregion
    return report;
  },
};
