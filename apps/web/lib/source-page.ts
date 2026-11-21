import type { Source } from "./types";

const cadastre = "https://www.geoportal.gov.pl/pl/dane/ewidencja-gruntow-i-budynkow-egib/";

/** Public information pages for readers. Source.url identifies the data request. */
export function sourcePage(source: Source): string | undefined {
  switch (source.id) {
    case "uldk":
    case "land_use":
      return cadastre;
    case "dem":
      return source.provider?.includes("Elevation")
        ? "https://open-meteo.com/en/docs/elevation-api"
        : "https://www.geoportal.gov.pl/pl/dane/numeryczny-model-terenu-nmt/";
    case "hydro":
      if (source.provider?.includes("OpenFreeMap")) return "https://openfreemap.org/";
      if (!source.provider || source.provider.includes("OpenStreetMap")) return "https://www.openstreetmap.org/about";
      return undefined;
    case "open_meteo":
      return "https://open-meteo.com/en/docs/historical-weather-api";
    case "soilgrids":
      return "https://isric.org/explore/soilgrids";
    case "sentinel2":
      return "https://dataspace.copernicus.eu/data-collections/copernicus-sentinel-missions/sentinel-2";
    case "edo":
      return "https://drought.emergency.copernicus.eu/";
  }
}
