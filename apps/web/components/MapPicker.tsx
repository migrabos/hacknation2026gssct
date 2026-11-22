"use client";

/**
 * Leaflet map: aerial photo / street basemap, national parcel boundaries,
 * click-to-pick and the selected plot highlighted.
 *
 * Layers (all public, CORS-enabled, no key):
 *  - Geoportal ORTO WMTS StandardResolution (EPSG:3857) — fast overview
 *  - Geoportal ORTO WMS HighResolution — sharp photo from zoom 15
 *  - GUGiK Krajowa Integracja Ewidencji Gruntów (KIEG) WMS — parcel lines + numbers, zoom ≥ 15
 *  - Own vector map (lib/mapStyle.ts) over OpenFreeMap tiles, rendered by MapLibre
 *    inside Leaflet — site colours, water emphasised, Polish names; its labels-only
 *    variant sits on top of the aerial photo. Only ONE WebGL map is alive at a time.
 *  - Fallback when WebGL2 is missing or software-only (old devices, GPU blocklisted,
 *    hardware acceleration off): plain OpenStreetMap raster tiles, photo without labels.
 *
 * Load via components/Map.tsx (dynamic, ssr:false) — Leaflet needs `window`.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  GeoJSON,
  MapContainer,
  Marker,
  ScaleControl,
  TileLayer,
  WMSTileLayer,
  ZoomControl,
  useMap,
  useMapEvents,
} from "react-leaflet";
import L from "leaflet";
import type { LatLngBoundsExpression, LatLngExpression } from "leaflet";
import "maplibre-gl/dist/maplibre-gl.css";
import { maplibreGL } from "@maplibre/maplibre-gl-leaflet";
import { setWorkerUrl } from "maplibre-gl";
import { buildMapStyle, type MapTheme, type MapVariant } from "@/lib/mapStyle";
import type { Plot, RetentionSpot } from "@/lib/types";
import { LocateIcon } from "./Icons";

// Served from /public (copied by scripts/copy-maplibre-worker.mjs) — the bundler can't locate it.
setWorkerUrl("/maplibre-gl-worker.mjs");

const POLAND_CENTER: LatLngExpression = [52.07, 19.48];
const POLAND_ZOOM = 6;
/** Parcel lines are only served / readable from this zoom. */
const PARCEL_MIN_ZOOM = 15;
/** Below this zoom a click zooms in instead of picking. */
const PICK_MIN_ZOOM = 14;

const ORTO_WMTS =
  "https://mapy.geoportal.gov.pl/wss/service/PZGIK/ORTO/WMTS/StandardResolution" +
  "?SERVICE=WMTS&REQUEST=GetTile&VERSION=1.0.0&LAYER=ORTOFOTOMAPA&STYLE=default" +
  "&FORMAT=image/jpeg&TILEMATRIXSET=EPSG:3857&TILEMATRIX=EPSG:3857:{z}&TILEROW={y}&TILECOL={x}";
const ORTO_WMS_HR = "https://mapy.geoportal.gov.pl/wss/service/PZGIK/ORTO/WMS/HighResolution";
const KIEG_WMS = "https://integracja.gugik.gov.pl/cgi-bin/KrajowaIntegracjaEwidencjiGruntow";

const OSM_TILES = "https://tile.openstreetmap.org/{z}/{x}/{y}.png";

const ATTR_GUGIK = '&copy; <a href="https://www.geoportal.gov.pl/">GUGiK</a>';
const ATTR_OSM = '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>';

/** WebGL settings shared by the probe and MapLibre, so "probe OK" means "MapLibre will start". */
const GL_ATTRIBUTES = {
  antialias: true,
  // keep the frame so the map shows up in print / PDF of the report
  preserveDrawingBuffer: true,
  // refuse software rendering (SwiftShader & co.) — it works but stutters badly
  failIfMajorPerformanceCaveat: true,
};

let vectorSupport: boolean | null = null;
/** Can this browser run the vector map smoothly? (WebGL2 with a real GPU.) Cached per page load. */
function supportsVectorMap(): boolean {
  if (vectorSupport !== null) return vectorSupport;
  try {
    const canvas = document.createElement("canvas");
    const gl = canvas.getContext("webgl2", GL_ATTRIBUTES) as WebGL2RenderingContext | null;
    vectorSupport = Boolean(gl);
    gl?.getExtension("WEBGL_lose_context")?.loseContext();
  } catch {
    vectorSupport = false;
  }
  return vectorSupport;
}

type Basemap = "orto" | "map";

export interface MapPickerProps {
  plot?: Plot | null;
  /** Called with the clicked point. Omit for a read-only map. */
  onPick?: (lat: number, lng: number) => void;
  busy?: boolean;
  height?: number | string;
  defaultBasemap?: Basemap;
  /** [min_lng, min_lat, max_lng, max_lat] to zoom to (e.g. a chosen village). Ignored while a plot is shown. */
  focusBbox?: [number, number, number, number] | null;
}

export default function MapPicker({
  plot,
  onPick,
  busy = false,
  height = 520,
  defaultBasemap = "map",
  focusBbox = null,
}: MapPickerProps) {
  const [basemap, setBasemap] = useState<Basemap>(defaultBasemap);
  const [zoom, setZoom] = useState(POLAND_ZOOM);
  const [vector, setVector] = useState(supportsVectorMap);
  const onVectorFail = useCallback(() => {
    vectorSupport = false;
    setVector(false);
  }, []);
  const [locateMsg, setLocateMsg] = useState<string | null>(null);
  const interactive = Boolean(onPick);

  let hint: string | null = null;
  if (locateMsg) hint = locateMsg;
  else if (interactive && !plot) {
    hint =
      zoom < PICK_MIN_ZOOM
        ? "Przybliż mapę do swojej miejscowości (kliknij, żeby przybliżyć)"
        : "Kliknij swoją działkę";
  } else if (interactive && plot) {
    hint = "Kliknij inną działkę, żeby zmienić wybór";
  }

  return (
    <div className="map-block">
    <div className="map-wrap" style={{ height }}>
      <MapContainer
        center={POLAND_CENTER}
        zoom={POLAND_ZOOM}
        minZoom={5}
        maxZoom={19}
        scrollWheelZoom={interactive}
        className={interactive ? "picking" : undefined}
        attributionControl
        zoomControl={false}
      >
        <ZoomControl position="topright" zoomInTitle="Przybliż" zoomOutTitle="Oddal" />
        <MapPanes />
        {basemap === "map" &&
          (vector ? (
            <VectorLayer key="vec-base" variant="base" pane="tilePane" onFail={onVectorFail} />
          ) : (
            <TileLayer key="osm" url={OSM_TILES} attribution={ATTR_OSM} maxZoom={19} />
          ))}
        {basemap === "orto" && (
          <>
            {/* raster fallback only: street map outside Poland's photo coverage (overview zooms) */}
            {!vector && <TileLayer key="osm-under" url={OSM_TILES} attribution={ATTR_OSM} maxZoom={11} />}
            <TileLayer key="orto-wmts" url={ORTO_WMTS} attribution={ATTR_GUGIK} maxNativeZoom={19} maxZoom={19} />
            <WMSTileLayer
              key="orto-hr"
              url={ORTO_WMS_HR}
              // PNG + transparent: HighResolution has coverage gaps; there the
              // StandardResolution photo underneath stays visible instead of white.
              params={{ layers: "Raster", format: "image/png", transparent: true }}
              minZoom={PARCEL_MIN_ZOOM}
              maxZoom={19}
            />
            {/* our place / road / river names over the photo — the only WebGL map in this mode */}
            {vector && <VectorLayer key="vec-labels" variant="labels" pane="labels" onFail={onVectorFail} />}
          </>
        )}

        <WMSTileLayer
          key={`kieg-${basemap}`}
          url={KIEG_WMS}
          params={{ layers: "dzialki,numery_dzialek", format: "image/png", transparent: true }}
          tileSize={512}
          pane="parcels"
          className={basemap === "orto" ? undefined : "parcels-on-map"}
          minZoom={PARCEL_MIN_ZOOM}
          maxZoom={19}
          opacity={basemap === "orto" ? 0.95 : 0.9}
          attribution="działki: GUGiK KIEG"
        />

        {plot && <PlotShape plot={plot} onOrto={basemap === "orto"} />}
        {plot?.retentionSpot && <RetentionSpotMarker key={plot.plotId} spot={plot.retentionSpot} />}
        {!plot && focusBbox && <FocusBounds bbox={focusBbox} />}

        <ScaleControl position="bottomleft" imperial={false} />
        <ZoomWatcher onZoom={setZoom} />
        {interactive && <ClickHandler onPick={onPick!} disabled={busy} />}
        <LocateEvents onMsg={setLocateMsg} />
        <MapTools basemap={basemap} setBasemap={setBasemap} interactive={interactive} onLocateStart={() => setLocateMsg("Szukam Twojej lokalizacji…")} />
      </MapContainer>

      {hint && !busy && <div className="map-hint">{hint}</div>}
      {busy && (
        <div className="map-loading" role="status">
          <span>
            <span className="spinner" /> Szukam działki…
          </span>
        </div>
      )}
    </div>
    {plot?.retentionSpot && <RetentionLegend spot={plot.retentionSpot} />}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Retention spot = lowest sampled NMT point of the plot (computed in apps/api).

const fmtPl = (x: number, digits = 1) => x.toFixed(digits).replace(".", ",");

// Dot + two "ripple on water" rings (CSS-animated after the outline is drawn; static with reduced motion).
const RETENTION_ICON = L.divIcon({
  className: "retention-dot-icon",
  html:
    '<span class="retention-ripple" aria-hidden="true"></span>' +
    '<span class="retention-ripple retention-ripple-2" aria-hidden="true"></span>' +
    '<span class="retention-dot" aria-hidden="true"></span>',
  iconSize: [16, 16],
  iconAnchor: [8, 8],
});

function hasLocation(spot: RetentionSpot): spot is RetentionSpot & { lat: number; lng: number } {
  return typeof spot.lat === "number" && typeof spot.lng === "number";
}

function RetentionSpotMarker({ spot }: { spot: RetentionSpot }) {
  if (!hasLocation(spot)) return null;
  // Plain map symbol – all details are in the legend under the map (no hover tooltip).
  return <Marker position={[spot.lat, spot.lng]} icon={RETENTION_ICON} interactive={false} keyboard={false} />;
}

function RetentionLegend({ spot }: { spot: RetentionSpot }) {
  if (!hasLocation(spot)) {
    return (
      <div className="map-legend" role="note">
        <span>
          <strong>Miejsce retencji wody nie zostało wskazane.</strong> {spot.reason}
        </span>
      </div>
    );
  }
  return (
    <div className="map-legend" role="note">
      <span className="retention-dot" aria-hidden="true" />
      <span>
        <strong>Sugerowane miejsce retencji wody</strong> – najniższy punkt działki, gdzie naturalnie spływa woda
        opadowa; możliwe miejsce na oczko wodne lub zbiornik.
        {spot.elevationDropM != null && <> Różnica wysokości na działce: {fmtPl(spot.elevationDropM)} m.</>}
        {spot.nearEdge && <> Punkt leży blisko granicy – zachowaj bezpieczną odległość od działki sąsiada.</>}
        {spot.confidence === "medium" && <> Teren mało zróżnicowany – wskazanie orientacyjne.</>}
        <span className="retention-legend-meta">
          {" "}
          ({spot.pointsSampled ?? "kilkadziesiąt"} pomiarów NMT GUGiK
          {spot.gridSpacingM != null && <>, dokładność ok. {Math.round(spot.gridSpacingM)} m</>})
        </span>
      </span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Own vector map (MapLibre inside Leaflet).

/** Extra panes: names over the photo, then parcel lines (above names, below the plot outline). */
function MapPanes() {
  const map = useMap();
  useMemo(() => {
    for (const [name, z] of [
      ["labels", 380],
      ["parcels", 390],
    ] as const) {
      if (!map.getPane(name)) {
        const pane = map.createPane(name);
        pane.style.zIndex = String(z);
        pane.style.pointerEvents = "none";
      }
    }
  }, [map]);
  return null;
}

/** Follows the site's light/dark toggle (class "dark" on <html>). */
function useSiteTheme(): MapTheme {
  const [theme, setTheme] = useState<MapTheme>(() =>
    typeof document !== "undefined" && document.documentElement.classList.contains("dark") ? "dark" : "light",
  );
  useEffect(() => {
    const el = document.documentElement;
    const obs = new MutationObserver(() => setTheme(el.classList.contains("dark") ? "dark" : "light"));
    obs.observe(el, { attributes: true, attributeFilter: ["class"] });
    return () => obs.disconnect();
  }, []);
  return theme;
}

function VectorLayer({ variant, pane, onFail }: { variant: MapVariant; pane: string; onFail: () => void }) {
  const map = useMap();
  const theme = useSiteTheme();
  const [layer, setLayer] = useState<L.MaplibreGL | null>(null);

  useEffect(() => {
    let gl: L.MaplibreGL | null = maplibreGL({
      style: buildMapStyle(theme, variant),
      pane,
      canvasContextAttributes: GL_ATTRIBUTES,
    } as L.LeafletMaplibreGLOptions);
    try {
      gl.addTo(map);
    } catch (err) {
      // WebGL refused after all (probe passed, context creation didn't) → raster fallback
      console.warn("[map] vector map unavailable, using raster tiles", err);
      try {
        gl.remove();
      } catch {
        /* half-initialised layer */
      }
      gl = null;
      onFail();
      return;
    }
    const glMap = gl.getMaplibreMap();
    // GPU reset / too many contexts on weak devices: don't leave a blank map behind
    glMap.on("webglcontextlost", () => onFail());
    setLayer(gl);
    return () => {
      gl?.remove();
      setLayer(null);
    };
    // theme changes are applied with setStyle below, without re-creating the GL map
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [map, variant, pane, onFail]);

  useEffect(() => {
    layer?.getMaplibreMap()?.setStyle(buildMapStyle(theme, variant));
  }, [layer, theme, variant]);

  return null;
}

// ---------------------------------------------------------------------------

function FocusBounds({ bbox }: { bbox: [number, number, number, number] }) {
  const map = useMap();
  const [w, s, e, n] = bbox;
  useEffect(() => {
    map.fitBounds(
      [
        [s, w],
        [n, e],
      ],
      { padding: [24, 24], maxZoom: 15, animate: true },
    );
  }, [map, w, s, e, n]);
  return null;
}

const prefersReducedMotion = () =>
  typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

/** SVG <path> elements of a GeoJSON layer (one per polygon / multipolygon). */
function pathsOf(layer: L.GeoJSON | null): SVGPathElement[] {
  const out: SVGPathElement[] = [];
  layer?.eachLayer((l) => {
    const el = (l as L.Path).getElement?.();
    if (el instanceof SVGPathElement) out.push(el);
  });
  return out;
}

const DRAW_MS = 600;
const FLY_S = 0.8;

/**
 * "Draw" the outline around the plot: dash the stroke to its own length and slide it in,
 * then fade the fill in. Styles are cleared afterwards, so later zoom / pan (which changes
 * the path length) renders a normal solid outline.
 */
function drawOutline(paths: SVGPathElement[]) {
  const restore: (() => void)[] = [];
  for (const p of paths) {
    const len = p.getTotalLength();
    p.style.transition = "none";
    p.style.strokeLinecap = "butt"; // round caps would show a dot at the start of the hidden dash
    p.style.strokeDasharray = `${len} ${len}`;
    p.style.strokeDashoffset = `${len}`;
    p.style.fillOpacity = "0";
    // stroke is now hidden by the dash offset → safe to drop the "born hidden" class (same frame, no flash)
    p.classList.remove(PENDING_CLASS);
    p.getBoundingClientRect(); // commit the start state before transitioning
    p.style.transition = `stroke-dashoffset ${DRAW_MS}ms ease-in-out, fill-opacity 400ms ease ${DRAW_MS - 200}ms`;
    p.style.strokeDashoffset = "0";
    p.style.fillOpacity = "";
    restore.push(() => {
      p.style.transition = p.style.strokeDasharray = p.style.strokeDashoffset = p.style.strokeLinecap = "";
      p.style.fillOpacity = "";
    });
  }
  const t = window.setTimeout(() => restore.forEach((r) => r()), DRAW_MS + 300);
  return () => {
    window.clearTimeout(t);
    restore.forEach((r) => r());
  };
}

/**
 * Paths are created with this class (Leaflet `className` option), so the outline is invisible from
 * its very first paint until the map has flown to the plot — no flash of the full outline, even when
 * React (dev / StrictMode) re-adds the layer and Leaflet creates new <path> elements.
 */
const PENDING_CLASS = "plot-outline--pending";

function PlotShape({ plot, onOrto }: { plot: Plot; onOrto: boolean }) {
  const map = useMap();
  const haloRef = useRef<L.GeoJSON | null>(null);
  const lineRef = useRef<L.GeoJSON | null>(null);
  // Plot whose outline has finished drawing: later re-mounts (basemap toggle) are born visible.
  const [drawnFor, setDrawnFor] = useState<string | null>(null);
  const pending = drawnFor !== plot.plotId && !prefersReducedMotion();
  const outlineClass = pending ? `plot-outline ${PENDING_CLASS}` : "plot-outline";
  const bounds: LatLngBoundsExpression = useMemo(
    () => [
      [plot.bbox[1], plot.bbox[0]],
      [plot.bbox[3], plot.bbox[2]],
    ],
    [plot.bbox],
  );

  // Fly to the plot, then draw its outline (only when a new plot is shown — not on basemap toggle).
  useEffect(() => {
    const opts = { padding: [48, 48] as [number, number], maxZoom: 17 };
    if (prefersReducedMotion()) {
      map.fitBounds(bounds, { ...opts, animate: false });
      return;
    }
    const plotId = plot.plotId;
    const paths = () => [...pathsOf(haloRef.current), ...pathsOf(lineRef.current)];
    let undoDraw: (() => void) | null = null;
    let done: number | undefined;
    let started = false;
    const start = () => {
      if (started) return;
      started = true;
      undoDraw = drawOutline(paths());
      done = window.setTimeout(() => {
        // Leaflet sets className only when a path is created — make sure nothing stays hidden
        paths().forEach((p) => p.classList.remove(PENDING_CLASS));
        setDrawnFor(plotId);
      }, DRAW_MS + 300);
    };
    map.once("moveend", start);
    // Normally drawing starts on "moveend". Fallback only for "already there, nothing to fly"
    // (no moveend) — long enough not to start mid-flight on slow devices.
    const fallback = window.setTimeout(start, 2500);
    map.flyToBounds(bounds, { ...opts, duration: FLY_S });
    return () => {
      map.off("moveend", start);
      window.clearTimeout(fallback);
      window.clearTimeout(done);
      undoDraw?.();
    };
  }, [map, bounds, plot.plotId]);

  const stroke = onOrto ? "#3fe07f" : "#0f6b3a";
  return (
    <>
      {/* white halo underneath keeps the outline readable on any photo */}
      <GeoJSON
        ref={haloRef}
        key={`${plot.plotId}-halo`}
        data={plot.geometry}
        interactive={false}
        style={{ color: "#ffffff", weight: 7, opacity: 0.9, fill: false, className: outlineClass }}
      />
      <GeoJSON
        ref={lineRef}
        key={`${plot.plotId}-${onOrto}`}
        data={plot.geometry}
        interactive={false}
        style={{
          color: stroke,
          weight: 3.5,
          opacity: 1,
          fillColor: stroke,
          fillOpacity: onOrto ? 0.22 : 0.16,
          className: outlineClass,
        }}
      />
    </>
  );
}

function ZoomWatcher({ onZoom }: { onZoom: (z: number) => void }) {
  const map = useMapEvents({ zoomend: () => onZoom(map.getZoom()) });
  useEffect(() => onZoom(map.getZoom()), [map, onZoom]);
  return null;
}

function ClickHandler({ onPick, disabled }: { onPick: (lat: number, lng: number) => void; disabled: boolean }) {
  const map = useMapEvents({
    click(e) {
      if (disabled) return;
      const z = map.getZoom();
      if (z < PICK_MIN_ZOOM) {
        map.flyTo(e.latlng, Math.min(z + 3, PARCEL_MIN_ZOOM), { duration: 0.6 });
        return;
      }
      onPick(e.latlng.lat, e.latlng.lng);
    },
  });
  return null;
}

function LocateEvents({ onMsg }: { onMsg: (m: string | null) => void }) {
  useMapEvents({
    locationfound: () => onMsg(null),
    locationerror: () => {
      onMsg("Nie udało się ustalić lokalizacji — przybliż mapę ręcznie");
      setTimeout(() => onMsg(null), 4000);
    },
  });
  return null;
}

function MapTools({
  basemap,
  setBasemap,
  interactive,
  onLocateStart,
}: {
  basemap: Basemap;
  setBasemap: (b: Basemap) => void;
  interactive: boolean;
  onLocateStart: () => void;
}) {
  const map = useMap();

  // Keep clicks on the toolbar from reaching the map (would pick a plot).
  const stop = (el: HTMLDivElement | null) => {
    if (!el) return;
    import("leaflet").then((L) => {
      L.DomEvent.disableClickPropagation(el);
      L.DomEvent.disableScrollPropagation(el);
    });
  };

  return (
    <div className="map-tools" ref={stop}>
      <div className="seg" role="group" aria-label="Rodzaj mapy">
        <button type="button" aria-pressed={basemap === "orto"} onClick={() => setBasemap("orto")}>
          Zdjęcie lotnicze
        </button>
        <button type="button" aria-pressed={basemap === "map"} onClick={() => setBasemap("map")}>
          Mapa
        </button>
      </div>
      {interactive && (
        <button
          type="button"
          className="map-btn"
          onClick={() => {
            onLocateStart();
            map.locate({ setView: true, maxZoom: 16, timeout: 10_000 });
          }}
        >
          <LocateIcon /> Moja lokalizacja
        </button>
      )}
    </div>
  );
}
