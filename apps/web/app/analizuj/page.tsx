"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import Map from "@/components/Map";
import Notice from "@/components/Notice";
import PipelineLoader from "@/components/PipelineLoader";
import { ApiError, api } from "@/lib/api";
import { ERROR_MESSAGE, countyLabel, formatNumber } from "@/lib/labels";
import { loadForm, saveForm, saveReport } from "@/lib/report-store";
import type { ApiErrorKind, Crop, Plot, Region } from "@/lib/types";

function isoDay(d: Date): string {
  const tz = d.getTimezoneOffset() * 60_000;
  return new Date(d.getTime() - tz).toISOString().slice(0, 10);
}

function errorKind(err: unknown): ApiErrorKind {
  return err instanceof ApiError ? err.kind : "server";
}

/** Above this many matches we ask the user to add the commune after a comma. */
const REGION_FILTER_HINT_AT = 6;
/** The API returns at most this many matches (best first). */
const REGION_MAX_RESULTS = 100;
/** Matches shown before "Pokaż wszystkie" — a long list of buttons is hard to scan on a phone. */
const REGION_SHOWN_AT_FIRST = 8;

const reducedMotion = () =>
  typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

/**
 * Show which city an obręb belongs to: "Kraków – obręb K-1" (numbered city obręby),
 * "Wrocław – Biskupin" (city obręby named after districts). Villages keep their name.
 * Region id kind digit: _1 = city gmina, _8 / _9 = city districts (Warszawa, Kraków, Łódź…).
 */
function regionName(r: Region): string {
  const name = r.region ?? r.regionId;
  if (!r.commune || name === r.commune) return name;
  const letters = (name.match(/\p{L}/gu) ?? []).length;
  if (letters < 3) return `${r.commune} – obręb ${name}`;
  const kind = r.regionId.charAt(7);
  return kind === "1" || kind === "8" || kind === "9" ? `${r.commune} – ${name}` : name;
}

function regionLabel(r: Region): string {
  return [
    r.commune && `gm. ${r.commune}`,
    r.county && countyLabel(r.county),
    r.voivodeship && `woj. ${r.voivodeship}`,
  ]
    .filter(Boolean)
    .join(", ");
}

/** "Zalesie, Halinów" -> name "Zalesie", filter "halinów" (matched against commune/county/voivodeship). */
function splitVillageQuery(q: string): { name: string; filter: string } {
  const [name, ...rest] = q.split(",");
  return { name: name.trim(), filter: rest.join(" ").trim().toLowerCase() };
}

export default function AnalyzePage() {
  const router = useRouter();

  const [plotQuery, setPlotQuery] = useState("");
  const [plot, setPlot] = useState<Plot | null>(null);
  const [plotBusy, setPlotBusy] = useState<"id" | "map" | null>(null);
  const [plotError, setPlotError] = useState<ApiErrorKind | null>(null);

  // Village (obręb) + parcel number lookup — the simple path for most farmers.
  const [villageQuery, setVillageQuery] = useState("");
  const [regions, setRegions] = useState<Region[] | null>(null);
  const [regionsBusy, setRegionsBusy] = useState(false);
  const [regionsError, setRegionsError] = useState<ApiErrorKind | null>(null);
  const [region, setRegion] = useState<Region | null>(null);
  const [parcelNr, setParcelNr] = useState("");
  const [showAllRegions, setShowAllRegions] = useState(false);
  // Focus the parcel-number field only when the farmer picked the village themselves — not when an
  // exact match was chosen automatically (they may still be typing, the keys would land in the wrong field).
  const [focusParcel, setFocusParcel] = useState(false);
  const [nrBusy, setNrBusy] = useState(false);
  const [nrError, setNrError] = useState<string | null>(null);
  const searchSeq = useRef(0);

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
  // Becomes true once the saved form has been restored — saving before that would wipe it.
  const [hydrated, setHydrated] = useState(false);
  const mapRef = useRef<HTMLElement>(null);

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
    const minIso = isoDay(min);
    const maxIso = isoDay(today);
    setDateMax(maxIso);
    setDateMin(minIso);
    // Back from the report ("Zmień uprawę lub datę" / browser back): keep the plot, crop and date.
    const saved = loadForm();
    setDate(saved?.date && saved.date >= minIso && saved.date <= maxIso ? saved.date : maxIso);
    if (saved) {
      setPlot(saved.plot);
      setRegion(saved.region);
      setCropId(saved.cropId ?? "");
      if (saved.region) setVillageQuery(saved.region.region ?? "");
    }
    setHydrated(true);
    loadCrops();
    api.health().catch(() => setApiDown(true));
  }, [loadCrops]);

  useEffect(() => {
    if (hydrated) saveForm({ plot, region, cropId, date });
  }, [hydrated, plot, region, cropId, date]);

  const villageName = splitVillageQuery(villageQuery).name;
  const villageSearch = villageQuery.trim();

  // Debounced search over the offline PRG index (prefix, no diacritics needed, by gmina);
  // the text after a comma narrows results server-side ("Zdziłowice, Godziszów").
  useEffect(() => {
    if (region) return;
    const name = villageName;
    const q = villageSearch;
    if (name.length < 2) {
      searchSeq.current++; // drop any in-flight search for the text that was just deleted
      setRegionsBusy(false);
      setRegions(null);
      setRegionsError(null);
      return;
    }
    const seq = ++searchSeq.current;
    const t = setTimeout(async () => {
      setRegionsBusy(true);
      setRegionsError(null);
      try {
        const found = await api.searchRegions(q);
        if (seq !== searchSeq.current) return;
        setRegions(found);
        setShowAllRegions(false);
      } catch (err) {
        if (seq !== searchSeq.current) return;
        setRegions(null);
        setRegionsError(errorKind(err));
      } finally {
        if (seq === searchSeq.current) setRegionsBusy(false);
      }
    }, 250);
    return () => clearTimeout(t);
  }, [villageName, villageSearch, region]);

  const villageFilter = splitVillageQuery(villageQuery).filter;
  const shownRegions = regions;

  function chooseRegion(r: Region, byUser = true) {
    setFocusParcel(byUser);
    setRegion(r);
    setNrError(null);
    setPlotError(null);
    // The search index has no geometry; fetch the obręb extent to zoom the map (best-effort).
    if (!r.bbox) {
      api
        .regionExtent(r.regionId)
        .then((bbox) => {
          if (bbox) setRegion((cur) => (cur?.regionId === r.regionId ? { ...cur, bbox } : cur));
        })
        .catch(() => {});
    }
  }

  function clearRegion() {
    setRegion(null);
    setParcelNr("");
    setNrError(null);
  }

  // A single *exact* match needs no extra click (not while the user is still typing a prefix).
  useEffect(() => {
    if (
      !region &&
      regions?.length === 1 &&
      !villageFilter &&
      regions[0].region?.toLowerCase() === villageName.toLowerCase()
    )
      chooseRegion(regions[0], false);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [regions, region, villageFilter, villageName]);

  async function findByRegion(e?: { preventDefault(): void }) {
    e?.preventDefault();
    if (!region) return;
    if (!parcelNr.trim()) {
      setNrError("Wpisz numer działki, np. 134 albo 134/2.");
      return;
    }
    setNrBusy(true);
    setNrError(null);
    try {
      setPlot(await api.plotByRegion(region.regionId, parcelNr));
    } catch (err) {
      const kind = errorKind(err);
      setNrError(
        kind === "not_found" || kind === "bad_request"
          ? (err as ApiError).message && (err as ApiError).message !== kind
            ? (err as ApiError).message
            : `Nie znaleziono działki nr ${parcelNr.trim()} w tej miejscowości.`
          : ERROR_MESSAGE[kind].text,
      );
    } finally {
      setNrBusy(false);
    }
  }

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
  const canSubmit = Boolean(plot && dateValid && cropId);

  function submit(e: FormEvent) {
    e.preventDefault();
    void runAnalysis();
  }

  /** Bring the first missing answer into view — on a phone the error can be a screen above the button. */
  function focusFirstProblem() {
    const id = !plot
      ? region
        ? "parcelNr"
        : document.getElementById("village")
          ? "village"
          : "plotId"
      : !cropId
        ? "crop"
        : "date";
    requestAnimationFrame(() => {
      const el = document.getElementById(id) ?? document.querySelector<HTMLElement>(".workspace-panel .field-error");
      if (!el) return;
      el.scrollIntoView({ block: "center", behavior: reducedMotion() ? "auto" : "smooth" });
      el.focus({ preventScroll: true });
    });
  }

  function showMap() {
    mapRef.current?.scrollIntoView({ block: "start", behavior: reducedMotion() ? "auto" : "smooth" });
  }

  async function runAnalysis() {
    setShowErrors(true);
    if (!plot || !canSubmit) {
      focusFirstProblem();
      return;
    }
    setAnalyzeError(null);
    setRunning(true);
    window.scrollTo({ top: 0 });
    try {
      const where = { plotId: plot.plotId, lat: plot.centroid[1], lng: plot.centroid[0], analysisDate: date };
      saveReport(await api.analyze({ ...where, cropId }, plot));
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

  // "Najpierw wskaż działkę" sits right under the field the farmer is sent back to (village or number)
  const plotMissing = showErrors && !plot && !plotError;
  const plotErrMsg =
    plotError === "bad_request"
      ? { title: "Wpisz identyfikator działki", text: "Na przykład 141201_1.0001.123 — znajdziesz go na wypisie z rejestru gruntów." }
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
          Wpisz swoją miejscowość i numer działki (albo kliknij ją na mapie), wybierz uprawę i kliknij „Przygotuj
          raport”.
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

      <div className="analyze-grid workspace">
        <section aria-labelledby="map-h" className="workspace-map" ref={mapRef}>
          <h2 id="map-h" className="visually-hidden">
            Mapa
          </h2>
          <Map
            plot={plot}
            onPick={pickOnMap}
            busy={plotBusy === "map"}
            height="100%"
            focusBbox={region?.bbox ?? null}
          />
        </section>

        <form className="panel workspace-panel" onSubmit={submit} noValidate>
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
              <button type="button" className="btn-link small narrow-only" onClick={showMap}>
                Pokaż na mapie ↓
              </button>
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
          ) : null}

          {!plot && (
            <>
              {!region ? (
                <div className="field" style={{ marginBottom: 12 }}>
                  <label htmlFor="village">Miejscowość, w której leży działka</label>
                  <p className="hint" id="village-hint">
                    Zacznij pisać nazwę wsi albo gminy — polskie litery nie są konieczne (np. Zdziłowice, Godziszów).
                  </p>
                  <div className="input-row">
                    <input
                      id="village"
                      className="input"
                      type="search"
                      enterKeyHint="search"
                      value={villageQuery}
                      onChange={(e) => setVillageQuery(e.target.value)}
                      onKeyDown={(e) => {
                        // Enter / "Szukaj" on a phone keyboard must not submit the whole form.
                        if (e.key !== "Enter") return;
                        e.preventDefault();
                        if (shownRegions?.length === 1) chooseRegion(shownRegions[0]);
                      }}
                      placeholder="np. Krzewina"
                      autoComplete="off"
                      aria-describedby={`village-hint village-status${showErrors && !plot ? " plot-err" : ""}`}
                      aria-invalid={showErrors && !plot ? true : undefined}
                    />
                    {regionsBusy && <span className="spinner" style={{ alignSelf: "center" }} aria-label="Szukam" />}
                  </div>
                  {plotMissing && (
                    <p className="field-error" id="plot-err">
                      Najpierw wskaż działkę — wpisz miejscowość i numer albo kliknij ją na mapie.
                    </p>
                  )}

                  {/* Only the short status is a live region — not the list of buttons, which would be read out whole. */}
                  <div id="village-status" aria-live="polite">
                    {regionsError && <p className="field-error">{ERROR_MESSAGE[regionsError].text}</p>}
                    {shownRegions && shownRegions.length === 0 && !regionsBusy && (
                      <p className="hint">
                        {villageFilter
                          ? `Nie znaleźliśmy „${villageName}” w „${villageFilter}”. Sprawdź nazwę gminy albo usuń tekst po przecinku.`
                          : `Nie znaleźliśmy miejscowości „${villageName}”. Sprawdź pisownię albo wpisz nazwę gminy. W miastach obręby mają numery zamiast nazw dzielnic — wpisz miasto i numer obrębu z wypisu (np. Warszawa 1-01-01, Kraków K-12) albo kliknij działkę na mapie.`}
                      </p>
                    )}
                    {shownRegions && shownRegions.length > 0 && (
                      <p className="hint" style={{ marginTop: 6 }}>
                        {shownRegions.length === 1
                          ? "Znaleziono:"
                          : shownRegions.length >= REGION_MAX_RESULTS
                            ? `Ponad ${REGION_MAX_RESULTS - 1} pasujących miejscowości`
                            : `Pasujące miejscowości: ${shownRegions.length}`}
                        {shownRegions.length > REGION_FILTER_HINT_AT && !villageFilter ? (
                          <>
                            {" "}
                            — dopisz po przecinku gminę lub powiat, np.{" "}
                            <em>
                              {villageName}, {shownRegions[0].commune ?? shownRegions[0].county}
                            </em>
                            , albo wybierz z listy:
                          </>
                        ) : shownRegions.length > 1 ? (
                          " — wybierz swoją:"
                        ) : null}
                      </p>
                    )}
                  </div>
                  {shownRegions && shownRegions.length > 0 && (
                    <>
                      <ul className="region-list">
                        {(showAllRegions ? shownRegions : shownRegions.slice(0, REGION_SHOWN_AT_FIRST)).map((r) => (
                          <li key={r.regionId}>
                            <button type="button" className="region-option" onClick={() => chooseRegion(r)}>
                              <strong>{regionName(r)}</strong>
                              <span>{regionLabel(r)}</span>
                            </button>
                          </li>
                        ))}
                      </ul>
                      {!showAllRegions && shownRegions.length > REGION_SHOWN_AT_FIRST && (
                        <button type="button" className="btn btn-secondary region-more" onClick={() => setShowAllRegions(true)}>
                          Pokaż wszystkie ({shownRegions.length})
                        </button>
                      )}
                    </>
                  )}
                </div>
              ) : (
                <>
                  <div className="region-chosen">
                    <div>
                      <strong>{regionName(region)}</strong>
                      <span className="muted small"> — {regionLabel(region)}</span>
                    </div>
                    <button type="button" className="btn-link small" onClick={clearRegion}>
                      Zmień
                    </button>
                  </div>
                  <div className="field" style={{ marginBottom: 8 }}>
                    <label htmlFor="parcelNr">Numer działki</label>
                    <p className="hint">Tak jak na wypisie z rejestru gruntów, np. 134 albo 134/2.</p>
                    <div className="input-row">
                      <input
                        id="parcelNr"
                        className="input"
                        value={parcelNr}
                        onChange={(e) => setParcelNr(e.target.value)}
                        onKeyDown={(e) => {
                          if (e.key === "Enter") findByRegion(e);
                        }}
                        placeholder="np. 134"
                        inputMode="text"
                        autoComplete="off"
                        spellCheck={false}
                        autoFocus={focusParcel}
                        aria-invalid={(showErrors && !plot) || nrError ? true : undefined}
                        aria-describedby={nrError ? "nr-err" : showErrors && !plot ? "plot-err" : undefined}
                      />
                      <button type="button" className="btn btn-secondary" onClick={() => findByRegion()} disabled={nrBusy}>
                        {nrBusy ? <span className="spinner" /> : "Znajdź"}
                      </button>
                    </div>
                    {nrError ? (
                      <p className="field-error" role="alert" id="nr-err">
                        {nrError}
                      </p>
                    ) : (
                      plotMissing && (
                        <p className="field-error" id="plot-err">
                          Najpierw wskaż działkę — wpisz miejscowość i numer albo kliknij ją na mapie.
                        </p>
                      )
                    )}
                  </div>
                  <p className="muted small" style={{ marginTop: 0 }}>
                    Nie znasz numeru? Mapa pokazuje już Twoją miejscowość — przybliż ją i kliknij swoje pole.{" "}
                    <button type="button" className="btn-link narrow-only" onClick={showMap}>
                      Pokaż mapę ↓
                    </button>
                  </p>
                </>
              )}

              <div className="or-sep">albo</div>
              <p className="muted small" style={{ marginTop: 0 }}>
                Kliknij działkę na mapie — granice działek pojawią się po przybliżeniu.
              </p>

              <details className="help" id="plotId-help">
                <summary>Mam pełny identyfikator działki</summary>
                <div>
                  <div className="field" style={{ marginBottom: 8 }}>
                    <label htmlFor="plotId">Identyfikator działki</label>
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
                      />
                      <button type="button" className="btn btn-secondary" onClick={() => findById()} disabled={plotBusy === "id"}>
                        {plotBusy === "id" ? <span className="spinner" /> : "Znajdź"}
                      </button>
                    </div>
                  </div>
                  <p style={{ marginBottom: 0 }} className="small">
                    Pełny identyfikator jest na <strong>wypisie z rejestru gruntów</strong>, np.{" "}
                    <code>141201_1.0001.123</code>.
                  </p>
                </div>
              </details>
            </>
          )}

          {plotErrMsg && (
            <Notice tone="error" title={plotErrMsg.title} role="alert">
              <p>{plotErrMsg.text}</p>
            </Notice>
          )}


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
                aria-invalid={showErrors && !cropId ? true : undefined}
                aria-describedby={showErrors && !cropId ? "crop-err" : undefined}
              >
                <option value="">{crops ? "Wybierz uprawę…" : "Ładowanie…"}</option>
                {crops?.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                  </option>
                ))}
              </select>
            )}
            {showErrors && !cropId && (
              <p className="field-error" id="crop-err">
                Wybierz uprawę.
              </p>
            )}
          </div>

          <div className="field">
            <label htmlFor="date">Na jaki dzień przygotować ocenę?</label>
            <p className="hint" id="date-hint">
              Domyślnie dzisiaj. Możesz wybrać dowolny dzień z ostatnich 10 lat.
            </p>
            <input
              id="date"
              type="date"
              className="input"
              value={date}
              min={dateMin}
              max={dateMax}
              onChange={(e) => setDate(e.target.value)}
              aria-invalid={showErrors && !dateValid ? true : undefined}
              aria-describedby={`date-hint${showErrors && !dateValid ? " date-err" : ""}`}
            />
            {showErrors && !dateValid && (
              <p className="field-error" id="date-err">
                Wybierz datę z ostatnich 10 lat.
              </p>
            )}
          </div>

          <button type="submit" className="btn btn-lg" style={{ width: "100%" }}>
            Przygotuj raport wodny
          </button>
          <p className="muted small" style={{ margin: "10px 0 0", textAlign: "center" }}>
            Raport powstaje na żywo z publicznych danych. Zwykle trwa to kilkanaście sekund.
          </p>
        </form>
      </div>
    </div>
  );
}
