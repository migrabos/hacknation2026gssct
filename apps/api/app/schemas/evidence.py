"""Evidence / Report truth models.

1:1 mirror of `apps/web/lib/types.ts` — that file is the shared contract.
Change field names in BOTH places (and in `apps/web/mocks/*.json`) or not at all.
Extra backend-only fields (scores, meta) are allowed; the UI ignores them.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

# ---------- Enums (same literals as types.ts) ----------

Confidence = Literal["low", "medium", "high"]
RiskLevel = Literal["low", "medium", "high"]
MoistureLevel = Literal["very_dry", "dry", "normal", "wet", "insufficient_data"]
CauseId = Literal["precip_deficit", "low_soil_storage", "runoff", "crop_sensitivity"]
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
    level: RiskLevel


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
    generatedBy: Literal["llm", "template"]
    sections: list[NarrativeSection] = Field(default_factory=list)


class ReportMeta(BaseModel):
    engineVersion: str
    adapters: Literal["live", "mock"]
    llmEnabled: bool
    llmModel: str | None = None
    durationMs: int = 0


class Report(BaseModel):
    """Full /analyze response — deterministic Evidence + optional narrative."""

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
    sources: list[Source] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    missingData: list[MissingData] = Field(default_factory=list)
    narrative: Narrative | None = None
    meta: ReportMeta | None = None


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    version: str | None = None
    adapters: str | None = None
    llm: bool | None = None
    model: str | None = None
