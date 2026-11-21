/**
 * Shared data contract for the web app.
 *
 * Mirrors the "Evidence / report shape" in AGENTS.md (owned by Person 3).
 * Backend twin: apps/api/app/schemas/evidence.py (Pydantic, 1:1 field names).
 * Change BOTH files together — apps/api/tests/test_contract_web.py validates a
 * sample report fixture against the backend schema and fails on drift.
 */

// ---------- Geometry (WGS84, GeoJSON order: [lng, lat]) ----------

export type Position = [number, number];

export interface PolygonGeometry {
  type: "Polygon";
  coordinates: Position[][];
}

export interface MultiPolygonGeometry {
  type: "MultiPolygon";
  coordinates: Position[][][];
}

export type PlotGeometry = PolygonGeometry | MultiPolygonGeometry;

/** [minLng, minLat, maxLng, maxLat] */
export type BBox = [number, number, number, number];

// ---------- Enums ----------

export type Confidence = "low" | "medium" | "high";
export type RiskLevel = "low" | "medium" | "high";

/** Current moisture situation (≠ multi-year susceptibility). */
export type MoistureLevel = "very_dry" | "dry" | "normal" | "wet" | "insufficient_data";

export type CauseId =
  | "precip_deficit"
  | "low_soil_storage"
  | "runoff"
  | "crop_sensitivity";

/** Fixed action catalog — IDs are never invented by the LLM. */
export type ActionId =
  | "residues"
  | "cover_crops"
  | "reduce_tillage"
  | "small_pond"
  | "buffer_strips"
  | "ditch_retention"
  | "irrigation_timing";

export type SourceStatus = "ok" | "partial" | "failed";
/** live = fetched for this request, cached = from disk cache, static = bundled table */
export type SourceMode = "live" | "cached" | "static";

// ---------- Plot (Person 2) ----------

/** Cadastral precinct (obręb) — usually one village. From GET /plot/regions. */
export interface Region {
  /** e.g. "022503_5.0003" */
  regionId: string;
  region?: string | null;
  commune?: string | null;
  county?: string | null;
  voivodeship?: string | null;
  /** [min_lng, min_lat, max_lng, max_lat] */
  bbox?: [number, number, number, number] | null;
}

/** GET /plot/regions — at most 50 regions; `total` = all matches. */
export interface RegionSearch {
  regions: Region[];
  total: number;
}

export interface Plot {
  plotId: string;
  geometry: PlotGeometry;
  centroid: Position;
  areaHa: number;
  bbox: BBox;
  voivodeship?: string;
  county?: string;
  commune?: string;
  terrain?: {
    slopePct?: number;
    runoffRisk?: RiskLevel;
  };
  hydro?: {
    nearbyWater?: boolean;
    distanceClass?: string;
    missing?: boolean;
  };
  /** Field / meadow / pasture / forest… — ONLY from the EGiB land register; no data = category/labelPl absent. */
  landUse?: {
    category?:
      | "arable" | "meadow" | "pasture" | "orchard" | "farmyard" | "forest"
      | "woodland" | "built" | "transport" | "water" | "wetland" | "bare" | "other" | "mixed";
    labelPl?: string;
    isAgricultural?: boolean;
    source?: "egib";
    uses?: string[];
    /** Raw EGiB contour codes, e.g. ["RIIIa", "Br/PsIV"] */
    codes?: string[];
    soilClasses?: string[];
    notes?: string[];
  };
  sources?: Source[];
  fetchedAt?: string;
}

// ---------- Crops ----------

export interface Crop {
  id: string;
  name: string;
  droughtSensitivity?: RiskLevel;
}

// ---------- Report / Evidence (Person 3) ----------

/** One verifiable fact. Everything in the report points back to these ids. */
export interface Evidence {
  id: string;
  label: string;
  value: number | string;
  unit?: string;
  /** e.g. "norma wieloletnia: 118 mm" */
  comparison?: string;
  sourceId: string;
}

export interface MoistureAssessment {
  current: {
    level: MoistureLevel;
    headline: string;
    summary: string;
    confidence: Confidence;
    evidenceRefs: string[];
  };
  susceptibility: {
    level: RiskLevel;
    headline: string;
    summary: string;
    confidence: Confidence;
    evidenceRefs: string[];
  };
}

export interface Cause {
  id: CauseId;
  title: string;
  explanation: string;
  confidence: Confidence;
  evidenceRefs: string[];
}

export interface Recommendation {
  actionId: ActionId;
  title: string;
  description: string;
  /** Why this action fits THIS plot — built from evidence. */
  why: string;
  /** 1 = do first */
  priority: number;
  costLevel?: RiskLevel;
  timeframe?: string;
  evidenceRefs: string[];
}

export interface Source {
  id: string;
  name: string;
  provider?: string;
  url?: string;
  fetchedAt?: string;
  /** Date range / acquisition date of the underlying data. */
  dataPeriod?: string;
  mode: SourceMode;
  status: SourceStatus;
  license?: string;
  error?: string;
}

export interface MissingData {
  id: string;
  /** What is missing, farmer language. */
  what: string;
  reason: string;
  /** How this affects the report. */
  impact: string;
}

export type NarrativeSectionId =
  | "assessment"
  | "causes"
  | "retention"
  | "agrotech"
  | "irrigation";

export interface Narrative {
  generatedBy: "llm" | "template";
  sections: {
    id: NarrativeSectionId;
    text: string;
    evidenceRefs: string[];
  }[];
}

export interface Report {
  reportId: string;
  status: "complete" | "partial";
  plot: Plot;
  crop: Crop;
  /** YYYY-MM-DD */
  analysisDate: string;
  /** ISO timestamp */
  generatedAt: string;
  moistureAssessment: MoistureAssessment;
  causes: Cause[];
  recommendations: {
    retention: Recommendation[];
    agrotech: Recommendation[];
    /** Optional, always last. null/undefined = not recommended now. */
    irrigation?: Recommendation[] | null;
    /** Shown when irrigation is not recommended. */
    irrigationNote?: string;
  };
  evidence: Evidence[];
  sources: Source[];
  limitations: string[];
  missingData: MissingData[];
  narrative?: Narrative;
  meta?: ReportMeta;
}

export interface ReportMeta {
  engineVersion: string;
  adapters: "live";
  llmEnabled: boolean;
  llmModel?: string;
  durationMs: number;
}

// ---------- API ----------

export interface AnalyzeRequest {
  plotId?: string;
  lat?: number;
  lng?: number;
  cropId: string;
  analysisDate: string;
}

export interface HealthResponse {
  status: "ok" | "degraded";
  version?: string;
  adapters?: "live";
  llm?: boolean;
  model?: string;
}

export type ApiErrorKind =
  | "not_found"
  | "timeout"
  | "api_down"
  | "bad_request"
  | "server";
