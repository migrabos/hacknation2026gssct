"use client";

import Link from "next/link";
import { useEffect, useMemo } from "react";
import type { Confidence, Evidence, NarrativeSectionId, Recommendation, Report, Source } from "@/lib/types";
import {
  CONFIDENCE_LABEL,
  MOISTURE_SCALE,
  RISK_SCALE,
  SOURCE_MODE_LABEL,
  SOURCE_STATUS_LABEL,
  formatDate,
  formatDateTime,
  formatNumber,
} from "@/lib/labels";
import Map from "./Map";
import Notice from "./Notice";
import { PrintIcon } from "./Icons";

const MOISTURE_TONE: Record<string, string> = {
  very_dry: "var(--c-m-very-dry)",
  dry: "var(--c-m-dry)",
  normal: "var(--c-m-normal)",
  wet: "var(--c-m-wet)",
};
const RISK_TONE: Record<string, string> = {
  low: "var(--c-m-normal)",
  medium: "var(--c-m-dry)",
  high: "var(--c-m-very-dry)",
};

const SECTIONS = [
  { id: "ocena", title: "Ocena wilgotności" },
  { id: "przyczyny", title: "Możliwe przyczyny" },
  { id: "retencja", title: "Zatrzymaj wodę na polu" },
  { id: "agrotechnika", title: "Zmiany w uprawie gleby" },
  { id: "nawadnianie", title: "Nawadnianie" },
] as const;

export default function ReportView({ report }: { report: Report }) {
  const evidence = useMemo(() => new globalThis.Map(report.evidence.map((e) => [e.id, e])), [report.evidence]);
  const sources = useMemo(() => new globalThis.Map(report.sources.map((s) => [s.id, s])), [report.sources]);
  const narrative = useMemo(() => {
    const m = new globalThis.Map<NarrativeSectionId, string>();
    report.narrative?.sections.forEach((s) => m.set(s.id, s.text));
    return m;
  }, [report.narrative]);

  // Open every "Na jakiej podstawie?" block when printing.
  useEffect(() => {
    const open = () => document.querySelectorAll<HTMLDetailsElement>("details.evidence, details.sources-more").forEach((d) => (d.open = true));
    window.addEventListener("beforeprint", open);
    return () => window.removeEventListener("beforeprint", open);
  }, []);

  const { plot, moistureAssessment: ma, recommendations: rec } = report;
  const failedSources = report.sources.filter((s) => s.status !== "ok");
  const irrigation = rec.irrigation ?? [];
  const landUse = plot.landUse;
  const landUseWarnings = report.limitations.filter((l) => l.startsWith("UWAGA:"));
  const place = [plot.commune, plot.county && `pow. ${plot.county}`, plot.voivodeship && `woj. ${plot.voivodeship}`]
    .filter(Boolean)
    .join(", ");

  // #region agent log
  useEffect(() => {
    const failedOrPartial = report.sources.filter((s) => s.status !== "ok").map((s) => s.id);
    fetch("http://127.0.0.1:7469/ingest/78fee146-1b5b-4d90-8bb6-2bc46ba8b822", {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-Debug-Session-Id": "68e619" },
      body: JSON.stringify({
        sessionId: "68e619",
        runId: "pre-fix",
        hypothesisId: "H1",
        location: "ReportView.tsx:mount",
        message: "report sources + plot for UI",
        data: {
          reportStatus: report.status,
          meta: report.meta ?? null,
          sources: report.sources.map((s) => ({ id: s.id, status: s.status, mode: s.mode, error: s.error ?? null })),
          failedOrPartial,
          plotId: plot.plotId,
          centroid: plot.centroid,
          bbox: plot.bbox,
          geomType: plot.geometry?.type,
        },
        timestamp: Date.now(),
      }),
    }).catch(() => {});
  }, [report]);
  // #endregion

  return (
    <article className="report container">
      {/* ---------- Header ---------- */}
      <header className="report-head">
        <div>
          <p className="muted small no-print" style={{ margin: "0 0 6px" }}>
            <Link href="/analizuj">‹ Nowa analiza</Link>
          </p>
          <p className="print-only muted small" style={{ margin: 0 }}>
            Retencja — raport wodny
          </p>
          <h1>Raport wodny dla działki</h1>
          <p className="muted" style={{ margin: 0, overflowWrap: "anywhere" }}>
            {plot.plotId}
            {place && <> · {place}</>}
          </p>
        </div>
        <div className="report-actions no-print">
          <button type="button" className="btn" onClick={() => window.print()}>
            <PrintIcon /> Drukuj / zapisz PDF
          </button>
          <Link href="/analizuj" className="btn btn-secondary">
            Sprawdź inną działkę
          </Link>
        </div>
      </header>

      {report.meta?.adapters === "mock" && (
        <Notice tone="warn" title="Tryb demonstracyjny — dane przykładowe" role="status">
          <p>Serwer działa na danych przykładowych (DEMO), nie na prawdziwych pomiarach dla tej działki.</p>
        </Notice>
      )}

      {report.status === "partial" && (
        <Notice tone="warn" title="Raport niepełny — części danych nie udało się pobrać" role="status">
          <p>
            Brakuje: {report.missingData.map((m) => m.what.charAt(0).toLowerCase() + m.what.slice(1)).join(", ")}. Wnioski opieramy na pozostałych
            danych.{" "}
            <a href="#braki" className="no-print">
              Zobacz, czego brakuje i co to zmienia
            </a>
          </p>
        </Notice>
      )}

      {landUseWarnings.length > 0 && (
        <Notice tone="warn" title="Sprawdź rodzaj użytku" role="status">
          {landUseWarnings.map((w, i) => (
            <p key={i}>{w.replace(/^UWAGA:\s*/, "")}</p>
          ))}
        </Notice>
      )}

      <dl className="meta-grid">
        <div>
          <dt>Uprawa</dt>
          <dd>{report.crop.name}</dd>
        </div>
        {landUse && (
          <div>
            <dt>Rodzaj użytku</dt>
            {landUse.labelPl ? (
              <dd>
                {landUse.labelPl.charAt(0).toUpperCase() + landUse.labelPl.slice(1)}
                {landUse.soilClasses && landUse.soilClasses.length > 0 && <>, klasa gleby {landUse.soilClasses.join(", ")}</>}
                <span className="muted small" style={{ display: "block" }}>
                  z ewidencji gruntów (EGiB){landUse.codes && landUse.codes.length > 0 && <>: {landUse.codes.join(", ")}</>}
                </span>
              </dd>
            ) : (
              <dd>
                Brak danych
                <span className="muted small" style={{ display: "block" }}>
                  {landUse.notes?.[0] ?? "ewidencja gruntów nie podaje użytku dla tej działki"}
                </span>
              </dd>
            )}
          </div>
        )}
        <div>
          <dt>Ocena na dzień</dt>
          <dd>{formatDate(report.analysisDate)}</dd>
        </div>
        <div>
          <dt>Powierzchnia</dt>
          <dd>{formatNumber(plot.areaHa, 2)} ha</dd>
        </div>
        <div>
          <dt>Raport utworzono</dt>
          <dd>{formatDateTime(report.generatedAt)}</dd>
        </div>
      </dl>

      <div className="report-overview">
        <Map plot={plot} height={300} />
        <nav className="toc no-print" aria-label="Spis treści raportu">
          <strong>W tym raporcie</strong>
          <ol>
            {SECTIONS.map((s) => (
              <li key={s.id}>
                <a href={`#${s.id}`}>{s.title}</a>
              </li>
            ))}
            <li>
              <a href="#zrodla">Źródła danych i ograniczenia</a>
            </li>
          </ol>
        </nav>
      </div>

      {/* ---------- 1. Assessment ---------- */}
      <Section n={1} id="ocena" title="Ocena wilgotności" lead="Obecnie i w poprzednich latach">
        <div className="assess-grid">
          <div className="assess-card">
            <div className="assess-kicker">Teraz</div>
            <h3>{ma.current.headline}</h3>
            {ma.current.level !== "insufficient_data" && (
              <Scale
                steps={MOISTURE_SCALE}
                active={ma.current.level}
                tone={MOISTURE_TONE[ma.current.level]}
                label="Wilgotność teraz"
              />
            )}
            <p>{ma.current.summary}</p>
            <ConfidenceBadge c={ma.current.confidence} />
            <EvidenceDetails refs={ma.current.evidenceRefs} evidence={evidence} sources={sources} />
          </div>
          <div className="assess-card">
            <div className="assess-kicker">Przez ostatnie lata</div>
            <h3>{ma.susceptibility.headline}</h3>
            <Scale
              steps={RISK_SCALE}
              active={ma.susceptibility.level}
              tone={RISK_TONE[ma.susceptibility.level]}
              label="Podatność na suszę"
            />
            <p>{ma.susceptibility.summary}</p>
            <ConfidenceBadge c={ma.susceptibility.confidence} />
            <EvidenceDetails refs={ma.susceptibility.evidenceRefs} evidence={evidence} sources={sources} />
          </div>
        </div>
        <NarrativeNote text={narrative.get("assessment")} />
      </Section>

      {/* ---------- 2. Causes ---------- */}
      <Section n={2} id="przyczyny" title="Możliwe przyczyny" lead="Najważniejsze przyczyny, od najpewniejszych.">
        {report.causes.length === 0 ? (
          <p>Nie znaleźliśmy wyraźnych przyczyn niedoboru wody.</p>
        ) : (
          <ul className="cause-list">
            {report.causes.map((c) => (
              <li key={c.id} className="cause">
                <div className="cause-head">
                  <h3>{c.title}</h3>
                  <ConfidenceBadge c={c.confidence} />
                </div>
                <p style={{ marginBottom: 0 }}>{c.explanation}</p>
                <EvidenceDetails refs={c.evidenceRefs} evidence={evidence} sources={sources} />
              </li>
            ))}
          </ul>
        )}
        <NarrativeNote text={narrative.get("causes")} />
      </Section>

      {/* ---------- 3. Retention ---------- */}
      <Section
        n={3}
        id="retencja"
        title="Zatrzymaj wodę na polu"
        lead="Działania, które pomagają zatrzymać deszcz i roztopy na działce i w jej otoczeniu. Od tych najważniejszych."
      >
        <RecList items={rec.retention} evidence={evidence} sources={sources} />
        <NarrativeNote text={narrative.get("retention")} />
      </Section>

      {/* ---------- 4. Agrotech ---------- */}
      <Section
        n={4}
        id="agrotechnika"
        title="Zmiany w uprawie gleby"
        lead="Sposoby uprawy, dzięki którym gleba zatrzyma więcej wody."
      >
        <RecList items={rec.agrotech} evidence={evidence} sources={sources} />
        <NarrativeNote text={narrative.get("agrotech")} />
      </Section>

      {/* ---------- 5. Irrigation (optional, last) ---------- */}
      <Section
        n={5}
        id="nawadnianie"
        title="Nawadnianie"
        lead="Nawadnianie to ostateczność — najpierw warto zatrzymać wodę, która już spada na pole."
      >
        {irrigation.length > 0 ? (
          <RecList items={irrigation} evidence={evidence} sources={sources} />
        ) : (
          <div className="irrigation-note">
            <strong>{ma.current.level === "insufficient_data" ? "Potrzeba nawadniania jest nieznana." : "Nawadnianie nie jest teraz potrzebne."}</strong>
            <p style={{ margin: "6px 0 0" }}>
              {rec.irrigationNote ?? "Przy obecnych warunkach lepsze efekty dadzą działania z punktów 3 i 4."}
            </p>
          </div>
        )}
        <NarrativeNote text={narrative.get("irrigation")} />
      </Section>

      {/* ---------- Sources, gaps, limitations ---------- */}
      <section className="r-section sources-section" id="zrodla" aria-label="Źródła danych i ograniczenia">
        {report.missingData.length > 0 && (
          <div id="braki" style={{ marginBottom: 20, scrollMarginTop: 16 }}>
            <h3>Czego brakuje w tym raporcie</h3>
            <ul className="missing-list">
              {report.missingData.map((m) => (
                <li key={m.id}>
                  <strong>{m.what}</strong> — {m.reason}
                  <br />
                  <span className="small">
                    <strong>Co to zmienia:</strong> {m.impact}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        )}

        <details className="sources-more">
          <summary>Źródła danych i ograniczenia</summary>
          <div className="sources-body">
            <p className="muted small">Każda liczba w raporcie pochodzi z jednego z tych źródeł.</p>
            <div className="table-wrap" style={{ marginBottom: 20 }}>
              <table className="data">
                <thead>
                  <tr>
                    <th scope="col">Dane</th>
                    <th scope="col">Źródło</th>
                    <th scope="col">Stan</th>
                    <th scope="col">Okres / pobrano</th>
                  </tr>
                </thead>
                <tbody>
                  {report.sources.map((s) => (
                    <tr key={s.id}>
                      <td>
                        <strong>{s.name}</strong>
                      </td>
                      <td>
                        {s.url ? (
                          <a href={s.url} target="_blank" rel="noreferrer">
                            {s.provider ?? s.url}
                          </a>
                        ) : (
                          s.provider
                        )}
                        {s.license && <div className="small muted">Licencja: {s.license}</div>}
                      </td>
                      <td>
                        <span className={`badge ${s.status === "ok" ? "badge-ok" : "badge-fail"}`}>
                          {s.mode === "static" && s.status === "ok" ? "wbudowane" : SOURCE_STATUS_LABEL[s.status]}
                        </span>
                        {s.status === "ok" && s.mode !== "static" && (
                          <div className="small muted">{SOURCE_MODE_LABEL[s.mode]}</div>
                        )}
                        {s.error && <div className="small muted">{s.error}</div>}
                      </td>
                      <td className="small">
                        {s.dataPeriod && <div>{s.dataPeriod}</div>}
                        {s.fetchedAt && <div className="muted">pobrano {formatDateTime(s.fetchedAt)}</div>}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {failedSources.length === 0 && report.missingData.length === 0 && (
              <p className="small muted">Wszystkie źródła danych odpowiedziały poprawnie.</p>
            )}

            <h4>Ograniczenia</h4>
            <ul className="small">
              {report.limitations.map((l, i) => (
                <li key={i}>{l}</li>
              ))}
            </ul>

            {report.narrative && (
              <p className="small muted">
                Opisy słowne w raporcie{" "}
                {report.narrative.generatedBy === "llm"
                  ? "napisała sztuczna inteligencja wyłącznie na podstawie powyższych danych i sprawdziliśmy je automatycznie."
                  : "powstały automatycznie z szablonu, wyłącznie na podstawie powyższych danych."}{" "}
                Oceny i zalecenia wylicza deterministyczny silnik reguł.
              </p>
            )}
            <p className="small muted">Identyfikator raportu: {report.reportId}</p>
          </div>
        </details>
      </section>
    </article>
  );
}

// ---------------------------------------------------------------------------

function Section({
  n,
  id,
  title,
  lead,
  children,
}: {
  n: number;
  id: string;
  title: string;
  lead?: string;
  children: React.ReactNode;
}) {
  return (
    <section className="r-section" id={id} aria-labelledby={`${id}-h`}>
      <div className="r-section-head">
        <span className="r-section-num">{n}</span>
        <div>
          <h2 id={`${id}-h`}>{title}</h2>
          {lead && <p className="muted">{lead}</p>}
        </div>
      </div>
      {children}
    </section>
  );
}

function Scale<T extends string>({
  steps,
  active,
  tone,
  label,
}: {
  steps: { level: T; label: string }[];
  active: T;
  tone: string;
  label: string;
}) {
  const current = steps.find((s) => s.level === active)?.label;
  return (
    <div className="scale" role="img" aria-label={`${label}: ${current}`} style={{ ["--tone" as string]: tone }}>
      {steps.map((s) => (
        <span key={s.level} className="scale-step" data-active={s.level === active} aria-hidden="true">
          {s.label}
        </span>
      ))}
    </div>
  );
}

function ConfidenceBadge({ c }: { c: Confidence }) {
  return <span className={`badge badge-conf-${c}`}>{CONFIDENCE_LABEL[c]}</span>;
}

function RecList({
  items,
  evidence,
  sources,
}: {
  items: Recommendation[];
  evidence: globalThis.Map<string, Evidence>;
  sources: globalThis.Map<string, Source>;
}) {
  if (items.length === 0) return <p className="muted">Brak zaleceń w tej grupie dla tej działki.</p>;
  const sorted = [...items].sort((a, b) => a.priority - b.priority);
  return (
    <ol className="rec-list">
      {sorted.map((r, i) => (
        <li key={r.actionId} className="rec">
          <span className="rec-prio" aria-label={`Kolejność: ${i + 1}`}>
            {i + 1}
          </span>
          <div>
            <div className="rec-head">
              <h3>{r.title}</h3>
            </div>
            {r.timeframe && (
              <div className="rec-tags">
                <span className="badge">kiedy: {r.timeframe}</span>
              </div>
            )}
            <p style={{ marginBottom: 0 }}>{r.description}</p>
            <p className="why">{r.why}</p>
            <EvidenceDetails refs={r.evidenceRefs} evidence={evidence} sources={sources} />
          </div>
        </li>
      ))}
    </ol>
  );
}

function EvidenceDetails({
  refs,
  evidence,
  sources,
}: {
  refs: string[];
  evidence: globalThis.Map<string, Evidence>;
  sources: globalThis.Map<string, Source>;
}) {
  const items = refs.map((id) => evidence.get(id)).filter((e): e is Evidence => Boolean(e));
  if (items.length === 0) return null;
  return (
    <details className="evidence">
      <summary>Na jakiej podstawie? ({items.length})</summary>
      <ul className="ev-list">
        {items.map((e) => (
          <li key={e.id}>
            <span>{e.label}</span>
            <span className="ev-value">
              {typeof e.value === "number" ? formatNumber(e.value) : e.value}
              {e.unit ? ` ${e.unit}` : ""}
            </span>
            <span className="ev-meta">
              {e.comparison && <>{e.comparison} · </>}
              źródło: {sources.get(e.sourceId)?.name ?? e.sourceId}
            </span>
          </li>
        ))}
      </ul>
    </details>
  );
}

/** Narrative strips [evidence_id] tags — the structured cards above carry the refs. */
function NarrativeNote({ text }: { text?: string }) {
  if (!text) return null;
  const clean = text.replace(/\s*\[[a-z0-9_]+\]/gi, "");
  return (
    <div className="narrative" style={{ marginTop: 20 }}>
      <p style={{ margin: 0 }}>{clean}</p>
    </div>
  );
}
