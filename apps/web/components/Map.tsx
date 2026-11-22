"use client";

import dynamic from "next/dynamic";
import { createContext, useContext } from "react";
import type { MapPickerProps } from "./MapPicker";

/** Height of the map being loaded, so the placeholder takes exactly its space (no jump when Leaflet arrives). */
const PlaceholderHeight = createContext<number | string>(520);

function MapPlaceholder() {
  const height = useContext(PlaceholderHeight);
  return (
    <div className="map-block">
      <div className="map-wrap map-placeholder" style={{ height }}>
        <span className="muted">Ładowanie mapy…</span>
      </div>
    </div>
  );
}

/** Client-only map (Leaflet touches `window`). */
const MapPicker = dynamic(() => import("./MapPicker"), {
  ssr: false,
  loading: () => <MapPlaceholder />,
});

export default function Map(props: MapPickerProps) {
  return (
    <PlaceholderHeight.Provider value={props.height ?? 520}>
      <MapPicker {...props} />
    </PlaceholderHeight.Provider>
  );
}
