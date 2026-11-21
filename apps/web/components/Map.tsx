"use client";

import dynamic from "next/dynamic";
import type { MapPickerProps } from "./MapPicker";

/** Client-only map (Leaflet touches `window`). */
const MapPicker = dynamic(() => import("./MapPicker"), {
  ssr: false,
  loading: () => (
    <div className="map-wrap" style={{ height: 520, display: "grid", placeItems: "center" }}>
      <span className="muted">Ładowanie mapy…</span>
    </div>
  ),
});

export default function Map(props: MapPickerProps) {
  return <MapPicker {...props} />;
}
