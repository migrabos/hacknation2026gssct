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
 *   POST /analyze
 */
import type {
  AnalyzeRequest,
  ApiErrorKind,
  Crop,
  HealthResponse,
  Plot,
  Position,
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

export const api = API_MODE === "real" ? realApi : mockApi;
