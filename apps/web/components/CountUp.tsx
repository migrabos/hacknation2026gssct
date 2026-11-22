"use client";

import { useEffect, useState } from "react";
import { formatNumber } from "@/lib/labels";

/**
 * A number that runs up to its value once when the report opens (~0.7 s, ease-out).
 * Screen readers get the final value right away; with reduced motion it is static.
 * Purely visual — the value itself always comes from the report.
 */
export default function CountUp({
  value,
  digits = 0,
  durationMs = 700,
  delayMs = 150,
}: {
  value: number;
  digits?: number;
  durationMs?: number;
  delayMs?: number;
}) {
  const [shown, setShown] = useState(value);

  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      setShown(value);
      return;
    }
    let frame = 0;
    const start = performance.now() + delayMs;
    const tick = (now: number) => {
      const t = Math.min(1, Math.max(0, (now - start) / durationMs));
      setShown(value * (1 - Math.pow(1 - t, 3))); // ease-out cubic
      if (t < 1) frame = requestAnimationFrame(tick);
    };
    setShown(0);
    frame = requestAnimationFrame(tick);
    // printing mid-animation must still show the real value
    const onPrint = () => {
      cancelAnimationFrame(frame);
      setShown(value);
    };
    window.addEventListener("beforeprint", onPrint);
    return () => {
      cancelAnimationFrame(frame);
      window.removeEventListener("beforeprint", onPrint);
    };
  }, [value, durationMs, delayMs]);

  return (
    <>
      <span aria-hidden="true" className="count-up">
        {formatNumber(shown, digits)}
      </span>
      <span className="visually-hidden">{formatNumber(value, digits)}</span>
    </>
  );
}
