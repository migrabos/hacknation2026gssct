"""Rank recommendations: retention → agrotech → irrigation (last, strict conditions)."""

from __future__ import annotations

from app.actions.catalog import ACTIONS, get_action
from app.engine.assess import AWC_LOW, HIGH_SENSITIVITY
from app.engine.facts import WATER_TYPE_PL, Facts, fmt
from app.schemas.evidence import Cause, MoistureAssessment, Recommendation, Recommendations

NO_IRRIGATION_NOTE = (
    "Przy obecnych warunkach nawadnianie nie jest konieczne. Lepsze i tańsze efekty dadzą działania "
    "z punktów 3 i 4 — zatrzymanie wody, która już spada na pole."
)


def _why(action_id: str, f: Facts, cause_ids: set[str]) -> tuple[str, list[str]]:
    """Plot-specific justification built only from facts. Returns (text, evidence refs)."""
    if action_id == "buffer_strips":
        if f.slope is not None:
            return (f"Działka ma spadek {fmt(f.slope)}%, więc przy ulewach woda spływa. "
                    "Pas zieleni ją spowalnia i pozwala wsiąknąć.", ["ev_slope"])
        return "Pas zieleni zatrzymuje wodę spływającą po ulewach i chroni glebę przed erozją.", []
    if action_id == "ditch_retention":
        if f.nearby_water and f.water_dist is not None:
            what = WATER_TYPE_PL.get(f.water_type or "", "ciek")
            return (f"Ok. {fmt(f.water_dist, 0)} m od działki jest {what}. Zatrzymanie w nim wody wiosną "
                    "podniesie jej poziom w glebie latem.", ["ev_water"])
        if f.nearby_water is None:
            return ("Wiosną woda z roztopów odpływa rowami, a latem jej brakuje. Nie mamy danych o rowach "
                    "przy tej działce – sprawdź na miejscu.", [])
        return ("Na mapach nie widać rowu przy działce, ale rowy bywają niezmapowane. Jeśli jest rów, "
                "warto zatrzymać w nim wodę.", ["ev_water"])
    if action_id == "small_pond":
        ds = f.dry_summers
        if ds and ds[0]:
            return (f"Suche lata powtarzają się tu często ({ds[0]} z {ds[1]}). Oczko zatrzyma wodę na miejscu "
                    "i poprawi wilgotność wokół.", ["ev_dry_summers"])
        return "Oczko zatrzymuje wodę z ulew i roztopów, zamiast pozwolić jej spłynąć z działki.", ["ev_precip_30d"]
    if action_id == "cover_crops":
        if f.soc is not None and f.soc < 2.0:
            return (f"Gleba ma mało próchnicy ({fmt(f.soc)}% węgla organicznego). Więcej próchnicy to więcej "
                    "wody zatrzymanej w glebie.", ["ev_soil_soc", "ev_soil_awc"])
        if f.awc is not None and f.awc < AWC_LOW:
            return (f"Gleba zatrzymuje tylko ok. {fmt(f.awc, 0)} mm wody. Okrywa ogranicza parowanie, "
                    "a korzenie międzyplonu poprawiają strukturę gleby.", ["ev_soil_awc"])
        return "Okrywa roślinna chroni glebę przed wysychaniem i wspiera retencję w profilu glebowym.", []
    if action_id == "residues":
        if f.sand is not None and f.sand >= 50:
            return (f"Resztki chronią glebę przed słońcem i wiatrem, więc mniej wody wyparowuje. "
                    f"To ważne na glebie z {fmt(f.sand, 0)}% piasku.", ["ev_soil_sand"])
        return ("Resztki chronią glebę przed słońcem i wiatrem, więc mniej wody wyparowuje.",
                ["ev_kbw_30d"])
    if action_id == "reduce_tillage":
        if f.awc is not None and f.awc < AWC_LOW:
            return (f"Gleba zatrzymuje tylko ok. {fmt(f.awc, 0)} mm wody. Każda orka dodatkowo ją przesusza.",
                    ["ev_soil_awc"])
        return "Każda orka wysusza glebę. Płytsza uprawa chroni strukturę i zapas wody.", ["ev_soil_awc"]
    if action_id == "irrigation_timing":
        missing = (f.precip30_normal or 0) - (f.precip30 or 0)
        text = (f"Brakuje ok. {fmt(missing, 0)} mm deszczu względem normy, a uprawa jest wrażliwa na suszę. "
                if missing > 0 else "Uprawa jest wrażliwa na suszę, a na działce jest teraz bardzo sucho. ")
        return text + "Najpierw jednak zadbaj o zatrzymanie wody na polu.", ["ev_precip_30d", "ev_crop_sensitivity"]
    return "", []


def rank_recommendations(*, assessment: MoistureAssessment, causes: list[Cause], f: Facts) -> Recommendations:
    if assessment is None:
        raise RuntimeError("Nie można rekomendować bez oceny wilgoci.")

    cause_ids = {c.id for c in causes}
    note: str | None = NO_IRRIGATION_NOTE
    if assessment.current.level == "insufficient_data":
        note = "Za mało danych, aby ocenić potrzebę nawadniania."
    moisture_risk = assessment.current.level in ("dry", "very_dry") or assessment.susceptibility.level != "low"
    if not moisture_risk and not cause_ids:
        return Recommendations(irrigation=None, irrigationNote=note)

    selected: dict[str, list[str]] = {"retention": [], "agrotech": []}
    for aid, meta in ACTIONS.items():
        if meta["kind"] == "irrigation":
            continue
        if set(meta["triggers"]) & cause_ids:
            selected[meta["kind"]].append(aid)

    # Ditch retention is only worth suggesting when water could be nearby (or unknown).
    if f.nearby_water is False and "ditch_retention" in selected["retention"] and "runoff" not in cause_ids:
        selected["retention"].remove("ditch_retention")
    if f.nearby_water and "ditch_retention" not in selected["retention"]:
        selected["retention"].append("ditch_retention")

    # Any moisture risk → always give at least one action in each bucket.
    if moisture_risk:
        if not selected["retention"]:
            selected["retention"] = ["small_pond"] if f.nearby_water is False else ["ditch_retention", "small_pond"]
        if not selected["agrotech"]:
            selected["agrotech"] = ["cover_crops", "residues"]

    def to_rec(aid: str, prio: int) -> Recommendation:
        a = get_action(aid)
        why, refs = _why(aid, f, cause_ids)
        return Recommendation(actionId=aid, title=a["titlePl"], description=a["descriptionPl"], why=why,  # type: ignore[arg-type]
                              priority=prio, costLevel=a["costLevel"], timeframe=a["timeframePl"], evidenceRefs=refs)

    def ordered(kind: str) -> list[Recommendation]:
        ids = sorted(set(selected[kind]), key=lambda i: ACTIONS[i]["basePriority"])
        return [to_rec(aid, i) for i, aid in enumerate(ids, start=1)]

    retention = ordered("retention")
    agrotech = ordered("agrotech")

    # Irrigation last: only when dry now AND sensitive crop AND retention already offered.
    irrigation: list[Recommendation] | None = None
    if assessment.current.level in ("dry", "very_dry") and f.crop_sens >= HIGH_SENSITIVITY and retention:
        irrigation = [to_rec("irrigation_timing", 1)]
        note = None
    elif assessment.current.level in ("dry", "very_dry"):
        note = ("Mimo suszy ta uprawa dobrze znosi niedobory wody, więc nawadnianie zwykle się nie opłaca. "
                "Skup się na działaniach z punktów 3 i 4.")

    return Recommendations(retention=retention, agrotech=agrotech, irrigation=irrigation, irrigationNote=note)
