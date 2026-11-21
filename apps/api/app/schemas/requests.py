"""Incoming API request models."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field, model_validator

from adapters.dates import shift_years, today_pl


class PlotDateRequest(BaseModel):
    """Plot + date part shared by POST /analyze and POST /crop-fit.

    Give plotId (preferred) or lat+lng. If both are sent, plotId wins.
    analysisDate must be within the last 10 years.
    """

    plotId: str | None = None
    lat: float | None = Field(default=None, ge=-90, le=90)
    lng: float | None = Field(default=None, ge=-180, le=180)
    analysisDate: date

    @model_validator(mode="after")
    def validate_location_and_date(self) -> PlotDateRequest:
        has_plot = bool(self.plotId and self.plotId.strip())
        has_coords = self.lat is not None and self.lng is not None
        if not has_plot and not has_coords:
            raise ValueError("Podaj identyfikator działki (plotId) albo parę lat+lng.")
        if has_plot:
            self.plotId = self.plotId.strip()  # type: ignore[union-attr]
            self.lat = self.lng = None

        today = today_pl()  # Polish time, same as the date picker in the browser
        earliest = shift_years(today, -10)  # calendar years, same as the web form's min date
        if self.analysisDate > today:
            raise ValueError("analysisDate nie może być w przyszłości.")
        if self.analysisDate < earliest:
            raise ValueError("analysisDate musi mieścić się w ostatnich 10 latach.")
        return self


class AnalyzeRequest(PlotDateRequest):
    """POST /analyze body — the water report for one crop."""

    cropId: str = Field(description="Crop id from GET /crops")


class CropFitRequest(PlotDateRequest):
    """POST /crop-fit body — which crops cope best with the water on this plot (no crop needed)."""
