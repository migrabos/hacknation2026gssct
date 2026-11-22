export const THEME_STORAGE_KEY = "retencja-theme";

export type Theme = "light" | "dark";

/** Dark is the default look; the farmer's own choice (toggle) is remembered and wins. */
export const DEFAULT_THEME: Theme = "dark";

export function readStoredTheme(): Theme | null {
  try {
    const stored = localStorage.getItem(THEME_STORAGE_KEY);
    if (stored === "light" || stored === "dark") return stored;
  } catch {
    /* private mode / blocked storage */
  }
  return null;
}

export function applyTheme(theme: Theme) {
  document.documentElement.classList.toggle("dark", theme === "dark");
  document.documentElement.style.colorScheme = theme;
}

export function resolveInitialTheme(): Theme {
  return readStoredTheme() ?? DEFAULT_THEME;
}

