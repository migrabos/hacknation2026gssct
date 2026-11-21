"""AdapterProtocol + documented value shapes for Person 2.

Mock `values` keys the engine reads:

plot:
  plotId, geometry, centroid {lat,lng}, areaHa, bbox, voivodeship,
  terrain.slopePct, terrain.runoffRisk, hydro.nearbyWater, hydro.distanceClass

meteo:
  precipMmLast30d, precipMmClimate30d, drySpellDays, precipAnomalyPct10y,
  monthlyPrecipMm[12]

soil:
  sandPct, clayPct, socPct, awcMmProxy

sat:
  ndviLatest, ndviAnomaly  (nullable; stub OK)

drought:
  iungClass  (nullable)

hydro:
  nearbyWater, distanceClass  (nullable)
"""

from __future__ import annotations

from datetime import date
from typing import Protocol, runtime_checkable

from app.schemas.adapters import AdapterResult


@runtime_checkable
class AdapterProtocol(Protocol):
    """Person 2 adapters must satisfy this async callable shape."""

    async def fetch(
        self,
        *,
        plot_id: str | None,
        lat: float | None,
        lng: float | None,
        analysis_date: date,
    ) -> AdapterResult: ...
