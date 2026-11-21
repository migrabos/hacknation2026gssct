"""Evidence / Report truth models — Person 1 UI contract."""

from __future__ import annotations

from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, Field

CauseId = Literal[
    "precip_deficit",
    "low_soil_storage",
    "runoff",
    "crop_sensitivity",
]

MoistureLevel = Literal["ok", "watch", "deficit", "severe"]
SusceptibilityLevel = Literal["low", "moderate", "high"]
NarrativeMode = Literal["llm", "template"]
ActionKind = Literal["retention", "agrotech", "irrigation"]


class Centroid(BaseModel):
    lat: float
    lng: float


class TerrainInfo(BaseModel):
    slopePct: float | None = None
    runoffRisk: str | None = None


class HydroInfo(BaseModel):
    nearbyWater: bool | None = None
    distanceClass: str | None = None


class PlotInfo(BaseModel):
    plotId: str | None = None
    centroid: Centroid
    areaHa: float | None = None
    geometry: dict[str, Any] | None = None
    voivodeship: str | None = None
    terrain: TerrainInfo | None = None
    hydro: HydroInfo | None = None


class CropInfo(BaseModel):
    id: str
    namePl: str
    droughtSensitivity: float


class SituationBlock(BaseModel):
    level: MoistureLevel
    score0to100: int = Field(ge=0, le=100)
    summaryPl: str
    evidenceIds: list[str] = Field(default_factory=list)


class SusceptibilityBlock(BaseModel):
    level: SusceptibilityLevel
    score0to100: int = Field(ge=0, le=100)
    peakMonths: list[int] = Field(default_factory=list)
    summaryPl: str
    evidenceIds: list[str] = Field(default_factory=list)


class MoistureAssessment(BaseModel):
    current: SituationBlock
    multiYearSusceptibility: SusceptibilityBlock
    confidence0to1: float = Field(ge=0, le=1)
    uncertaintyNotes: list[str] = Field(default_factory=list)


class Cause(BaseModel):
    id: CauseId
    labelPl: str
    confidence0to1: float = Field(ge=0, le=1)
    evidenceIds: list[str] = Field(default_factory=list)
    rationalePl: str


class Recommendation(BaseModel):
    id: str
    titlePl: str
    whyPl: str
    priority: int = Field(ge=1)
    evidenceIds: list[str] = Field(default_factory=list)
    kind: ActionKind | None = None


class Recommendations(BaseModel):
    retention: list[Recommendation] = Field(default_factory=list)
    agrotech: list[Recommendation] = Field(default_factory=list)
    irrigation: list[Recommendation] = Field(default_factory=list)


class Source(BaseModel):
    id: str
    name: str
    url: str | None = None
    fetchedAt: str | None = None
    coverage: str | None = None


class NarrativeSection(BaseModel):
    id: str
    titlePl: str
    bodyPl: str


class Narrative(BaseModel):
    mode: NarrativeMode
    sections: list[NarrativeSection] = Field(default_factory=list)


class ReportMeta(BaseModel):
    engineVersion: str
    llmEnabled: bool
    llmModel: str | None = None
    durationMs: int = 0


class Report(BaseModel):
    """Full analyze response — deterministic Evidence + optional narrative."""

    plot: PlotInfo
    crop: CropInfo
    analysisDate: date
    moistureAssessment: MoistureAssessment
    causes: list[Cause] = Field(default_factory=list)
    recommendations: Recommendations
    sources: list[Source] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    missingData: list[str] = Field(default_factory=list)
    narrative: Narrative | None = None
    meta: ReportMeta
