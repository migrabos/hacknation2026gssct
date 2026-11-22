"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import ReportView from "@/components/ReportView";
import { splitPlotId } from "@/lib/labels";
import { loadReport } from "@/lib/report-store";
import type { Report } from "@/lib/types";

export default function ReportPage() {
  const [report, setReport] = useState<Report | null | undefined>(undefined);

  useEffect(() => {
    setReport(loadReport());
  }, []);

  // Tab title with the plot ("Raport wodny — działka 318, gm. Kutno · Retencja"); browsers also use it
  // as the default file name when the report is saved as PDF. Restored when leaving the page.
  useEffect(() => {
    if (!report) return;
    const previous = document.title;
    const { nr } = splitPlotId(report.plot.plotId);
    const where = report.plot.commune ? `, gm. ${report.plot.commune}` : "";
    document.title = `Raport wodny — działka ${nr}${where} · Retencja`;
    return () => {
      document.title = previous;
    };
  }, [report]);

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
