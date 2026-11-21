import type { PrecipMonth } from "@/lib/types";
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
export default function RainChart({ months, analysisDate }: { months: PrecipMonth[]; analysisDate: string }) {
  const rows = months.filter((m) => /^\d{4}-\d{2}$/.test(m.month));
  if (rows.length === 0 || rows.every((m) => m.precipMm == null)) return null;

  const max = niceMax(Math.max(...rows.flatMap((m) => [m.precipMm ?? 0, m.normalMm ?? 0])));
  const complete = rows.every((m) => m.precipMm != null && m.normalMm != null);
  const total = rows.reduce((s, m) => s + (m.precipMm ?? 0), 0);
  const norm = rows.reduce((s, m) => s + (m.normalMm ?? 0), 0);
  const years = Math.max(...rows.map((m) => m.normalYears));
  const partialTo = formatDate(analysisDate);

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

        <div className="rain-plot" aria-hidden="true">
          <span className="rain-max">{max} mm</span>
          {rows.map((m, i) => {
            const { y, mo, long } = label(m);
            const edge = i < 2 ? "start" : i > rows.length - 3 ? "end" : "mid";
            return (
              <div key={m.month} className="rain-col" tabIndex={0} data-edge={edge}>
                <div className="rain-track">
                  {m.precipMm != null && (
                    <span className="rain-bar" data-partial={m.partial} style={{ height: `${(m.precipMm / max) * 100}%` }} />
                  )}
                  {m.normalMm != null && <span className="rain-avg" style={{ bottom: `${(m.normalMm / max) * 100}%` }} />}
                </div>
                <span className="rain-month">
                  {SHORT[mo - 1]}
                  {(i === 0 || mo === 1) && <span className="rain-year">{y}</span>}
                </span>
                <span className="rain-tip" role="tooltip">
                  <strong>{long}</strong>
                  <br />
                  {m.precipMm != null ? `${formatNumber(m.precipMm, 0)} mm` : "brak danych"}
                  {m.normalMm != null && <> · zwykle {formatNumber(m.normalMm, 0)} mm</>}
                </span>
              </div>
            );
          })}
        </div>

        <table className="visually-hidden">
          <caption>Opady w ostatnich 12 miesiącach i średnia z {years} lat</caption>
          <thead>
            <tr>
              <th scope="col">Miesiąc</th>
              <th scope="col">Opady (mm)</th>
              <th scope="col">Średnia (mm)</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((m) => (
              <tr key={m.month}>
                <th scope="row">{label(m).long}</th>
                <td>{m.precipMm != null ? formatNumber(m.precipMm, 0) : "brak"}</td>
                <td>{m.normalMm != null ? formatNumber(m.normalMm, 0) : "brak"}</td>
              </tr>
            ))}
          </tbody>
        </table>

        <p className="rain-note">
          Kreska to średnia z tych samych dni w {years} poprzednich latach.
          {rows.some((m) => m.partial) && <> Ostatni miesiąc liczony do {partialTo}.</>} Źródło: Open-Meteo (ERA5).
        </p>
      </div>
    </details>
  );
}
