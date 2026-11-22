// MapLibre 6 runs tile parsing in a Web Worker loaded from its own file. Bundlers
// (Turbopack) don't emit it, so we serve a copy from /public and point setWorkerUrl at it.
import { copyFileSync, mkdirSync } from "node:fs";
import { createRequire } from "node:module";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const require = createRequire(import.meta.url);
const src = join(dirname(require.resolve("maplibre-gl/package.json")), "dist", "maplibre-gl-worker.mjs");
const outDir = join(dirname(fileURLToPath(import.meta.url)), "..", "public");
mkdirSync(outDir, { recursive: true });
copyFileSync(src, join(outDir, "maplibre-gl-worker.mjs"));
