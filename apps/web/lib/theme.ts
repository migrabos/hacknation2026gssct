export const THEME_STORAGE_KEY = "retencja-theme";

export type Theme = "light" | "dark";

/** Light is the default look; the farmer's own choice (toggle) is remembered and wins. */
export const DEFAULT_THEME: Theme = "light";

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
  const root = document.documentElement;
  // High-contrast mode (lib/a11y.ts) is a black look: keep the dark class while it is on.
  const effective: Theme = root.classList.contains("contrast") ? "dark" : theme;
  root.classList.toggle("dark", effective === "dark");
  root.style.colorScheme = effective;
}

export function resolveInitialTheme(): Theme {
  return readStoredTheme() ?? DEFAULT_THEME;
}

