/** Keeps the last reports in sessionStorage so /raport and /dobor-uprawy survive a refresh. */
import type { CropFitReport, Report } from "./types";

const KEY = "retencja:lastReport";
const CROP_FIT_KEY = "retencja:lastCropFit";

function save(key: string, value: unknown): void {
  try {
    sessionStorage.setItem(key, JSON.stringify(value));
  } catch {
    /* storage unavailable — report page will show "no report" state */
  }
}

function load<T>(key: string): T | null {
  try {
    const raw = sessionStorage.getItem(key);
    return raw ? (JSON.parse(raw) as T) : null;
  } catch {
    return null;
  }
}

export const saveReport = (report: Report) => save(KEY, report);
export const loadReport = () => load<Report>(KEY);

export const saveCropFitReport = (report: CropFitReport) => save(CROP_FIT_KEY, report);
export const loadCropFitReport = () => load<CropFitReport>(CROP_FIT_KEY);
