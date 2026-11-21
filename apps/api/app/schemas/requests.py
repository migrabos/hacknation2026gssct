"""Incoming API request models."""

from __future__ import annotations

from datetime import date, timedelta

from pydantic import BaseModel, Field, model_validator


class AnalyzeRequest(BaseModel):
    """POST /analyze body.

    Require plotId XOR (lat + lng). analysisDate must be within the last 10 years.
    """

    plotId: str | None = None
    lat: float | None = Field(default=None, ge=-90, le=90)
    lng: float | None = Field(default=None, ge=-180, le=180)
    cropId: str = Field(
        description="One of: kukurydza|ziemniak|warzywa|zboza|rzepak",
    )
    analysisDate: date

    @model_validator(mode="after")
    def validate_location_and_date(self) -> AnalyzeRequest:
        has_plot = bool(self.plotId and self.plotId.strip())
        has_coords = self.lat is not None and self.lng is not None
        if has_plot == has_coords:
            raise ValueError(
                "Podaj albo plotId, albo parę lat+lng (dokładnie jedną opcję)."
            )

        today = date.today()
        earliest = today - timedelta(days=365 * 10)
        if self.analysisDate > today:
            raise ValueError("analysisDate nie może być w przyszłości.")
        if self.analysisDate < earliest:
            raise ValueError("analysisDate musi mieścić się w ostatnich 10 latach.")
        return self
