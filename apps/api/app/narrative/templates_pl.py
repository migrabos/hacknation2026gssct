"""Always-available Polish template narrative from structured Evidence fields."""

from __future__ import annotations

from app.schemas.evidence import Narrative, NarrativeSection, Report


def _refs(*groups: list[str]) -> list[str]:
    return list(dict.fromkeys(r for g in groups for r in g))


def build_template_narrative(report: Report) -> Narrative:
    ma = report.moistureAssessment
    recs = report.recommendations

    rw = ma.susceptibility.riskWindow
    sections = [
        NarrativeSection(
            id="assessment",
            text=f"{ma.current.headline}. {ma.susceptibility.headline}. "
                 f"Pierwsza ocena dotyczy dnia {report.analysisDate}, druga – ostatnich lat."
                 + (f" {rw.text}" if rw else ""),
            evidenceRefs=_refs(ma.current.evidenceRefs, ma.susceptibility.evidenceRefs,
                               rw.evidenceRefs if rw else []),
        ),
        NarrativeSection(
            id="causes",
            text=("Najważniejsze przyczyny: " + ", ".join(c.title.lower() for c in report.causes) + "."
                  if report.causes else "Nie widać wyraźnych przyczyn niedoboru wody."),
            evidenceRefs=_refs(*(c.evidenceRefs for c in report.causes)),
        ),
        NarrativeSection(
            id="retention",
            text=("Zacznij od zatrzymania wody na polu: " + ", ".join(r.title.lower() for r in recs.retention) + "."
                  if recs.retention else "Działania retencyjne nie są teraz pilne."),
            evidenceRefs=_refs(*(r.evidenceRefs for r in recs.retention)),
        ),
        NarrativeSection(
            id="agrotech",
            text=("W uprawie gleby pomogą: " + ", ".join(r.title.lower() for r in recs.agrotech) + "."
                  if recs.agrotech else "Zmiany w uprawie gleby nie są teraz pilne."),
            evidenceRefs=_refs(*(r.evidenceRefs for r in recs.agrotech)),
        ),
    ]
    if recs.irrigation:
        sections.append(NarrativeSection(
            id="irrigation",
            text="Nawadnianie rozważ dopiero po działaniach retencyjnych – i tylko w najbardziej wrażliwej fazie uprawy.",
            evidenceRefs=_refs(*(r.evidenceRefs for r in recs.irrigation)),
        ))
    return Narrative(sections=sections)
