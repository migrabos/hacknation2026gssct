/** Polish, farmer-friendly labels for enum values. */
import type {
  ApiErrorKind,
  Confidence,
  MoistureLevel,
  RiskLevel,
  SourceMode,
  SourceStatus,
} from "./types";

export const MOISTURE_SCALE: { level: MoistureLevel; label: string }[] = [
  { level: "very_dry", label: "Bardzo sucho" },
  { level: "dry", label: "Sucho" },
  { level: "normal", label: "W normie" },
  { level: "wet", label: "Mokro" },
];

export const RISK_SCALE: { level: RiskLevel; label: string }[] = [
  { level: "low", label: "Niska" },
  { level: "medium", label: "Średnia" },
  { level: "high", label: "Wysoka" },
];

export const CONFIDENCE_LABEL: Record<Confidence, string> = {
  low: "niska pewność",
  medium: "średnia pewność",
  high: "wysoka pewność",
};

export const COST_LABEL: Record<RiskLevel, string> = {
  low: "niski koszt",
  medium: "średni koszt",
  high: "wyższy koszt",
};

export const SOURCE_STATUS_LABEL: Record<SourceStatus, string> = {
  ok: "pobrano",
  partial: "częściowo",
  failed: "brak danych",
};

export const SOURCE_MODE_LABEL: Record<SourceMode, string> = {
  live: "pobrane teraz",
  cached: "z pamięci podręcznej",
  static: "tabela wbudowana",
};

export const ERROR_MESSAGE: Record<ApiErrorKind, { title: string; text: string }> = {
  not_found: {
    title: "Nie znaleźliśmy tej działki",
    text: "Sprawdź numer działki (najlepiej przepisz go z wypisu z rejestru gruntów) albo wskaż działkę na mapie.",
  },
  timeout: {
    title: "Analiza trwa zbyt długo",
    text: "Któryś z serwisów z danymi odpowiada wolno. Spróbuj ponownie za chwilę.",
  },
  api_down: {
    title: "Brak połączenia z serwerem",
    text: "Nie udało się połączyć z serwerem analizy. Sprawdź internet i spróbuj ponownie.",
  },
  bad_request: {
    title: "Sprawdź wpisane dane",
    text: "Coś w formularzu jest niepoprawne. Sprawdź numer działki, uprawę i datę.",
  },
  server: {
    title: "Coś poszło nie tak",
    text: "Serwer analizy zgłosił błąd. Spróbuj ponownie za chwilę.",
  },
};

const dateFmt = new Intl.DateTimeFormat("pl-PL", { day: "numeric", month: "long", year: "numeric" });
const dateTimeFmt = new Intl.DateTimeFormat("pl-PL", {
  day: "numeric",
  month: "short",
  year: "numeric",
  hour: "2-digit",
  minute: "2-digit",
});

export function formatDate(iso: string): string {
  const d = new Date(iso.length === 10 ? `${iso}T12:00:00` : iso);
  return Number.isNaN(d.getTime()) ? iso : dateFmt.format(d);
}

export function formatDateTime(iso: string): string {
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : dateTimeFmt.format(d);
}

export function formatNumber(n: number, digits = 1): string {
  return n.toLocaleString("pl-PL", { maximumFractionDigits: digits });
}
