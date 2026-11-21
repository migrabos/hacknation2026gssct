/** Keeps the last report in sessionStorage so /raport survives a refresh. */
import type { Report } from "./types";

const KEY = "retencja:lastReport";

export function saveReport(report: Report): void {
  try {
    sessionStorage.setItem(KEY, JSON.stringify(report));
  } catch {
    /* storage unavailable — report page will show "no report" state */
  }
}

export function loadReport(): Report | null {
  try {
    const raw = sessionStorage.getItem(KEY);
    return raw ? (JSON.parse(raw) as Report) : null;
  } catch {
    return null;
  }
}
