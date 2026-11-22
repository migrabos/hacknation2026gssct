/** Keeps the last report (and the form that produced it) in sessionStorage so /raport survives a refresh
 *  and "Zmień uprawę lub datę" brings the farmer back to a filled-in form. */
import type { Plot, Region, Report } from "./types";

const KEY = "retencja:lastReport";
const FORM_KEY = "retencja:lastForm";

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

/** What the farmer picked on /analizuj — restored when they come back from the report. */
export interface SavedForm {
  plot: Plot | null;
  region: Region | null;
  cropId: string;
  date: string;
}

export const saveForm = (form: SavedForm) => save(FORM_KEY, form);
export const loadForm = () => load<SavedForm>(FORM_KEY);
export function clearForm() {
  try {
    sessionStorage.removeItem(FORM_KEY);
  } catch {
    /* ignore */
  }
}
