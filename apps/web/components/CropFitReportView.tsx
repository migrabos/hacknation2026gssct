"use client";

/**
 * Separate report: which crops cope best with the water and soil of this plot (POST /crop-fit).
 * Same look as the water report (ReportView) — same header, cards, evidence and sources blocks.
 */
import Link from "next/link";
import { useEffect, useMemo } from "react";
import type { CropFitItem, CropFitReport, Evidence, Source } from "@/lib/types";
import { SOURCE_MODE_LABEL, SOURCE_STATUS_LABEL, formatDate, formatDateTime, formatNumber } from "@/lib/labels";
import Map from "./Map";
import Notice from "./Notice";
import { ConfidenceBadge, EvidenceDetails } from "./ReportView";
import { PrintIcon } from "./Icons";

type EvMap = globalThis.Map<string, Evidence>;
type SrcMap = globalThis.Map<string, Source>;

const FIT_LABEL: Record<CropFitItem["fit"], string> = {
  good: "dobrze pasuje",
  medium: "średnio pasuje",
  poor: "słabo pasuje",
};
const FIT_TONE: Record<CropFitItem["fit"], string> = {
  good: "var(--c-m-normal)",
  medium: "var(--c-m-dry)",
  poor: "var(--c-m-very-dry)",
};

export default function CropFitReportView({ report }: { report: CropFitReport }) {
  const evidence: EvMap = useMemo(() => new globalThis.Map(report.evidence.map((e) => [e.id, e])), [report.evidence]);
  const sources: SrcMap = useMemo(() => new globalThis.Map(report.sources.map((s) => [s.id, s])), [report.sources]);

  useEffect(() => {
    const open = () => document.querySelectorAll<HTMLDetailsElement>("details.evidence, details.sources-more").forEach((d) => (d.open = true));
    window.addEventListener("beforeprint", open);
    return () => window.removeEventListener("beforeprint", open);
  }, []);

  const { plot, cropFit: fit } = report;
  const landUse = plot.landUse;
  const warnings = report.limitations.filter((l) => l.startsWith("UWAGA:"));
  const place = [plot.commune, plot.county && `pow. ${plot.county}`, plot.voivodeship && `woj. ${plot.voivodeship}`]
    .filter(Boolean)
    .join(", ");
  const ranking = fit?.ranking ?? [];
  const best = ranking.slice(0, 3);
  const poor = ranking.filter((i) => i.fit === "poor");
  const avoid = (poor.length > 0 ? poor : ranking.slice(-2)).slice(-3).reverse();

  return (
    <article className="report container">
      <header className="report-head">
        <div>
          <p className="muted small no-print" style={{ margin: "0 0 6px" }}>
            <Link href="/analizuj">‹ Nowa analiza</Link>
          </p>
          <p className="print-only muted small" style={{ margin: 0 }}>
            Retencja — dobór uprawy
          </p>
          <h1>Jaka uprawa najlepiej poradzi sobie z wodą na tej działce</h1>
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

      {report.status === "partial" && (
        <Notice tone="warn" title="Raport niepełny — części danych nie udało się pobrać" role="status">
          <p>
            Brakuje: {report.missingData.map((m) => m.what.charAt(0).toLowerCase() + m.what.slice(1)).join(", ")}. Porównanie
            opieramy na pozostałych danych.{" "}
            <a href="#braki" className="no-print">
              Zobacz, co to zmienia
            </a>
          </p>
        </Notice>
      )}
      {warnings.length > 0 && (
        <Notice tone="warn" title="Sprawdź rodzaj użytku" role="status">
          {warnings.map((w, i) => (
            <p key={i}>{w.replace(/^UWAGA:\s*/, "")}</p>
          ))}
        </Notice>
      )}

      <dl className="meta-grid">
        {landUse?.labelPl && (
          <div>
            <dt>Rodzaj użytku</dt>
            <dd>
              {landUse.labelPl.charAt(0).toUpperCase() + landUse.labelPl.slice(1)}
              {landUse.soilClasses && landUse.soilClasses.length > 0 && <>, klasa gleby {landUse.soilClasses.join(", ")}</>}
              <span className="muted small" style={{ display: "block" }}>
                z ewidencji gruntów (EGiB)
              </span>
            </dd>
          </div>
        )}
        <div>
          <dt>Warunki z lat</dt>
          <dd>10 lat do {formatDate(report.analysisDate)}</dd>
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
        {fit && (
          <div className="toc">
            <strong>Na czym opieramy porównanie</strong>
            <ul className="small" style={{ paddingLeft: "1.2em", margin: "8px 0" }}>
              {fit.basis.map((b) => (
                <li key={b}>{b}</li>
              ))}
            </ul>
            <ConfidenceBadge c={fit.confidence} />
          </div>
        )}
      </div>

      {fit ? (
        <>
          <section className="r-section" id="najlepsze" aria-labelledby="najlepsze-h">
            <div className="r-section-head">
              <span className="r-section-num">1</span>
              <div>
                <h2 id="najlepsze-h">Najlepiej pasują</h2>
                <p className="muted">
                  Uprawy, które przy tej glebie, klimacie i ukształtowaniu terenu najlepiej zniosą niedobory wody.
                </p>
              </div>
            </div>
            <ul className="cause-list">
              {best.map((i) => (
                <FitCard key={i.id} item={i} evidence={evidence} sources={sources} />
              ))}
            </ul>
          </section>

          <section className="r-section" id="unikac" aria-labelledby="unikac-h">
            <div className="r-section-head">
              <span className="r-section-num">2</span>
              <div>
                <h2 id="unikac-h">Tu raczej nie</h2>
                <p className="muted">Uprawy, które na tej działce najbardziej ucierpią przy braku wody.</p>
              </div>
            </div>
            <ul className="cause-list">
              {avoid.map((i) => (
                <FitCard key={i.id} item={i} evidence={evidence} sources={sources} />
              ))}
            </ul>
          </section>

          <section className="r-section" id="wszystkie" aria-labelledby="wszystkie-h">
            <div className="r-section-head">
              <span className="r-section-num">3</span>
              <div>
                <h2 id="wszystkie-h">Wszystkie porównane uprawy</h2>
                <p className="muted">Od najlepiej do najsłabiej dopasowanej. Punkty 0–100 to jawna heurystyka.</p>
              </div>
            </div>
            <div className="table-wrap">
              <table className="data">
                <thead>
                  <tr>
                    <th scope="col">Uprawa</th>
                    <th scope="col">Dopasowanie</th>
                    <th scope="col">Punkty</th>
                  </tr>
                </thead>
                <tbody>
                  {ranking.map((i) => (
                    <tr key={i.id}>
                      <td>{i.name}</td>
                      <td>{FIT_LABEL[i.fit]}</td>
                      <td>{i.score0to100}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="small muted">{fit.notConsidered}</p>
          </section>
        </>
      ) : (
        <section className="r-section">
          <p>Dla tej działki nie porównujemy upraw — szczegóły w ostrzeżeniu powyżej.</p>
        </section>
      )}

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

            <h4>Ograniczenia</h4>
            <ul className="small">
              {report.limitations
                .filter((l) => !l.startsWith("UWAGA:"))
                .map((l, i) => (
                  <li key={i}>{l}</li>
                ))}
            </ul>
            <p className="small muted">
              Ranking wylicza deterministyczny silnik reguł — te same dane zawsze dają ten sam wynik. Identyfikator
              raportu: {report.reportId}
            </p>
          </div>
        </details>
      </section>
    </article>
  );
}

function FitCard({ item, evidence, sources }: { item: CropFitItem; evidence: EvMap; sources: SrcMap }) {
  return (
    <li className="cause" style={{ borderLeftColor: FIT_TONE[item.fit] }}>
      <div className="cause-head">
        <h3>{item.name}</h3>
        <span className="badge">{FIT_LABEL[item.fit]}</span>
      </div>
      {item.pros.length > 0 && (
        <ul className="fit-points">
          {item.pros.map((p, k) => (
            <li key={k}>{p}</li>
          ))}
        </ul>
      )}
      {item.cons.length > 0 && (
        <ul className="fit-points fit-cons">
          {item.cons.map((c, k) => (
            <li key={k}>{c}</li>
          ))}
        </ul>
      )}
      <EvidenceDetails refs={item.evidenceRefs} evidence={evidence} sources={sources} />
    </li>
  );
}
