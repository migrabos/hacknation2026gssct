import { applyTheme, resolveInitialTheme } from "./theme";

/** Accessibility settings (WCAG 2.x AA helpers): text size and high-contrast mode. */

export const FONT_SCALE_STORAGE_KEY = "retencja-font-scale";
export const CONTRAST_STORAGE_KEY = "retencja-contrast";

/** 0 = 100%, 1 = 125%, 2 = 150% of the browser's base text size. */
export type FontScale = 0 | 1 | 2;
export const FONT_SCALES: FontScale[] = [0, 1, 2];

export function readFontScale(): FontScale {
  try {
    const v = Number(localStorage.getItem(FONT_SCALE_STORAGE_KEY));
    if (v === 1 || v === 2) return v;
  } catch {
    /* blocked storage */
  }
  return 0;
}

export function readContrast(): boolean {
  try {
    return localStorage.getItem(CONTRAST_STORAGE_KEY) === "1";
  } catch {
    return false;
  }
}

export function applyFontScale(scale: FontScale) {
  const root = document.documentElement;
  if (scale === 0) delete root.dataset.fontScale;
  else root.dataset.fontScale = String(scale);
}

/** High contrast is a black-background look, so it also switches the dark class on (maps follow it). */
export function applyContrast(on: boolean) {
  document.documentElement.classList.toggle("contrast", on);
  if (on) applyTheme("dark");
  else applyTheme(resolveInitialTheme());
}

export function save(key: string, value: string) {
  try {
    localStorage.setItem(key, value);
  } catch {
    /* ignore */
  }
}

export function applyInitialA11y() {
  applyFontScale(readFontScale());
  if (readContrast()) applyContrast(true);
}
