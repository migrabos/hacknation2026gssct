import type { PrecipMonth, Source } from "@/lib/types";
import { weatherProviders } from "@/lib/source-page";
import { formatDate, formatNumber } from "@/lib/labels";

const SHORT = ["sty", "lut", "mar", "kwi", "maj", "cze", "lip", "sie", "wrz", "paź", "lis", "gru"];
const LONG = [
  "styczeń", "luty", "marzec", "kwiecień", "maj", "czerwiec",
  "lipiec", "sierpień", "wrzesień", "październik", "listopad", "grudzień",
];

function niceMax(v: number): number {
  const step = v > 100 ? 25 : v > 40 ? 20 : 10;
  return Math.max(step, Math.ceil(v / step) * step);
}

/** Collapsible monthly rain histogram: last 12 months vs the multi-year mean. */
export default function RainChart({ months, analysisDate, source }: { months: PrecipMonth[]; analysisDate: string; source?: Source }) {
  const rows = months.filter((m) => /^\d{4}-\d{2}$/.test(m.month));
  if (rows.length === 0 || rows.every((m) => m.precipMm == null)) return null;

  const max = niceMax(Math.max(...rows.flatMap((m) => [m.precipMm ?? 0, m.normalMm ?? 0])));
  const complete = rows.every((m) => m.precipMm != null && m.normalMm != null);
  const total = rows.reduce((s, m) => s + (m.precipMm ?? 0), 0);
  const norm = rows.reduce((s, m) => s + (m.normalMm ?? 0), 0);
  const years = Math.max(...rows.map((m) => m.normalYears));
  const partialTo = formatDate(analysisDate);
  const providers = weatherProviders(source).map(({ name }) => name);

  const label = (m: PrecipMonth) => {
    const [y, mo] = m.month.split("-").map(Number);
    return { y, mo, long: `${LONG[mo - 1]} ${y}${m.partial ? ` (do ${partialTo})` : ""}` };
  };

  return (
    <details className="rain">
      <summary>
        <span>Opady miesiąc po miesiącu</span>
        {complete && norm > 0 && (
          <span className="rain-sum">
            {SHORT[Number(rows[0].month.slice(5)) - 1]} {rows[0].month.slice(0, 4)} – {rows[rows.length - 1].partial ? partialTo : `${SHORT[Number(rows[rows.length - 1].month.slice(5)) - 1]} ${rows[rows.length - 1].month.slice(0, 4)}`}:{" "}
            {formatNumber(total, 0)} mm · zwykle {formatNumber(norm, 0)} mm ({formatNumber((total / norm) * 100, 0)}%)
          </span>
        )}
      </summary>

      <div className="rain-body">
        <div className="rain-legend" aria-hidden="true">
          <span><i className="rain-key-bar" /> opady</span>
          <span><i className="rain-key-avg" /> średnia z {years} lat</span>
        </div>

        {/* Each bar is a labelled image (screen readers, Tab); tapping or hovering shows the same text as a tip. */}
        <div className="rain-plot" role="group" aria-label={`Opady w ostatnich 12 miesiącach i średnia z ${years} lat`}>
          <span className="rain-max" aria-hidden="true">
            {max} mm
          </span>
          {rows.map((m, i) => {
            const { y, mo, long } = label(m);
            // tip anchored to the bar's side of the chart, so it never sticks out of a narrow phone screen
            const edge = i < rows.length / 3 ? "start" : i >= rows.length - rows.length / 3 ? "end" : "mid";
            return (
              <div
                key={m.month}
                className="rain-col"
                tabIndex={0}
                role="img"
                aria-label={`${long}: ${m.precipMm != null ? `${formatNumber(m.precipMm, 0)} mm` : "brak danych"}${m.normalMm != null ? `, zwykle ${formatNumber(m.normalMm, 0)} mm` : ""}`}
                data-edge={edge}
                // iOS Safari does not focus a tapped <div> by itself — the tip is shown on :focus
                onClick={(e) => e.currentTarget.focus()}
              >
                <div className="rain-track">
                  {m.precipMm != null && (
                    <span
                      className="rain-bar"
                      data-partial={m.partial}
                      style={{ height: `${(m.precipMm / max) * 100}%`, ["--i" as string]: i }}
                    />
                  )}
                  {m.normalMm != null && <span className="rain-avg" style={{ bottom: `${(m.normalMm / max) * 100}%` }} />}
                </div>
                <span className="rain-month" aria-hidden="true">
                  {SHORT[mo - 1]}
                  {(i === 0 || mo === 1) && <span className="rain-year">{y}</span>}
                </span>
                <span className="rain-tip" aria-hidden="true">
                  <strong>{long}</strong>
                  <br />
                  {m.precipMm != null ? `${formatNumber(m.precipMm, 0)} mm` : "brak danych"}
                  {m.normalMm != null && <> · zwykle {formatNumber(m.normalMm, 0)} mm</>}
                </span>
              </div>
            );
          })}
        </div>

        <p className="rain-note">
          Kreska to średnia z tych samych dni w {years} poprzednich latach.
          {rows.some((m) => m.partial) && <> Ostatni miesiąc liczony do {partialTo}.</>}{" "}
          {providers.length ? `Dane: ${providers.join(" + ")}.` : "Brak informacji o dostawcy danych."}
        </p>
      </div>
    </details>
  );
}
