"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import CropFitReportView from "@/components/CropFitReportView";
import { loadCropFitReport } from "@/lib/report-store";
import type { CropFitReport } from "@/lib/types";

export default function CropFitPage() {
  const [report, setReport] = useState<CropFitReport | null | undefined>(undefined);

  useEffect(() => {
    setReport(loadCropFitReport());
  }, []);

  if (report === undefined) {
    return (
      <div className="container" style={{ paddingBlock: 48 }}>
        <p className="muted">Wczytywanie raportu…</p>
      </div>
    );
  }

  if (report === null) {
    return (
      <div className="container" style={{ paddingBlock: 48, maxWidth: 640 }}>
        <h1>Brak raportu</h1>
        <p>Nie mamy jeszcze porównania upraw do pokazania. Wskaż działkę i wybierz „Dobór uprawy”.</p>
        <Link href="/analizuj" className="btn">
          Sprawdź działkę
        </Link>
      </div>
    );
  }

  return <CropFitReportView report={report} />;
}
