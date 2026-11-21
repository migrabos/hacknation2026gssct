"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import ReportView from "@/components/ReportView";
import { loadReport } from "@/lib/report-store";
import type { Report } from "@/lib/types";

export default function ReportPage() {
  const [report, setReport] = useState<Report | null | undefined>(undefined);

  useEffect(() => {
    setReport(loadReport());
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
        <p>Nie mamy jeszcze raportu do pokazania. Wskaż działkę i uprawę, a przygotujemy go w kilkanaście sekund.</p>
        <Link href="/analizuj" className="btn">
          Sprawdź działkę
        </Link>
      </div>
    );
  }

  return <ReportView report={report} />;
}
