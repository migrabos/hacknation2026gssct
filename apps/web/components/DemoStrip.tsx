import { API_MODE } from "@/lib/api";

/** Always tell the user when they are looking at sample data. */
export default function DemoStrip() {
  if (API_MODE !== "mock") return null;
  return (
    <div className="demo-strip" role="status">
      <div className="container">
        <strong>Tryb demonstracyjny:</strong> raporty pokazują przykładowe dane, a nie wynik
        prawdziwej analizy Twojej działki.
      </div>
    </div>
  );
}
