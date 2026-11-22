"use client";

import { useEffect, useState } from "react";
import {
  CONTRAST_STORAGE_KEY,
  FONT_SCALE_STORAGE_KEY,
  FONT_SCALES,
  applyContrast,
  applyFontScale,
  readContrast,
  readFontScale,
  save,
  type FontScale,
} from "@/lib/a11y";

const FONT_LABELS: Record<FontScale, { text: string; name: string }> = {
  0: { text: "A", name: "Domyślna wielkość tekstu" },
  1: { text: "A+", name: "Większy tekst" },
  2: { text: "A++", name: "Największy tekst" },
};

/** Accessibility bar in the top strip: text size (A / A+ / A++) and high-contrast switch. */
export default function A11yBar() {
  const [scale, setScale] = useState<FontScale>(0);
  const [contrast, setContrast] = useState(false);

  useEffect(() => {
    setScale(readFontScale());
    setContrast(readContrast());
  }, []);

  function pickScale(s: FontScale) {
    setScale(s);
    applyFontScale(s);
    save(FONT_SCALE_STORAGE_KEY, String(s));
  }

  function toggleContrast() {
    const next = !contrast;
    setContrast(next);
    applyContrast(next);
    save(CONTRAST_STORAGE_KEY, next ? "1" : "0");
  }

  return (
    <div className="a11y-bar" role="group" aria-label="Ułatwienia dostępu">
      <div className="a11y-group" role="group" aria-label="Wielkość tekstu">
        <span className="a11y-label" aria-hidden="true">
          Wielkość tekstu:
        </span>
        {FONT_SCALES.map((s) => (
          <button
            key={s}
            type="button"
            className={`a11y-btn a11y-font-${s}`}
            aria-pressed={scale === s}
            aria-label={FONT_LABELS[s].name}
            title={FONT_LABELS[s].name}
            onClick={() => pickScale(s)}
          >
            {FONT_LABELS[s].text}
          </button>
        ))}
      </div>
      <button
        type="button"
        className="a11y-btn a11y-contrast"
        aria-pressed={contrast}
        onClick={toggleContrast}
        aria-label="Wysoki kontrast"
        title={contrast ? "Wyłącz wysoki kontrast" : "Włącz wysoki kontrast"}
      >
        <ContrastIcon />
        <span>Wysoki kontrast</span>
      </button>
    </div>
  );
}

function ContrastIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true">
      <circle cx="8" cy="8" r="6.5" fill="none" stroke="currentColor" strokeWidth="1.6" />
      <path d="M8 1.5a6.5 6.5 0 0 1 0 13Z" fill="currentColor" />
    </svg>
  );
}
