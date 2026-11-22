import type { Metadata } from "next";
import "leaflet/dist/leaflet.css";
import "./globals.css";
import "@/styles/print.css";
import SiteHeader from "@/components/SiteHeader";

export const metadata: Metadata = {
  title: "Retencja — woda na Twoim polu",
  description:
    "Sprawdź, jak sucho jest na Twojej działce, dlaczego i co możesz zrobić, żeby zatrzymać wodę.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    // class="dark" already in the server HTML: dark is the default, so no light flash on load.
    // instrumentation-client.ts switches to light before hydration if the farmer chose it.
    <html lang="pl" className="dark" suppressHydrationWarning>
      <body>
        <a href="#tresc" className="visually-hidden">
          Przejdź do treści
        </a>
        <div className="topbar" aria-hidden="true">
          <div className="container" />
        </div>
        <SiteHeader />
        <main id="tresc">{children}</main>
        <footer className="site-footer">
          <div className="container">
            <span>Retencja — narzędzie wspierające decyzje o zatrzymywaniu wody na polu.</span>
            <span>Dane: GUGiK, Open-Meteo, ISRIC SoilGrids, Copernicus Sentinel-2.</span>
          </div>
        </footer>
      </body>
    </html>
  );
}
