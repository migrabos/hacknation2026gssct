/** Keeps the last report in sessionStorage so /raport survives a refresh. */
import type { Report } from "./types";

const KEY = "retencja:lastReport";

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
