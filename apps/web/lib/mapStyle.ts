/**
 * Own MapLibre style for the Retencja map, drawn from OpenFreeMap vector tiles
 * (OpenMapTiles schema, © OpenStreetMap contributors). Keyless, no usage limits.
 *
 * Deliberately sparse: land in the site's pale green, WATER emphasised (rivers,
 * streams, ditches, wetlands — that's what this app is about), muted roads,
 * Polish names in the site's text colour.
 *
 * `variant: "base"`   — full map
 * `variant: "labels"` — only names (+ waterways) to lay over the aerial photo
 */
import type { StyleSpecification, LayerSpecification, ExpressionSpecification } from "maplibre-gl";

export type MapTheme = "light" | "dark";
export type MapVariant = "base" | "labels";

export const OPENFREEMAP_ATTRIBUTION =
  '<a href="https://openfreemap.org" target="_blank" rel="noopener">OpenFreeMap</a> ' +
  '&copy; <a href="https://www.openmaptiles.org/" target="_blank" rel="noopener">OpenMapTiles</a> ' +
  '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a>';

const PALETTE = {
  light: {
    land: "#f3f6f1",
    farmland: "#eef3e7",
    grass: "#e5eedb",
    wood: "#d6e5d0",
    wetland: "#d9ebe8",
    sand: "#f1eee2",
    residential: "#eaece7",
    industrial: "#e6e6e2",
    building: "#dfe3dc",
    water: "#a8cde6",
    waterLine: "#6fa9d4",
    waterText: "#2f6896",
    road: "#ffffff",
    roadCase: "#d3d9d2",
    roadMajorCase: "#bfc8be",
    track: "#c4cbc2",
    rail: "#b6bdb5",
    border: "#7f8a82",
    borderAdmin: "#b8c1b9",
    text: "#1b1f1c",
    textSoft: "#3c463f",
    textMuted: "#6b746d",
    halo: "#f6faf6",
  },
  dark: {
    land: "#161b17",
    farmland: "#181e19",
    grass: "#1a221b",
    wood: "#1c2a1f",
    wetland: "#18282a",
    sand: "#22211b",
    residential: "#1c211d",
    industrial: "#1f221f",
    building: "#232a25",
    water: "#1d3a50",
    waterLine: "#3a76a3",
    waterText: "#8dbbe0",
    road: "#2c342e",
    roadCase: "#161b17",
    roadMajorCase: "#3a453c",
    track: "#343d36",
    rail: "#3a423c",
    border: "#7c887f",
    borderAdmin: "#3e4840",
    text: "#e8ebe8",
    textSoft: "#c9cfca",
    textMuted: "#9aa39c",
    halo: "#121512",
  },
} as const;

/** Colours of the labels drawn over the aerial photo (independent of site theme). */
const ON_PHOTO = { text: "#ffffff", textSoft: "#f2f5f2", halo: "rgba(15, 25, 18, 0.85)", waterText: "#d4ecff" };

const NAME: ExpressionSpecification = ["coalesce", ["get", "name:pl"], ["get", "name"]];
const FONT = ["Noto Sans Regular"];
const FONT_BOLD = ["Noto Sans Bold"];
const FONT_ITALIC = ["Noto Sans Italic"];

const lerp = (stops: [number, number][]): ExpressionSpecification =>
  ["interpolate", ["exponential", 1.5], ["zoom"], ...stops.flat()] as ExpressionSpecification;

export function buildMapStyle(theme: MapTheme, variant: MapVariant): StyleSpecification {
  const c = PALETTE[theme];
  const onPhoto = variant === "labels";
  const t = onPhoto ? ON_PHOTO : c;
  const layers: LayerSpecification[] = [];

  if (!onPhoto) {
    layers.push(
      { id: "land", type: "background", paint: { "background-color": c.land } },
      {
        id: "landcover",
        type: "fill",
        source: "omt",
        "source-layer": "landcover",
        paint: {
          "fill-color": [
            "match",
            ["get", "class"],
            "farmland", c.farmland,
            "grass", c.grass,
            "wood", c.wood,
            "wetland", c.wetland,
            "sand", c.sand,
            c.land,
          ],
          "fill-antialias": false,
        },
      },
      {
        id: "landuse",
        type: "fill",
        source: "omt",
        "source-layer": "landuse",
        filter: ["in", ["get", "class"], ["literal", ["residential", "suburb", "neighbourhood", "commercial", "industrial", "retail", "railway"]]],
        paint: {
          "fill-color": ["match", ["get", "class"], ["industrial", "commercial", "retail", "railway"], c.industrial, c.residential],
          "fill-opacity": lerp([[8, 0.6], [12, 1]]),
        },
      },
      {
        id: "park",
        type: "fill",
        source: "omt",
        "source-layer": "park",
        paint: { "fill-color": c.wood, "fill-opacity": 0.5 },
      },
    );
  }

  // --- water: always visible, also over the photo (thin lines only there) ---
  if (!onPhoto) {
    layers.push({
      id: "water",
      type: "fill",
      source: "omt",
      "source-layer": "water",
      paint: { "fill-color": c.water },
    });
  }
  layers.push(
    {
      id: "waterway-small",
      type: "line",
      source: "omt",
      "source-layer": "waterway",
      minzoom: 11,
      filter: ["in", ["get", "class"], ["literal", ["stream", "ditch", "drain"]]],
      layout: { "line-cap": "round", "line-join": "round" },
      paint: {
        "line-color": onPhoto ? "#7cc4ff" : c.waterLine,
        "line-width": lerp([[11, 0.6], [14, 1.4], [17, 2.6]]),
        "line-opacity": onPhoto ? 0.85 : 1,
      },
    },
    {
      id: "waterway-big",
      type: "line",
      source: "omt",
      "source-layer": "waterway",
      filter: ["in", ["get", "class"], ["literal", ["river", "canal"]]],
      layout: { "line-cap": "round", "line-join": "round" },
      paint: {
        "line-color": onPhoto ? "#7cc4ff" : c.waterLine,
        "line-width": lerp([[7, 0.8], [11, 1.8], [15, 4], [18, 8]]),
        "line-opacity": onPhoto ? 0.7 : 1,
      },
    },
  );

  if (!onPhoto) {
    layers.push(
      {
        id: "building",
        type: "fill",
        source: "omt",
        "source-layer": "building",
        minzoom: 14,
        paint: { "fill-color": c.building, "fill-opacity": lerp([[14, 0], [15, 1]]) },
      },
      // country + voivodeship borders
      {
        id: "border-admin",
        type: "line",
        source: "omt",
        "source-layer": "boundary",
        filter: ["all", ["==", ["get", "admin_level"], 4], ["!=", ["get", "maritime"], 1]],
        minzoom: 7,
        maxzoom: 11,
        paint: { "line-color": c.borderAdmin, "line-width": 0.8, "line-dasharray": [4, 3], "line-opacity": 0.6 },
      },
      {
        id: "border-country",
        type: "line",
        source: "omt",
        "source-layer": "boundary",
        filter: ["all", ["==", ["get", "admin_level"], 2], ["!=", ["get", "maritime"], 1]],
        paint: { "line-color": c.border, "line-width": lerp([[4, 0.8], [10, 2]]), "line-opacity": 0.7 },
      },
      // roads: unpaved tracks dashed, then casing + fill
      {
        id: "road-track",
        type: "line",
        source: "omt",
        "source-layer": "transportation",
        minzoom: 13,
        filter: ["in", ["get", "class"], ["literal", ["track", "path"]]],
        paint: { "line-color": c.track, "line-width": lerp([[13, 0.6], [17, 1.6]]), "line-dasharray": [3, 2] },
      },
      {
        id: "road-rail",
        type: "line",
        source: "omt",
        "source-layer": "transportation",
        minzoom: 9,
        filter: ["==", ["get", "class"], "rail"],
        paint: { "line-color": c.rail, "line-width": lerp([[9, 0.5], [15, 1.4]]) },
      },
      {
        id: "road-minor-case",
        type: "line",
        source: "omt",
        "source-layer": "transportation",
        minzoom: 12,
        filter: ["in", ["get", "class"], ["literal", ["minor", "service", "tertiary"]]],
        layout: { "line-cap": "round", "line-join": "round" },
        paint: { "line-color": c.roadCase, "line-width": lerp([[12, 1.2], [15, 5], [18, 16]]) },
      },
      {
        id: "road-major-case",
        type: "line",
        source: "omt",
        "source-layer": "transportation",
        minzoom: 6,
        filter: ["in", ["get", "class"], ["literal", ["motorway", "trunk", "primary", "secondary"]]],
        layout: { "line-cap": "round", "line-join": "round" },
        paint: { "line-color": c.roadMajorCase, "line-width": lerp([[6, 0.8], [10, 2.6], [15, 9], [18, 24]]) },
      },
      {
        id: "road-minor",
        type: "line",
        source: "omt",
        "source-layer": "transportation",
        minzoom: 12,
        filter: ["in", ["get", "class"], ["literal", ["minor", "service", "tertiary"]]],
        layout: { "line-cap": "round", "line-join": "round" },
        paint: { "line-color": c.road, "line-width": lerp([[12, 0.4], [15, 3.4], [18, 13]]) },
      },
      {
        id: "road-major",
        type: "line",
        source: "omt",
        "source-layer": "transportation",
        minzoom: 6,
        filter: ["in", ["get", "class"], ["literal", ["motorway", "trunk", "primary", "secondary"]]],
        layout: { "line-cap": "round", "line-join": "round" },
        paint: { "line-color": c.road, "line-width": lerp([[6, 0.3], [10, 1.6], [15, 7], [18, 21]]) },
      },
    );
  }

  // --- labels ---
  layers.push(
    {
      id: "label-water",
      type: "symbol",
      source: "omt",
      "source-layer": "water_name",
      layout: { "text-field": NAME, "text-font": FONT_ITALIC, "text-size": 12, "text-max-width": 8 },
      paint: { "text-color": t.waterText, "text-halo-color": t.halo, "text-halo-width": 1.2 },
    },
    {
      id: "label-waterway",
      type: "symbol",
      source: "omt",
      "source-layer": "waterway",
      minzoom: 12,
      filter: ["in", ["get", "class"], ["literal", ["river", "canal", "stream"]]],
      layout: {
        "symbol-placement": "line",
        "text-field": NAME,
        "text-font": FONT_ITALIC,
        "text-size": 11.5,
        "symbol-spacing": 350,
      },
      paint: { "text-color": t.waterText, "text-halo-color": t.halo, "text-halo-width": 1.2 },
    },
    {
      id: "label-road",
      type: "symbol",
      source: "omt",
      "source-layer": "transportation_name",
      minzoom: 14,
      layout: {
        "symbol-placement": "line",
        "text-field": NAME,
        "text-font": FONT,
        "text-size": 11,
        "symbol-spacing": 400,
      },
      paint: { "text-color": onPhoto ? t.textSoft : c.textMuted, "text-halo-color": t.halo, "text-halo-width": 1.4 },
    },
    {
      id: "label-village",
      type: "symbol",
      source: "omt",
      "source-layer": "place",
      minzoom: 10,
      filter: ["in", ["get", "class"], ["literal", ["village", "hamlet", "suburb", "isolated_dwelling", "neighbourhood", "quarter"]]],
      layout: {
        "text-field": NAME,
        "text-font": FONT,
        "text-size": [
          "interpolate", ["linear"], ["zoom"],
          10, ["match", ["get", "class"], "village", 11, 9.5],
          15, ["match", ["get", "class"], "village", 15, 12.5],
        ] as ExpressionSpecification,
        "text-max-width": 8,
      },
      paint: { "text-color": t.textSoft, "text-halo-color": t.halo, "text-halo-width": 1.6 },
    },
    {
      id: "label-town",
      type: "symbol",
      source: "omt",
      "source-layer": "place",
      minzoom: 6,
      filter: ["in", ["get", "class"], ["literal", ["city", "town"]]],
      layout: {
        "text-field": NAME,
        "text-font": ["match", ["get", "class"], "city", ["literal", FONT_BOLD], ["literal", FONT]] as ExpressionSpecification,
        "text-size": [
          "interpolate", ["linear"], ["zoom"],
          5, ["match", ["get", "class"], "city", 12, 9],
          12, ["match", ["get", "class"], "city", 20, 15],
        ] as ExpressionSpecification,
        "text-max-width": 8,
        "symbol-sort-key": ["get", "rank"],
      },
      paint: { "text-color": t.text, "text-halo-color": t.halo, "text-halo-width": 1.8 },
    },
    {
      id: "label-country",
      type: "symbol",
      source: "omt",
      "source-layer": "place",
      maxzoom: 7,
      filter: ["==", ["get", "class"], "country"],
      layout: {
        "text-field": NAME,
        "text-font": FONT_BOLD,
        "text-size": 13,
        "text-transform": "uppercase",
        "text-letter-spacing": 0.15,
      },
      paint: { "text-color": onPhoto ? t.textSoft : c.textMuted, "text-halo-color": t.halo, "text-halo-width": 1.5 },
    },
  );

  return {
    version: 8,
    // zooms above are written in Leaflet terms; the GL map renders one level lower (512px tiles)
    layers: layers.map(toGlZoom),
    glyphs: "https://tiles.openfreemap.org/fonts/{fontstack}/{range}.pbf",
    sources: {
      omt: { type: "vector", url: "https://tiles.openfreemap.org/planet", attribution: OPENFREEMAP_ATTRIBUTION },
    },
  };
}

/** maplibre-gl-leaflet drives the GL map at Leaflet zoom − 1; shift min/max zoom and zoom stops. */
const ZOOM_OFFSET = -1;

function shiftZoomStops(expr: unknown): unknown {
  if (!Array.isArray(expr)) return expr;
  if ((expr[0] === "interpolate" || expr[0] === "step") && Array.isArray(expr[expr[0] === "step" ? 1 : 2]) && (expr[expr[0] === "step" ? 1 : 2] as unknown[])[0] === "zoom") {
    const head = expr[0] === "interpolate" ? 3 : 3; // interpolate: [op, type, input, z, v...]; step: [op, input, v0, z, v...]
    return expr.map((v, i) => (i >= head && (i - head) % 2 === 0 && typeof v === "number" ? v + ZOOM_OFFSET : shiftZoomStops(v)));
  }
  return expr.map(shiftZoomStops);
}

function toGlZoom(layer: LayerSpecification): LayerSpecification {
  const out: Record<string, unknown> = { ...layer };
  if (typeof layer.minzoom === "number") out.minzoom = Math.max(0, layer.minzoom + ZOOM_OFFSET);
  if (typeof layer.maxzoom === "number") out.maxzoom = layer.maxzoom + ZOOM_OFFSET;
  for (const key of ["paint", "layout"] as const) {
    const block = layer[key] as Record<string, unknown> | undefined;
    if (block) out[key] = Object.fromEntries(Object.entries(block).map(([k, v]) => [k, shiftZoomStops(v)]));
  }
  return out as unknown as LayerSpecification;
}
