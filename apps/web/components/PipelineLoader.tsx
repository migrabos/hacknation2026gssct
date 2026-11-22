"use client";

import { useEffect, useState } from "react";

/**
 * Loading screen while /analyze runs: static description, one progress bar and elapsed time.
 * The API answers in a single response, so progress is paced by time: fast at first, then slowing
 * down and never reaching 100% on its own (it eases towards MAX_PCT) — the page moves on to the
 * report as soon as it arrives.
 */
const MAX_PCT = 92;
const TAU_MS = 7000; // ~50% after 5 s, ~80% after 15 s, ~90% after 30 s
const TICK_MS = 100;

export default function PipelineLoader({ plotLabel }: { plotLabel?: string }) {
  const [elapsedMs, setElapsedMs] = useState(0);

  useEffect(() => {
    const t0 = performance.now();
    const t = setInterval(() => setElapsedMs(performance.now() - t0), TICK_MS);
    return () => clearInterval(t);
  }, []);

  const pct = MAX_PCT * (1 - Math.exp(-elapsedMs / TAU_MS));
  const seconds = Math.floor(elapsedMs / 1000);

  return (
    <section className="panel pipeline" aria-busy="true">
      <h2>Przygotowujemy raport</h2>
      <p className="muted" style={{ marginBottom: 0 }}>
        {plotLabel ? <>Działka {plotLabel}. </> : null}
        Zwykle trwa to kilkanaście sekund.
      </p>

      <div
        className="progress"
        role="progressbar"
        aria-label="Postęp przygotowania raportu"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={Math.round(pct)}
      >
        <div style={{ width: `${pct}%` }} />
      </div>

      <p className="muted small pipe-meta">
        {seconds} s
        {seconds > 30 && " — niektóre serwisy z danymi odpowiadają dziś wolniej, prosimy o cierpliwość"}
      </p>
    </section>
  );
}
