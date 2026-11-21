import type { Metadata } from "next";
import "leaflet/dist/leaflet.css";
import "./globals.css";
import "@/styles/print.css";
import SiteHeader from "@/components/SiteHeader";
import { THEME_BOOTSTRAP } from "@/lib/theme";

export const metadata: Metadata = {
  title: "Retencja — woda na Twoim polu",
  description:
    "Sprawdź, jak sucho jest na Twojej działce, dlaczego i co możesz zrobić, żeby zatrzymać wodę.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="pl" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: THEME_BOOTSTRAP }} />
      </head>
      <body>
        <a href="#tresc" className="visually-hidden">
          Przejdź do treści
        </a>
        <div className="topbar">
          <div className="container">Prototyp narzędzia doradczego · HackNation 2026</div>
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
