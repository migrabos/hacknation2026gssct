"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import type { Confidence, Evidence, NarrativeSectionId, Recommendation, Report, Source } from "@/lib/types";
import {
  CONFIDENCE_LABEL,
  COST_LABEL,
  MOISTURE_SCALE,
  RISK_SCALE,
  SOURCE_MODE_LABEL,
  SOURCE_STATUS_LABEL,
  countyLabel,
  formatDate,
  formatDateTime,
  formatNumber,
  splitPlotId,
} from "@/lib/labels";
import { clearForm } from "@/lib/report-store";
import Map from "./Map";
import Notice from "./Notice";
import RainChart from "./RainChart";
import CountUp from "./CountUp";
import RiskChart from "./RiskChart";
import { PrintIcon } from "./Icons";
import { sourcePage, weatherProviders } from "@/lib/source-page";

export function SourceLink({ source }: { source: Source }) {
  if (source.id === "open_meteo") {
    const providers = weatherProviders(source);
    if (!providers.length) return <>Brak informacji o dostawcy</>;
    return <>{providers.map(({ name, page }) => (
      <div key={name}>{page ? <a href={page} target="_blank" rel="noreferrer">{name}</a> : name}</div>
    ))}</>;
  }
  const page = sourcePage(source);
  const label = source.provider ?? source.name;
  return page ? <a href={page} target="_blank" rel="noreferrer">{label}</a> : <>{label}</>;
}

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
    const open = () => document.querySelectorAll<HTMLDetailsElement>("details.evidence, details.sources-more, details.rain").forEach((d) => (d.open = true));
    window.addEventListener("beforeprint", open);
    return () => window.removeEventListener("beforeprint", open);
  }, []);

  const { plot, moistureAssessment: ma, recommendations: rec } = report;
  const failedSources = report.sources.filter((s) => s.status !== "ok");
  const irrigation = rec.irrigation ?? [];
  const landUse = plot.landUse;
  const landUseWarnings = report.limitations.filter((l) => l.startsWith("UWAGA:"));
  const { nr, obreb } = splitPlotId(plot.plotId);
  const place = [
    obreb && `obręb ${obreb}`,
    plot.commune && `gm. ${plot.commune}`,
    plot.county && countyLabel(plot.county),
    plot.voivodeship && `woj. ${plot.voivodeship}`,
  ]
    .filter(Boolean)
    .join(", ");

  return (
    <article className="report container">
      {/* ---------- Header ---------- */}
      <header className="report-head">
        <div>
          <p className="muted small no-print" style={{ margin: "0 0 6px" }}>
            <Link href="/analizuj">‹ Wróć do formularza</Link>
          </p>
          <p className="print-only muted small" style={{ margin: 0 }}>
            Retencja — raport wodny
          </p>
          <h1>Raport wodny — działka {nr}</h1>
          <p className="muted" style={{ margin: 0, overflowWrap: "anywhere" }}>
            {place}
            {place && <br />}
            <span className="small">Identyfikator: {plot.plotId}</span>
          </p>
        </div>
        <div className="report-actions no-print">
          <button type="button" className="btn" onClick={() => window.print()}>
            <PrintIcon /> Drukuj / zapisz PDF
          </button>
          <Link href="/analizuj" className="btn btn-secondary">
            Zmień uprawę lub datę
          </Link>
          <Link href="/analizuj" className="btn btn-secondary" onClick={clearForm}>
            Sprawdź inną działkę
          </Link>
        </div>
      </header>

      <SectionTabs />

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
          <dd>
            <CountUp value={plot.areaHa} digits={2} /> ha
          </dd>
        </div>
        {plot.terrain?.slopePct != null && (
          <div>
            <dt>Spadek terenu według modelu</dt>
            <dd>
              <CountUp value={plot.terrain.slopePct} digits={2} />%
              {sources.get("dem")?.dataPeriod && <> · {sources.get("dem")?.dataPeriod}</>}
            </dd>
          </div>
        )}
        <div>
          <dt>Raport utworzono</dt>
          <dd>{formatDateTime(report.generatedAt)}</dd>
        </div>
      </dl>

      <QuickSummary report={report} />

      <div className="report-overview">
        <Map plot={plot} height={300} />
        <nav className="toc no-print" id="spis" aria-label="Spis treści raportu">
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
            {ma.susceptibility.level !== "insufficient_data" && <Scale
              steps={RISK_SCALE}
              active={ma.susceptibility.level}
              tone={RISK_TONE[ma.susceptibility.level]}
              label="Podatność na suszę"
            />}
            <p>{ma.susceptibility.summary}</p>
            <ConfidenceBadge c={ma.susceptibility.confidence} />
            <EvidenceDetails refs={ma.susceptibility.evidenceRefs} evidence={evidence} sources={sources} />
          </div>
        </div>
        <RiskChart risk={ma.susceptibility.riskWindow} />
        <RainChart months={report.precipMonthly ?? []} analysisDate={report.analysisDate} source={sources.get("open_meteo")} />
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
        {report.sources.length > 0 && (
          <div className="source-coverage">
            <strong>Źródła z kompletem danych</strong>{" "}
            <span>{report.sources.length - failedSources.length} z {report.sources.length}</span>
            <div className="source-coverage-bar" aria-hidden="true">
              {report.sources.map((source) => (
                <span key={source.id} data-status={source.status} />
              ))}
            </div>
            {failedSources.length > 0 && (
              <small>
                Częściowe dane: {failedSources.filter((s) => s.status === "partial").length}
                {" · "}Brak danych: {failedSources.filter((s) => s.status === "failed").length}
              </small>
            )}
          </div>
        )}
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
              <table className="data stack" role="table">
                <thead role="rowgroup">
                  <tr role="row">
                    <th scope="col" role="columnheader">Dane</th>
                    <th scope="col" role="columnheader">Źródło</th>
                    <th scope="col" role="columnheader">Stan</th>
                    <th scope="col" role="columnheader">Okres / pobrano</th>
                  </tr>
                </thead>
                <tbody role="rowgroup">
                  {report.sources.map((s) => (
                    <tr key={s.id} role="row">
                      <td role="cell" data-label="Dane">
                        <strong>{s.name}</strong>
                      </td>
                      <td role="cell" data-label="Źródło">
                        <SourceLink source={s} />
                        {s.license && <div className="small muted">Licencja: {s.license}</div>}
                      </td>
                      <td role="cell" data-label="Stan">
                        <span className={`badge ${s.status === "ok" ? "badge-ok" : "badge-fail"}`}>
                          {s.mode === "static" && s.status === "ok" ? "wbudowane" : SOURCE_STATUS_LABEL[s.status]}
                        </span>
                        {s.status === "ok" && s.mode !== "static" && (
                          <div className="small muted">{SOURCE_MODE_LABEL[s.mode]}</div>
                        )}
                        {s.error && <div className="small muted">{s.error}</div>}
                      </td>
                      <td className="small" role="cell" data-label="Okres / pobrano">
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
                Opisy słowne w raporcie powstały automatycznie z szablonu, wyłącznie na podstawie
                powyższych danych. Oceny i zalecenia wylicza deterministyczny silnik reguł.
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

const TABS = [...SECTIONS.map((s, i) => ({ id: s.id, label: `${i + 1}. ${s.title}` })), { id: "zrodla", label: "Źródła" }];

/**
 * Phone-only sticky strip with the report sections — the report is ~8 screens long on a phone and the
 * table of contents sits far up the page. The section in view is marked with aria-current.
 */
function SectionTabs() {
  const [current, setCurrent] = useState<string | null>(null);

  useEffect(() => {
    const els = TABS.map((t) => document.getElementById(t.id)).filter((e): e is HTMLElement => Boolean(e));
    if (!("IntersectionObserver" in window) || els.length === 0) return;
    // a section counts as "current" while it crosses a line just under the strip
    const obs = new IntersectionObserver(
      (entries) => {
        for (const e of entries) if (e.isIntersecting) setCurrent(e.target.id);
      },
      { rootMargin: "-70px 0px -70% 0px" },
    );
    els.forEach((el) => obs.observe(el));
    return () => obs.disconnect();
  }, []);

  // keep the active tab visible inside the horizontally scrolling strip
  useEffect(() => {
    if (!current) return;
    document
      .querySelector<HTMLElement>(`.section-tabs a[href="#${current}"]`)
      ?.scrollIntoView({ block: "nearest", inline: "nearest" });
  }, [current]);

  return (
    <nav className="section-tabs no-print" aria-label="Sekcje raportu">
      <a href="#spis" aria-label="Do góry — spis treści">
        ↑
      </a>
      {TABS.map((t) => (
        <a key={t.id} href={`#${t.id}`} aria-current={current === t.id ? "location" : undefined}>
          {t.label}
        </a>
      ))}
    </nav>
  );
}

/** "In 5 seconds" box: restates structured fields only (headlines, top actions) – no new numbers. */
function QuickSummary({ report }: { report: Report }) {
  const { moistureAssessment: ma, recommendations: rec } = report;
  const top = [
    ...[...rec.retention].sort((a, b) => a.priority - b.priority).slice(0, 2),
    ...[...rec.agrotech].sort((a, b) => a.priority - b.priority).slice(0, 1),
    ...(rec.irrigation ?? []).slice(0, 1),
  ];
  return (
    <section className="quick-summary" aria-label="Najważniejsze w skrócie">
      <div className="quick-summary-grid">
        <div>
          <div className="assess-kicker">Teraz</div>
          <strong>{ma.current.headline}</strong>
        </div>
        <div>
          <div className="assess-kicker">Przez ostatnie lata</div>
          <strong>{ma.susceptibility.headline}</strong>
        </div>
        {ma.susceptibility.riskWindow?.peakLabel && (
          <div>
            <div className="assess-kicker">Najczęściej brakuje wody</div>
            <strong>{ma.susceptibility.riskWindow.peakLabel}</strong>
            {ma.susceptibility.riskWindow.yearsHit != null && ma.susceptibility.riskWindow.yearsTotal != null && (
              <span className="muted">
                {" "}
                · w <CountUp value={ma.susceptibility.riskWindow.yearsHit} delayMs={350} /> z{" "}
                {ma.susceptibility.riskWindow.yearsTotal} lat
              </span>
            )}
          </div>
        )}
      </div>
      {top.length > 0 ? (
        <>
          <div className="assess-kicker" style={{ marginTop: 14 }}>Co zrobić najpierw</div>
          <ol className="quick-summary-actions">
            {top.map((r) => (
              <li key={r.actionId}>
                <a
                  href={`#zalecenie-${r.actionId}`}
                  onClick={(event) => {
                    const card = document.getElementById(event.currentTarget.hash.slice(1));
                    const details = card?.querySelector<HTMLDetailsElement>("details.evidence");
                    if (details) details.open = true;
                  }}
                >
                  {r.title}
                </a>
                <span className="muted">
                  {" "}
                  {r.costLevel ? `· ${COST_LABEL[r.costLevel]}` : ""}
                  {r.timeframe ? ` · ${r.timeframe}` : ""}
                </span>
              </li>
            ))}
          </ol>
        </>
      ) : (
        <p style={{ margin: "10px 0 0" }}>
          Raport nie zawiera zaleceń dla tej działki.
          {report.missingData.length > 0 && <> <a href="#braki">Sprawdź, jakich danych zabrakło.</a></>}
        </p>
      )}
    </section>
  );
}

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

export function ConfidenceBadge({ c }: { c: Confidence }) {
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
        <li key={r.actionId} id={`zalecenie-${r.actionId}`} className="rec" tabIndex={-1}>
          <span className="rec-prio" aria-label={`Kolejność: ${i + 1}`}>
            {i + 1}
          </span>
          <div>
            <div className="rec-head">
              <h3>{r.title}</h3>
            </div>
            <div className="rec-tags">
              {r.timeframe && <span className="badge">kiedy: {r.timeframe}</span>}
              {r.costLevel && <span className="badge">{COST_LABEL[r.costLevel]}</span>}
            </div>
            <p style={{ marginBottom: 0 }}>{r.description}</p>
            <p className="why">{r.why}</p>
            <EvidenceDetails refs={r.evidenceRefs} evidence={evidence} sources={sources} />
          </div>
        </li>
      ))}
    </ol>
  );
}

export function EvidenceDetails({
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
