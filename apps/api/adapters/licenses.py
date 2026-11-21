"""Licence / terms per data source (matched by prefix of `sources[].name`).

Shared by warm_cache (provenance log) and the report (`sources[].license`).
"""

from __future__ import annotations

LICENSES: dict[str, str] = {
    "ULDK GUGiK": "Dane GUGiK (EGiB) udostępniane bezpłatnie – ustawa Prawo geodezyjne i kartograficzne, art. 40a",
    "PRG GUGiK": "Dane GUGiK (Państwowy Rejestr Granic – nazwy obrębów do wyszukiwarki miejscowości) udostępniane bezpłatnie – ustawa Prawo geodezyjne i kartograficzne, art. 40a",
    "GUGiK NMT": "Dane GUGiK (NMT) udostępniane bezpłatnie – ustawa Prawo geodezyjne i kartograficzne, art. 40a",
    "Open-Meteo Elevation": "Open-Meteo, dane CC BY 4.0 (Copernicus DEM GLO-90); API bezpłatne do użytku niekomercyjnego",
    "Open-Meteo Historical": "Open-Meteo, dane CC BY 4.0 (ERA5/ERA5-Land, Copernicus C3S); API bezpłatne do użytku niekomercyjnego (<10 000 zapytań/dzień)",
    "Open-Meteo Forecast": "Open-Meteo, dane CC BY 4.0; API bezpłatne do użytku niekomercyjnego",
    "NASA POWER": "NASA POWER – dane publiczne bez ograniczeń (NASA Earth Science Data Policy), prośba o cytowanie",
    "ISRIC SoilGrids": "ISRIC SoilGrids 2.0 – CC BY 4.0",
    "Sentinel-2": "Copernicus Sentinel data – licencja pełna, otwarta i bezpłatna (Rozp. UE 1159/2013); katalog STAC Element84 Earth Search",
    "OpenStreetMap": "© OpenStreetMap contributors – ODbL 1.0",
    "EDO": "Copernicus Emergency Management Service – EDO, CC BY 4.0",
}


def license_for(name: str) -> str | None:
    for prefix, lic in LICENSES.items():
        if name.startswith(prefix) or prefix in name:
            return lic
    return None
