/**
 * Single entry point for all backend calls — FastAPI at NEXT_PUBLIC_API_URL.
 *
 * Endpoints (see AGENTS.md + docs/roles/02-gis-data.md):
 *   GET  /health
 *   GET  /crops
 *   GET  /plot/by-id?id=...
 *   GET  /plot/by-point?lat=...&lng=...
 *   GET  /plot/regions?q=...            (obręby / villages by exact name)
 *   GET  /plot/by-region?regionId=...&nr=...
 *   POST /analyze                      (water report for one crop)
 *   POST /crop-fit                     (separate report: which crops suit this plot)
 */
import type {
  AnalyzeRequest,
  ApiErrorKind,
  Crop,
  CropFitReport,
  CropFitRequest,
  HealthResponse,
  Plot,
  Region,
  Report,
} from "./types";

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

export const api = {
  health: () => request<HealthResponse>("/health", {}, 5_000),
  getCrops: () => request<Crop[]>("/crops"),
  plotById: (id: string) => request<Plot>(`/plot/by-id?id=${encodeURIComponent(id.trim())}`),
  plotByPoint: (lat: number, lng: number) =>
    request<Plot>(`/plot/by-point?lat=${lat}&lng=${lng}`),
  searchRegions: (q: string) => request<Region[]>(`/plot/regions?q=${encodeURIComponent(q.trim())}`),
  regionExtent: async (regionId: string): Promise<Region["bbox"]> =>
    (await request<{ bbox: Region["bbox"] }>(`/plot/region-extent?regionId=${encodeURIComponent(regionId)}`, {}, 12_000))
      .bbox ?? null,
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
  /** Separate report: which crops cope best with the water on this plot (no crop needed). */
  cropFit: (req: CropFitRequest) => {
    const body: CropFitRequest = req.plotId ? { plotId: req.plotId, analysisDate: req.analysisDate } : req;
    return request<CropFitReport>("/crop-fit", { method: "POST", body: JSON.stringify(body) }, ANALYZE_TIMEOUT_MS);
  },
};
