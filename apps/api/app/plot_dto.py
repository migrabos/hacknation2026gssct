"""Resolver plot dict (plot/resolver.py) → `Plot` in apps/web/lib/types.ts.

The resolver keeps centroid as [lat, lng] (what meteo/soil adapters want); the web
contract uses GeoJSON order [lng, lat]. This is the only place that flips it.
"""

from __future__ import annotations

from typing import Any

from adapters.licenses import license_for
from app.schemas.evidence import Hydro, LandUse, Plot, RetentionSpot, Source, Terrain


def plot_to_dto(p: dict[str, Any]) -> Plot:
    lat, lng = p["centroid"]
    terrain = p.get("terrain")
    hydro = p.get("hydro")
    land_use = p.get("landUse")
    runoff = (terrain or {}).get("runoffRisk")
    return Plot(
        plotId=p["plotId"],
        geometry=p["geometry"],
        centroid=(lng, lat),
        areaHa=p["areaHa"],
        bbox=tuple(p["bbox"]),  # type: ignore[arg-type]
        voivodeship=p.get("voivodeship"),
        county=p.get("county"),
        commune=p.get("commune"),
        terrain=Terrain(
            slopePct=terrain.get("slopePct"),
            runoffRisk=runoff if runoff in ("low", "medium", "high") else None,
        ) if terrain else None,
        retentionSpot=RetentionSpot(**terrain["retentionSpot"]) if (terrain or {}).get("retentionSpot") else None,
        hydro=Hydro(
            nearbyWater=hydro.get("nearbyWater"),
            distanceClass=hydro.get("distanceClass"),
            missing=bool(hydro.get("missing")),
        ) if hydro else None,
        landUse=LandUse(**{k: land_use.get(k) for k in LandUse.model_fields if land_use.get(k) is not None})
        if land_use else None,
        sources=[
            Source(id=f"plot_{i}", name=s["name"], provider=s["name"], url=s.get("url") or None,
                   fetchedAt=s.get("fetchedAt"), mode="live", status="ok", license=license_for(s["name"]))
            for i, s in enumerate(p.get("sources") or [])
        ],
        fetchedAt=p.get("fetchedAt"),
    )
