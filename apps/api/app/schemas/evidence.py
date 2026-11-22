"""Evidence / Report truth models.

1:1 mirror of `apps/web/lib/types.ts` — that file is the shared contract.
Change field names in BOTH places or not at all.
Extra backend-only fields (scores, meta) are allowed; the UI ignores them.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

# ---------- Enums (same literals as types.ts) ----------

Confidence = Literal["low", "medium", "high"]
RiskLevel = Literal["low", "medium", "high"]
MoistureLevel = Literal["very_dry", "dry", "normal", "wet", "insufficient_data"]
CauseId = Literal["precip_deficit", "low_soil_storage", "runoff", "crop_sensitivity", "bare_soil"]
ActionId = Literal[
    "residues",
    "cover_crops",
    "reduce_tillage",
    "small_pond",
    "buffer_strips",
    "ditch_retention",
    "irrigation_timing",
]
SourceStatus = Literal["ok", "partial", "failed"]
SourceMode = Literal["live", "cached", "static"]
NarrativeSectionId = Literal["assessment", "causes", "retention", "agrotech", "irrigation"]


def confidence_label(x: float) -> Confidence:
    """Numeric engine confidence 0–1 → UI band."""
    if x >= 0.75:
        return "high"
    if x >= 0.55:
        return "medium"
    return "low"


# ---------- Plot (Person 2) ----------


class Terrain(BaseModel):
    slopePct: float | None = None
    runoffRisk: RiskLevel | None = None


class RetentionSpot(BaseModel):
    """Lowest sampled NMT point of the plot – suggested place for a pond / micro-retention.

    lat/lng are None when no place is suggested (flat plot, coarse or missing DEM).
    """
    lat: float | None = None
    lng: float | None = None
    elevationM: float | None = None
    elevationDropM: float | None = None  # highest − lowest sampled point
    pointsSampled: int | None = None
    gridSpacingM: float | None = None  # ≈ accuracy of the location
    nearEdge: bool | None = None
    confidence: Confidence
    reason: str


class Hydro(BaseModel):
    nearbyWater: bool | None = None
    distanceClass: str | None = None
    missing: bool | None = None


LandUseCategory = Literal[
    "arable", "meadow", "pasture", "orchard", "farmyard", "forest", "woodland",
    "built", "transport", "water", "wetland", "bare", "other", "mixed",
]


class LandUse(BaseModel):
    category: LandUseCategory | None = None
    labelPl: str | None = None
    isAgricultural: bool | None = None
    source: Literal["egib"] | None = None  # official land register only – never inferred
    uses: list[str] = Field(default_factory=list)  # all official uses on the parcel (EGiB)
    codes: list[str] = Field(default_factory=list)  # raw EGiB contour codes, e.g. RIIIa, Br/PsIV
    soilClasses: list[str] = Field(default_factory=list)  # EGiB soil valuation classes, e.g. IIIa
    notes: list[str] = Field(default_factory=list)


class Source(BaseModel):
    id: str
    name: str
    provider: str | None = None
    url: str | None = None
    fetchedAt: str | None = None
    dataPeriod: str | None = None
    mode: SourceMode
    status: SourceStatus
    license: str | None = None
    error: str | None = None


class Plot(BaseModel):
    plotId: str
    geometry: dict[str, Any]
    centroid: tuple[float, float]  # [lng, lat] — GeoJSON order
    areaHa: float
    bbox: tuple[float, float, float, float]  # [minLng, minLat, maxLng, maxLat]
    voivodeship: str | None = None
    county: str | None = None
    commune: str | None = None
    terrain: Terrain | None = None
    retentionSpot: RetentionSpot | None = None
    hydro: Hydro | None = None
    landUse: LandUse | None = None
    sources: list[Source] | None = None
    fetchedAt: str | None = None


# ---------- Crops ----------


class Crop(BaseModel):
    id: str
    name: str
    droughtSensitivity: RiskLevel | None = None


# ---------- Report / Evidence (Person 3) ----------


class Evidence(BaseModel):
    id: str
    label: str
    value: float | str
    unit: str | None = None
    comparison: str | None = None
    sourceId: str


class AssessmentBlock(BaseModel):
    headline: str
    summary: str
    confidence: Confidence
    evidenceRefs: list[str] = Field(default_factory=list)
    # backend-only transparency
    score0to100: int | None = None


class CurrentBlock(AssessmentBlock):
    level: MoistureLevel


class SusceptibilityBlock(AssessmentBlock):
    level: RiskLevel | Literal["insufficient_data"]


class MoistureAssessment(BaseModel):
    current: CurrentBlock
    susceptibility: SusceptibilityBlock


class Cause(BaseModel):
    id: CauseId
    title: str
    explanation: str
    confidence: Confidence
    evidenceRefs: list[str] = Field(default_factory=list)
    confidence0to1: float | None = None  # backend-only, used for sorting


class Recommendation(BaseModel):
    actionId: ActionId
    title: str
    description: str
    why: str
    priority: int = Field(ge=1)
    costLevel: RiskLevel | None = None
    timeframe: str | None = None
    evidenceRefs: list[str] = Field(default_factory=list)


class Recommendations(BaseModel):
    retention: list[Recommendation] = Field(default_factory=list)
    agrotech: list[Recommendation] = Field(default_factory=list)
    irrigation: list[Recommendation] | None = None
    irrigationNote: str | None = None


class MissingData(BaseModel):
    id: str
    what: str
    reason: str
    impact: str


class NarrativeSection(BaseModel):
    id: NarrativeSectionId
    text: str
    evidenceRefs: list[str] = Field(default_factory=list)


class Narrative(BaseModel):
    sections: list[NarrativeSection] = Field(default_factory=list)


class ReportMeta(BaseModel):
    engineVersion: str
    adapters: Literal["live"]
    durationMs: int = 0


class PrecipMonth(BaseModel):
    """One histogram bar: precipitation in a calendar month vs the multi-year mean."""

    month: str  # YYYY-MM
    precipMm: float | None = None
    normalMm: float | None = None  # mean of the same day-range in previous years
    normalYears: int = 0  # how many years the mean is based on
    partial: bool = False  # analysis month: counted only up to analysisDate


class Report(BaseModel):
    """Full /analyze response — deterministic Evidence + template narrative."""

    reportId: str
    status: Literal["complete", "partial"]
    plot: Plot
    crop: Crop
    analysisDate: str  # YYYY-MM-DD
    generatedAt: str  # ISO timestamp
    moistureAssessment: MoistureAssessment
    causes: list[Cause] = Field(default_factory=list)
    recommendations: Recommendations
    evidence: list[Evidence] = Field(default_factory=list)
    precipMonthly: list[PrecipMonth] = Field(default_factory=list)  # last 12 months, oldest first
    sources: list[Source] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    missingData: list[MissingData] = Field(default_factory=list)
    narrative: Narrative | None = None
    meta: ReportMeta | None = None


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    version: str | None = None
    adapters: str | None = None
