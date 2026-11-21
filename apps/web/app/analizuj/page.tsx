"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState, type FormEvent } from "react";
import Map from "@/components/Map";
import Notice from "@/components/Notice";
import PipelineLoader from "@/components/PipelineLoader";
import { API_MODE, ApiError, MOCK_NOT_FOUND_ID, api } from "@/lib/api";
import { ERROR_MESSAGE, formatNumber } from "@/lib/labels";
import { saveReport } from "@/lib/report-store";
import type { ApiErrorKind, Crop, Plot } from "@/lib/types";

function isoDay(d: Date): string {
  const tz = d.getTimezoneOffset() * 60_000;
  return new Date(d.getTime() - tz).toISOString().slice(0, 10);
}

function errorKind(err: unknown): ApiErrorKind {
  return err instanceof ApiError ? err.kind : "server";
}

export default function AnalyzePage() {
  const router = useRouter();

  const [plotQuery, setPlotQuery] = useState("");
  const [plot, setPlot] = useState<Plot | null>(null);
  const [plotBusy, setPlotBusy] = useState<"id" | "map" | null>(null);
  const [plotError, setPlotError] = useState<ApiErrorKind | null>(null);

  const [crops, setCrops] = useState<Crop[] | null>(null);
  const [cropsError, setCropsError] = useState(false);
  const [cropId, setCropId] = useState("");

  const [date, setDate] = useState("");
  const [dateMin, setDateMin] = useState("");
  const [dateMax, setDateMax] = useState("");

  const [apiDown, setApiDown] = useState(false);
  const [running, setRunning] = useState(false);
  const [analyzeError, setAnalyzeError] = useState<ApiErrorKind | null>(null);
  const [showErrors, setShowErrors] = useState(false);

  const loadCrops = useCallback(() => {
    setCropsError(false);
    api
      .getCrops()
      .then(setCrops)
      .catch(() => setCropsError(true));
  }, []);

  useEffect(() => {
    const today = new Date();
    const min = new Date(today);
    min.setFullYear(today.getFullYear() - 10);
    setDate(isoDay(today));
    setDateMax(isoDay(today));
    setDateMin(isoDay(min));
    loadCrops();
    if (API_MODE === "real") api.health().catch(() => setApiDown(true));
  }, [loadCrops]);

  async function findById(e?: { preventDefault(): void }) {
    e?.preventDefault();
    if (!plotQuery.trim()) {
      setPlotError("bad_request");
      return;
    }
    setPlotBusy("id");
    setPlotError(null);
    try {
      setPlot(await api.plotById(plotQuery));
    } catch (err) {
      setPlotError(errorKind(err));
    } finally {
      setPlotBusy(null);
    }
  }

  async function pickOnMap(lat: number, lng: number) {
    setPlotBusy("map");
    setPlotError(null);
    try {
      const p = await api.plotByPoint(lat, lng);
      setPlot(p);
      setPlotQuery(p.plotId);
    } catch (err) {
      setPlotError(errorKind(err));
    } finally {
      setPlotBusy(null);
    }
  }

  const dateValid = Boolean(date) && date >= dateMin && date <= dateMax;
  const canSubmit = Boolean(plot && cropId && dateValid);

  function submit(e: FormEvent) {
    e.preventDefault();
    void runAnalysis();
  }

  async function runAnalysis() {
    setShowErrors(true);
    if (!plot || !canSubmit) return;
    setAnalyzeError(null);
    setRunning(true);
    window.scrollTo({ top: 0 });
    try {
      const report = await api.analyze(
        { plotId: plot.plotId, lat: plot.centroid[1], lng: plot.centroid[0], cropId, analysisDate: date },
        plot,
      );
      saveReport(report);
      router.push("/raport");
    } catch (err) {
      setAnalyzeError(errorKind(err));
      setRunning(false);
    }
  }

  if (running) {
    return (
      <div className="container" style={{ paddingBottom: 24 }}>
        <PipelineLoader plotLabel={plot?.plotId} />
      </div>
    );
  }

  const plotErrMsg =
    plotError === "bad_request"
      ? { title: "Wpisz numer działki", text: "Na przykład 141201_1.0001.123 — znajdziesz go na wypisie z rejestru gruntów." }
      : plotError
        ? ERROR_MESSAGE[plotError]
        : null;

  return (
    <div className="container">
      <div className="page-head">
        <nav className="breadcrumbs" aria-label="Ścieżka">
          <Link href="/">Strona główna</Link> › Sprawdź działkę
        </nav>
        <h1>Sprawdź działkę</h1>
        <p className="muted" style={{ maxWidth: "60ch" }}>
          Wskaż działkę na mapie albo wpisz jej numer, wybierz uprawę i kliknij „Przygotuj raport”.
        </p>
      </div>

      {apiDown && (
        <Notice tone="error" title={ERROR_MESSAGE.api_down.title} role="alert">
          <p>{ERROR_MESSAGE.api_down.text}</p>
        </Notice>
      )}
      {analyzeError && (
        <Notice tone="error" title={ERROR_MESSAGE[analyzeError].title} role="alert">
          <p>{ERROR_MESSAGE[analyzeError].text}</p>
          <button type="button" className="btn btn-secondary" onClick={() => void runAnalysis()}>
            Spróbuj ponownie
          </button>
        </Notice>
      )}

      <div className="analyze-grid">
        <section aria-labelledby="map-h">
          <h2 id="map-h" className="visually-hidden">
            Mapa
          </h2>
          <Map plot={plot} onPick={pickOnMap} busy={plotBusy === "map"} height="min(70vh, 600px)" />
          <p className="muted small" style={{ marginTop: 8 }}>
            Granice działek pojawiają się po przybliżeniu mapy. Źródło: GUGiK (Geoportal).
          </p>
        </section>

        <form className="panel" onSubmit={submit} noValidate>
          <p className="panel-step">
            <span className="num">1</span> Działka
          </p>

          {plot ? (
            <div className="plot-card" aria-live="polite">
              <div className="plot-card-head">
                <strong>Wybrana działka</strong>
                <button
                  type="button"
                  className="btn-link small"
                  onClick={() => {
                    setPlot(null);
                    setPlotQuery("");
                  }}
                >
                  Zmień
                </button>
              </div>
              <dl>
                <dt>Numer</dt>
                <dd>{plot.plotId}</dd>
                <dt>Powierzchnia</dt>
                <dd>{formatNumber(plot.areaHa, 2)} ha</dd>
                {(plot.commune || plot.voivodeship) && (
                  <>
                    <dt>Gmina</dt>
                    <dd>{[plot.commune, plot.voivodeship && `woj. ${plot.voivodeship}`].filter(Boolean).join(", ")}</dd>
                  </>
                )}
              </dl>
            </div>
          ) : (
            <p className="muted small" style={{ marginTop: 0 }}>
              Kliknij działkę na mapie
            </p>
          )}

          {!plot && (
            <>
              <div className="or-sep">albo</div>
              <div className="field" style={{ marginBottom: 8 }}>
                <label htmlFor="plotId">Numer działki</label>
                <div className="input-row">
                  <input
                    id="plotId"
                    className="input"
                    value={plotQuery}
                    onChange={(e) => setPlotQuery(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") findById(e);
                    }}
                    placeholder="np. 141201_1.0001.123"
                    autoComplete="off"
                    spellCheck={false}
                    aria-describedby="plotId-help"
                  />
                  <button type="button" className="btn btn-secondary" onClick={() => findById()} disabled={plotBusy === "id"}>
                    {plotBusy === "id" ? <span className="spinner" /> : "Znajdź"}
                  </button>
                </div>
              </div>
              <details className="help" id="plotId-help">
                <summary>Gdzie znajdę numer działki?</summary>
                <div>
                  <p>
                    Pełny numer (identyfikator) działki jest na <strong>wypisie z rejestru gruntów</strong> oraz w
                    decyzji podatkowej. Wygląda np. tak: <code>141201_1.0001.123</code>.
                  </p>
                  <p style={{ marginBottom: 0 }}>Nie masz go pod ręką? Po prostu kliknij działkę na mapie.</p>
                  {API_MODE === "mock" && (
                    <p className="small muted" style={{ margin: "8px 0 0" }}>
                      Tryb demonstracyjny: wpisz <code>{MOCK_NOT_FOUND_ID}</code>, żeby zobaczyć komunikat o
                      nieznalezionej działce.
                    </p>
                  )}
                </div>
              </details>
            </>
          )}

          {plotErrMsg && (
            <Notice tone="error" title={plotErrMsg.title} role="alert">
              <p>{plotErrMsg.text}</p>
            </Notice>
          )}
          {showErrors && !plot && !plotErrMsg && <p className="field-error">Najpierw wskaż działkę.</p>}

          <hr className="panel-divider" />

          <p className="panel-step">
            <span className="num">2</span> Uprawa i termin
          </p>

          <div className="field">
            <label htmlFor="crop">Co rośnie (lub będzie rosło) na działce?</label>
            {cropsError ? (
              <Notice tone="error" title="Nie udało się pobrać listy upraw" role="alert">
                <button type="button" className="btn btn-secondary" onClick={loadCrops}>
                  Spróbuj ponownie
                </button>
              </Notice>
            ) : (
              <select
                id="crop"
                className="select"
                value={cropId}
                onChange={(e) => setCropId(e.target.value)}
                disabled={!crops}
              >
                <option value="">{crops ? "Wybierz uprawę…" : "Ładowanie…"}</option>
                {crops?.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                  </option>
                ))}
              </select>
            )}
            {showErrors && !cropId && <p className="field-error">Wybierz uprawę.</p>}
          </div>

          <div className="field">
            <label htmlFor="date">Na jaki dzień przygotować ocenę?</label>
            <p className="hint">Domyślnie dzisiaj. Możesz wybrać dowolny dzień z ostatnich 10 lat.</p>
            <input
              id="date"
              type="date"
              className="input"
              value={date}
              min={dateMin}
              max={dateMax}
              onChange={(e) => setDate(e.target.value)}
            />
            {showErrors && !dateValid && <p className="field-error">Wybierz datę z ostatnich 10 lat.</p>}
          </div>

          <button type="submit" className="btn btn-lg" style={{ width: "100%" }} disabled={showErrors && !canSubmit}>
            Przygotuj raport
          </button>
          <p className="muted small" style={{ margin: "10px 0 0", textAlign: "center" }}>
            Raport powstaje na żywo z publicznych danych. Zwykle trwa to kilkanaście sekund.
          </p>
        </form>
      </div>
    </div>
  );
}
