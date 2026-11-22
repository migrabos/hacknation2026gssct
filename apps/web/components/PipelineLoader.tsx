"use client";

import { useEffect, useState } from "react";
import { CheckIcon } from "./Icons";

/**
 * Shows the contest-order pipeline while /analyze runs.
 * The API answers in one response, so progress is paced by time;
 * the last step only completes when the report actually arrives.
 */
const DEFAULT_STEPS = [
  {
    title: "Pobieramy dane o działce",
    sub: "granice z GUGiK · pogoda z 10 lat · gleba · ukształtowanie terenu",
  },
  {
    title: "Analiza zdjęć satelitarnych",
    sub: "Sentinel-2 · kondycja roślinności · wilgotność",
  },
  {
    title: "Ocena wilgotności",
    sub: "jak sucho jest teraz i jak często bywa sucho",
  },
  {
    title: "Przyczyny i rekomendacje",
    sub: "brak deszczu · gleba · spływ wody · retencja · agrotechnika",
  },
  {
    title: "Generowanie raportu",
    sub: "tylko jeśli naprawdę potrzebne — nawadnianie na końcu",
  },
];

const STEP_MS = [3000, 2000, 1800, 2000];

export default function PipelineLoader({
  plotLabel,
  steps: STEPS = DEFAULT_STEPS,
}: {
  plotLabel?: string;
  steps?: { title: string; sub: string }[];
}) {
  const [active, setActive] = useState(0);
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    if (active >= STEPS.length - 1) return;
    const t = setTimeout(() => setActive((a) => a + 1), STEP_MS[active] ?? 2000);
    return () => clearTimeout(t);
  }, [active, STEPS.length]);

  useEffect(() => {
    const t = setInterval(() => setElapsed((s) => s + 1), 1000);
    return () => clearInterval(t);
  }, []);

  const pct = Math.round(((active + 0.5) / STEPS.length) * 100);

  return (
    <section className="panel pipeline" aria-live="polite" aria-busy="true">
      <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 16, flexWrap: "wrap" }}>
        <div>
          <h2 style={{ marginBottom: 6 }}>Przygotowujemy Twój raport</h2>
          <p className="muted" style={{ marginBottom: 0, fontSize: "0.9375rem" }}>
            {plotLabel ? (
              <>
                <strong style={{ color: "var(--c-text)" }}>Działka {plotLabel}</strong>
                {" · "}
              </>
            ) : null}
            Zwykle trwa to kilkanaście sekund
          </p>
        </div>
        <div style={{
          display: "flex",
          alignItems: "center",
          gap: 10,
          padding: "8px 16px",
          borderRadius: "var(--radius-pill)",
          border: "1px solid var(--c-border)",
          background: "var(--c-bg-subtle)",
          fontSize: "0.875rem",
          color: "var(--c-text-muted)",
          whiteSpace: "nowrap",
        }}>
          <span className="spinner" style={{ width: 14, height: 14, borderWidth: 2 }} />
          <span style={{ fontVariantNumeric: "tabular-nums" }}>{elapsed} s</span>
        </div>
      </div>

      <div className="progress" aria-hidden="true" style={{ marginTop: 20 }}>
        <div style={{ width: `${pct}%` }} />
      </div>
      <p style={{ margin: "6px 0 0", fontSize: "0.8125rem", color: "var(--c-text-muted)", textAlign: "right" }}>
        {pct}%
        {elapsed > 30 && " — niektóre serwisy odpowiadają dziś wolniej, prosimy o cierpliwość"}
      </p>

      <ol aria-label="Postęp analizy">
        {STEPS.map((s, i) => {
          const state = i < active ? "done" : i === active ? "active" : "todo";
          return (
            <li key={s.title} data-state={state}>
              <span className="pipe-icon" aria-hidden="true">
                {state === "done" ? (
                  <CheckIcon size={14} />
                ) : state === "active" ? (
                  <span className="spinner" style={{ width: 14, height: 14, borderWidth: 2 }} />
                ) : null}
              </span>
              <span>
                {s.title}
                <span className="pipe-sub">{s.sub}</span>
              </span>
            </li>
          );
        })}
      </ol>
    </section>
  );
}
