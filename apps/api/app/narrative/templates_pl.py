"""Always-available Polish template narrative from structured Evidence fields."""

from __future__ import annotations

from app.schemas.evidence import Narrative, NarrativeSection, Report


def build_template_narrative(report: Report) -> Narrative:
    ma = report.moistureAssessment
    causes = report.causes
    recs = report.recommendations

    cause_txt = (
        ", ".join(c.labelPl for c in causes)
        if causes
        else "brak wyraźnych etykiet przyczyn (dane częściowe)"
    )

    retention_txt = (
        ", ".join(r.titlePl for r in recs.retention)
        if recs.retention
        else "brak pilnych działań retencyjnych"
    )
    agrotech_txt = (
        ", ".join(r.titlePl for r in recs.agrotech)
        if recs.agrotech
        else "brak pilnych działań agrotechnicznych"
    )

    sections: list[NarrativeSection] = [
        NarrativeSection(
            id="ocena",
            titlePl="Ocena sytuacji wodnej",
            bodyPl=(
                f"Aktualna sytuacja: {ma.current.level} "
                f"(score {ma.current.score0to100}/100). "
                f"{ma.current.summaryPl} "
                f"Wieloletnia podatność: {ma.multiYearSusceptibility.level} "
                f"(score {ma.multiYearSusceptibility.score0to100}/100). "
                f"{ma.multiYearSusceptibility.summaryPl} "
                f"Pewność oceny: {ma.confidence0to1:.2f}."
            ),
        ),
        NarrativeSection(
            id="przyczyny",
            titlePl="Przyczyny",
            bodyPl=f"Wskazane przyczyny: {cause_txt}.",
        ),
        NarrativeSection(
            id="retencja",
            titlePl="Retencja",
            bodyPl=(
                f"Rekomendacje retencyjne (najpierw zatrzymaj wodę): {retention_txt}."
            ),
        ),
        NarrativeSection(
            id="agrotech",
            titlePl="Agrotechnika",
            bodyPl=f"Działania glebowe / agrotechniczne: {agrotech_txt}.",
        ),
    ]

    if recs.irrigation:
        irr = ", ".join(r.titlePl for r in recs.irrigation)
        sections.append(
            NarrativeSection(
                id="nawadnianie",
                titlePl="Nawadnianie",
                bodyPl=(
                    f"Nawadnianie rozważane dopiero po retencji i agrotechnice: {irr}."
                ),
            )
        )

    sources_txt = ", ".join(s.name for s in report.sources) or "brak"
    missing_txt = "; ".join(report.missingData) if report.missingData else "brak zgłoszonych braków"
    sections.append(
        NarrativeSection(
            id="zrodla",
            titlePl="Źródła i braki danych",
            bodyPl=(
                f"Źródła: {sources_txt}. "
                f"Braki / ograniczenia: {missing_txt}. "
                f"Ograniczenia metody: {'; '.join(report.limitations[:2])}."
            ),
        )
    )

    return Narrative(mode="template", sections=sections)
