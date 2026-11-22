import { applyTheme, resolveInitialTheme } from "./lib/theme";
import { applyInitialA11y } from "./lib/a11y";

applyTheme(resolveInitialTheme());
applyInitialA11y();
