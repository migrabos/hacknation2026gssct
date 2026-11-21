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
 *   POST /analyze
 */
import type {
  AnalyzeRequest,
  ApiErrorKind,
  Crop,
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

const realApi = {
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
};

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
      data: { apiUrl: API_URL, ...data },
      timestamp: Date.now(),
    }),
  }).catch(() => {});
}
// #endregion

export const api = {
  health: async () => {
    try {
      const h = await realApi.health();
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
  getCrops: () => realApi.getCrops(),
  searchRegions: (q: string) => realApi.searchRegions(q),
  plotByRegion: (regionId: string, nr: string) => realApi.plotByRegion(regionId, nr),
  regionExtent: (regionId: string) => realApi.regionExtent(regionId),
  plotById: async (id: string) => {
    const p = await realApi.plotById(id);
    // #region agent log
    _agentLog("api.ts:plotById", "plot resolved by id", { inputId: id.trim(), plot: _dbgPlot(p) }, "H2");
    // #endregion
    return p;
  },
  plotByPoint: async (lat: number, lng: number) => {
    const p = await realApi.plotByPoint(lat, lng);
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
    const report = await realApi.analyze(req, plot);
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
