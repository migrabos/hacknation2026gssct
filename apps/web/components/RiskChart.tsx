import type { RiskWindow } from "@/lib/types";
import { formatNumber } from "@/lib/labels";
import s from "./RiskChart.module.css";

/** SMSR window "21.V–20.VII" → short axis label "20.VII" (end of the 60-day window). */
function axisLabel(label: string, method: RiskWindow["method"]): string {
  if (method !== "smsr") return label;
  const parts = label.split("–");
  return parts[parts.length - 1] ?? label;
}

/** "When does this plot run short of water" – 10-year view, always open (also printed). */
export default function RiskChart({ risk }: { risk?: RiskWindow | null }) {
  if (!risk || risk.bars.length === 0) return null;
  const smsr = risk.method === "smsr";
  // smsr: bar = years below the IUNG threshold (0–10); monthly: bar = water deficit (−KBW, mm).
  const height = (v: number | null | undefined) => (smsr ? v ?? 0 : Math.max(0, -(v ?? 0)));
  const raw = Math.max(...risk.bars.map((b) => height(b.value)));
  const max = smsr ? Math.max(risk.bars[0]?.of || 10, 1) : Math.max(10, Math.ceil(raw / 20) * 20);
  const anyCritical = risk.bars.some((b) => b.critical);

  const tip = (b: RiskWindow["bars"][number]) =>
    smsr
      ? `${b.label}: w ${formatNumber(b.value ?? 0, 0)} z ${b.of} lat bilans wodny poniżej progu IUNG` +
        (b.thresholdMm != null ? ` (${formatNumber(b.thresholdMm, 0)} mm)` : "")
      : `${b.label}: mediana bilansu wodnego ${formatNumber(b.value ?? 0, 0)} mm (${b.of} lat)`;

  return (
    <section className={s.card} aria-labelledby="risk-window-h">
      <h3 id="risk-window-h" className={s.title}>Kiedy na tej działce najczęściej brakuje wody</h3>
      <p className={s.text}>{risk.text}</p>

      <div className={s.legend} aria-hidden="true">
        <span><i className={s.keyRisky} /> {smsr ? "okres ryzyka (≥ 3 lata na 10)" : "najbardziej suche miesiące"}</span>
        <span><i className={s.key} /> {smsr ? "pozostałe okresy" : "pozostałe miesiące"}</span>
        {anyCritical && <span><i className={s.keyCritical} /> najbardziej wrażliwa faza uprawy</span>}
      </div>

      {/* Each bar is a labelled image (screen readers, Tab); tapping or hovering shows the same text as a tip. */}
      <div className={s.plot} role="group" aria-label={risk.unit}>
        <span className={s.max} aria-hidden="true">
          {smsr ? `${max} lat` : `−${max} mm`}
        </span>
        {risk.bars.map((b, i) => (
          <div
            key={b.label}
            className={s.col}
            tabIndex={0}
            role="img"
            aria-label={tip(b) + (b.critical ? " · najbardziej wrażliwa faza uprawy" : "")}
            // iOS Safari does not focus a tapped <div> by itself — the tip is shown on :focus
            onClick={(e) => e.currentTarget.focus()}
            // tip anchored to the bar's side of the chart, so it never sticks out of a narrow phone screen
            data-edge={i < risk.bars.length / 3 ? "start" : i >= risk.bars.length - risk.bars.length / 3 ? "end" : "mid"}
          >
            <div className={s.track}>
              <span
                className={s.bar}
                data-risky={b.risky}
                style={{ height: `${(height(b.value) / max) * 100}%`, ["--i" as string]: i }}
              />
            </div>
            <span className={s.crit} data-on={b.critical} />
            <span className={s.label} aria-hidden="true">{axisLabel(b.label, risk.method)}</span>
            <span className={s.tip} aria-hidden="true">
              {tip(b)}
            </span>
          </div>
        ))}
      </div>

      <p className={s.note}>
        {smsr
          ? "Każdy słupek to jeden z 60-dniowych okresów monitoringu suszy IUNG (podpis = koniec okresu). Wysokość = w ilu z ostatnich 10 lat bilans wodny (opad minus parowanie) spadł poniżej progu suszy rolniczej z rozporządzenia MRiRW dla tej uprawy i tej kategorii gleby."
          : "Wysokość słupka = o ile parowanie zwykle przewyższa opady w danym miesiącu (mediana z 10 lat). Dla tej uprawy lub gleby nie ma progu suszy IUNG, więc nie oceniamy, kiedy brak wody obniża plon."}
      </p>
    </section>
  );
}
