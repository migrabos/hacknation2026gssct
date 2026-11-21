"use client";

import { useEffect, useState } from "react";
import { CheckIcon } from "./Icons";

/**
 * Shows the contest-order pipeline while /analyze runs.
 * The API answers in one response, so progress is paced by time;
 * the last step only completes when the report actually arrives.
 */
const DEFAULT_STEPS = [
  { title: "Pobieramy dane o działce", sub: "granice, pogoda z 10 lat, gleba, ukształtowanie terenu" },
  { title: "Ocena wilgotności", sub: "jak sucho jest teraz i jak często bywa sucho" },
  { title: "Przyczyny", sub: "brak deszczu, gleba, spływ wody, wymagania uprawy" },
  { title: "Retencja i agrotechnika", sub: "jak zatrzymać wodę na polu" },
  { title: "Nawadnianie", sub: "tylko jeśli naprawdę potrzebne" },
];
const STEP_MS = [2600, 1600, 1600, 1800];

/** Steps for the separate crop-fit report (POST /crop-fit). */
export const CROP_FIT_STEPS = [
  { title: "Pobieramy dane o działce", sub: "granice, pogoda z 10 lat, gleba, ukształtowanie terenu, ewidencja gruntów" },
  { title: "Warunki wodne działki", sub: "ile wody trzyma gleba i jak suche są tu lata" },
  { title: "Porównanie upraw", sub: "korzenie, wrażliwość na suszę, wymagania glebowe, spadek terenu" },
  { title: "Ranking", sub: "co tu najlepiej pasuje, a czego unikać" },
];

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
    const t = setTimeout(() => setActive((a) => a + 1), STEP_MS[active] ?? 1800);
    return () => clearTimeout(t);
  }, [active, STEPS.length]);

  useEffect(() => {
    const t = setInterval(() => setElapsed((s) => s + 1), 1000);
    return () => clearInterval(t);
  }, []);

  const pct = Math.round(((active + 0.5) / STEPS.length) * 100);

  return (
    <section className="panel pipeline" aria-live="polite" aria-busy="true">
      <h2>Przygotowujemy raport</h2>
      <p className="muted" style={{ marginBottom: 0 }}>
        {plotLabel ? <>Działka {plotLabel}. </> : null}
        Zwykle trwa to kilkanaście sekund.
      </p>
      <div className="progress" aria-hidden="true">
        <div style={{ width: `${pct}%` }} />
      </div>
      <ol>
        {STEPS.map((s, i) => {
          const state = i < active ? "done" : i === active ? "active" : "todo";
          return (
            <li key={s.title} data-state={state}>
              <span className="pipe-icon">
                {state === "done" ? <CheckIcon /> : state === "active" ? <span className="spinner" /> : null}
              </span>
              <span>
                {s.title}
                <span className="pipe-sub">{s.sub}</span>
              </span>
            </li>
          );
        })}
      </ol>
      <p className="muted small" style={{ margin: "12px 0 0" }}>
        Czas: {elapsed} s
        {elapsed > 30 && " — niektóre serwisy z danymi odpowiadają dziś wolniej, prosimy o cierpliwość."}
      </p>
    </section>
  );
}
