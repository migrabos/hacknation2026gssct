"""Rank recommendations: retention → agrotech → irrigation (last, strict conditions)."""

from __future__ import annotations

from typing import NamedTuple

from app.actions.catalog import ACTIONS, get_action
from app.engine.assess import AWC_LOW, HIGH_SENSITIVITY
from app.crops.catalog import MONTH_PL, NO_CROP_ID
from app.engine.facts import SHOW_WATER_PCT, WATER_TYPE_PL, Facts, fmt
from app.schemas.evidence import Cause, MoistureAssessment, Recommendation, Recommendations

# Single irrigation dose (mm): light soil holds less, so smaller and more frequent doses.
# Orientation ranges after common Polish extension guidance (gleby lekkie 15–20 mm, średnie i cięższe 25–30 mm).
DOSE_LIGHT_SOIL = (15, 20)
DOSE_MEDIUM_SOIL = (25, 30)
DOSE_UNKNOWN_SOIL = (20, 25)
# Interval between doses = dose / daily crop water use (ET0 × Kc per day), clamped to a sane range.
MIN_INTERVAL_DAYS = 2
MAX_INTERVAL_DAYS = 14


def irrigation_interval(dose: tuple[int, int], daily_use: float | None) -> tuple[int, int] | None:
    """Days between doses so each dose covers what the crop used since the last one."""
    if not daily_use or daily_use <= 0:
        return None
    clamp = lambda d: max(MIN_INTERVAL_DAYS, min(MAX_INTERVAL_DAYS, int(d)))  # floor = water a bit early
    return clamp(dose[0] / daily_use), clamp(dose[1] / daily_use)


def _range(lo: int, hi: int) -> str:
    return f"{lo}" if lo == hi else f"{lo}–{hi}"

class IrrigationPlan(NamedTuple):
    dose: tuple[int, int]            # mm = litres per m²
    every: tuple[int, int] | None    # days between doses
    daily: float | None              # crop water use, mm/day
    light_soil: bool | None


def irrigation_plan(f: Facts) -> IrrigationPlan:
    light = None if f.awc is None else f.awc < AWC_LOW
    dose = DOSE_UNKNOWN_SOIL if light is None else DOSE_LIGHT_SOIL if light else DOSE_MEDIUM_SOIL
    need = f.crop_water_need30
    daily = need / 30 if need else None
    return IrrigationPlan(dose, irrigation_interval(dose, daily), daily, light)


def _m3(x: float) -> str:
    """Water volume for farmers: round to 10 m³ above 100 m³."""
    return fmt(round(x, -1) if x >= 100 else round(x), 0)


def _irrigation_why(f: Facts) -> tuple[str, list[str]]:
    """Concrete plan in litres per m² (1 mm = 1 l/m²) and m³ per hectare / per plot."""
    refs = ["ev_crop_sensitivity"]
    deficit = f.crop_deficit30
    if deficit is not None and deficit > 0:
        lines = [f"Przez ostatnie 30 dni uprawie zabrakło ok. {fmt(deficit, 0)} litrów wody na każdy metr "
                 f"kwadratowy pola (potrzebowała ok. {fmt(f.crop_water_need30 or 0, 0)} l/m², "
                 f"a spadło {fmt(f.precip30 or 0, 0)} l/m² deszczu)."]
        refs.insert(0, "ev_crop_deficit")
    else:
        missing = (f.precip30_normal or 0) - (f.precip30 or 0)
        lines = [f"Spadło ok. {fmt(missing, 0)} litrów deszczu na m² mniej niż zwykle, a uprawa jest wrażliwa "
                 "na suszę." if missing > 0 else "Uprawa jest wrażliwa na suszę, a na działce jest teraz bardzo sucho."]
        refs.insert(0, "ev_precip_30d")

    plan = irrigation_plan(f)
    lo, hi = plan.dose
    how_much = (f"• Ile: jednorazowo {_range(lo, hi)} litrów wody na m² (to samo co {_range(lo, hi)} mm opadu), "
                f"czyli {_range(lo * 10, hi * 10)} m³ na hektar")
    if f.area_ha:
        how_much += f" – na całą działkę ({fmt(f.area_ha, 2)} ha) ok. {_m3(lo * 10 * f.area_ha)}–{_m3(hi * 10 * f.area_ha)} m³"
    if plan.light_soil is True:
        how_much += ". Więcej naraz nie podawaj – lekka gleba tego nie zatrzyma, woda ucieknie w głąb."
        refs.append("ev_soil_awc")
    elif plan.light_soil is False:
        how_much += ". Gleba zatrzyma taką dawkę w zasięgu korzeni."
        refs.append("ev_soil_awc")
    else:
        how_much += " (brak danych o glebie – to wartość pośrednia)."
    lines.append(how_much)

    if plan.every and plan.daily:
        lines.append(f"• Jak często: co {_range(*plan.every)} dni, nie codziennie – tyle czasu uprawa zużywa jedną "
                     f"dawkę (teraz ok. {fmt(plan.daily)} litra na m² dziennie). Podlewaj rano lub wieczorem, "
                     "żeby mniej wody wyparowało.")
    else:
        lines.append("• Jak często: nie codziennie – rzadziej, ale pełną dawką, gdy gleba na głębokości ok. 10 cm "
                     "jest sucha w dotyku. Podlewaj rano lub wieczorem.")
    lines.append(f"• Kiedy pominąć lub skończyć: jeśli spadnie co najmniej {lo} l/m² deszczu, pomiń najbliższe "
                 "podlewanie; skończ, gdy opady wrócą do normy albo minie okres krytyczny uprawy.")
    lines.append("Najpierw jednak zadbaj o zatrzymanie wody na polu (punkty 3 i 4).")
    return "\n".join(lines), refs


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
        return (f"Mapa wskazuje {WATER_TYPE_PL[f.water_type]} w odległości ok. {fmt(f.water_dist, 0)} m "
                "od działki. Sprawdź w terenie, czy odprowadza wodę z tego pola.", ["ev_water"])
    if action_id == "small_pond":
        if f.spot_drop is not None:
            where = " Leży ono przy granicy działki – sprawdź, czy woda nie ucieka do sąsiada lub rowu." \
                if f.spot_near_edge else ""
            return (f"Według modelu terenu najniższe miejsce działki leży {fmt(f.spot_drop)} m niżej niż najwyższe "
                    "(zaznaczone na mapie). Tam naturalnie spływa deszczówka – to najlepsze miejsce na oczko "
                    f"lub zagłębienie retencyjne.{where}", ["ev_low_spot"])
        if _standing_water(f):
            return (f"Na zdjęciu satelitarnym z {f.ndvi_date} ok. {fmt(f.water_pct, 0)}% działki pokrywa stojąca "
                    "woda. To naturalne najniższe miejsce – oczko zbierze tam wodę bez dużych prac ziemnych, "
                    "a reszta pola przestanie być podtapiana.", ["ev_standing_water"])
        ds = f.dry_summers
        if ds and ds[0]:
            return (f"Suche lata powtarzają się tu często ({ds[0]} z {ds[1]}). Oczko zatrzyma wodę na miejscu "
                    "i poprawi wilgotność wokół.", ["ev_dry_summers"])
        return "Oczko zatrzymuje wodę z ulew i roztopów, zamiast pozwolić jej spłynąć z działki.", ["ev_precip_30d"]
    if action_id == "cover_crops":
        if "bare_soil" in cause_ids:
            return (f"Na zdjęciu satelitarnym z {f.ndvi_date} ok. {fmt(f.bare_pct, 0)}% działki to goła gleba. "
                    "Międzyplon okryje ją do wiosny: mniej wody wyparuje, a deszcz nie zmyje gleby.",
                    ["ev_bare_soil"])
        if f.soc is not None and f.soc < 2.0:
            return (f"Gleba ma mało próchnicy ({fmt(f.soc)}% węgla organicznego). Więcej próchnicy to więcej "
                    "wody zatrzymanej w glebie.", ["ev_soil_soc", "ev_soil_awc"])
        if f.awc is not None and f.awc < AWC_LOW:
            return (f"Gleba zatrzymuje tylko ok. {fmt(f.awc, 0)} mm wody. Okrywa ogranicza parowanie, "
                    "a korzenie międzyplonu poprawiają strukturę gleby.", ["ev_soil_awc"])
        return "Okrywa roślinna chroni glebę przed wysychaniem i wspiera retencję w profilu glebowym.", []
    if action_id == "residues":
        if "bare_soil" in cause_ids:
            return (f"Satelita pokazuje, że ok. {fmt(f.bare_pct, 0)}% działki stoi bez okrywy. Resztki pożniwne "
                    "na powierzchni działają jak ściółka – gleba wolniej wysycha.", ["ev_bare_soil"])
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
        return _irrigation_why(f)
    return "", []


def _standing_water(f: Facts) -> bool:
    return f.water_pct is not None and f.water_pct >= SHOW_WATER_PCT


def rank_recommendations(*, assessment: MoistureAssessment, causes: list[Cause], f: Facts) -> Recommendations:
    if assessment is None:
        raise RuntimeError("Nie można rekomendować bez oceny wilgoci.")

    cause_ids = {c.id for c in causes}
    note: str | None = NO_IRRIGATION_NOTE
    if assessment.current.level == "insufficient_data":
        note = "Za mało danych, aby ocenić potrzebę nawadniania."
    moisture_risk = assessment.current.level in ("dry", "very_dry") or assessment.susceptibility.level in ("medium", "high")
    if not moisture_risk and not cause_ids and not _standing_water(f):
        return Recommendations(irrigation=None, irrigationNote=note)

    selected: dict[str, list[str]] = {"retention": [], "agrotech": []}
    for aid, meta in ACTIONS.items():
        if meta["kind"] == "irrigation":
            continue
        if set(meta["triggers"]) & cause_ids:
            selected[meta["kind"]].append(aid)

    if f.nearby_water and f.water_type in ("ditch", "drain") and f.water_dist is not None:
        selected["retention"].append("ditch_retention")

    # Standing water seen from space = ready-made spot for a pond, wet or dry year alike.
    if _standing_water(f) and "small_pond" not in selected["retention"]:
        selected["retention"].append("small_pond")

    # Any moisture risk → always give at least one action in each bucket.
    if moisture_risk:
        if not selected["retention"]:
            selected["retention"] = ["small_pond"]
        if not selected["agrotech"]:
            selected["agrotech"] = ["cover_crops", "residues"]

    def to_rec(aid: str, prio: int, timeframe: str | None = None) -> Recommendation:
        a = get_action(aid)
        why, refs = _why(aid, f, cause_ids)
        return Recommendation(actionId=aid, title=a["titlePl"], description=a["descriptionPl"], why=why,  # type: ignore[arg-type]
                              priority=prio, costLevel=a["costLevel"], timeframe=timeframe or a["timeframePl"],
                              evidenceRefs=refs)

    def ordered(kind: str) -> list[Recommendation]:
        ids = sorted(set(selected[kind]), key=lambda i: ACTIONS[i]["basePriority"])
        return [to_rec(aid, i) for i, aid in enumerate(ids, start=1)]

    retention = ordered("retention")
    agrotech = ordered("agrotech")

    # Irrigation last: only when dry now AND sensitive crop AND in the crop's season
    # AND retention already offered. „Brak uprawy” never gets irrigation.
    irrigation: list[Recommendation] | None = None
    dry_now = assessment.current.level in ("dry", "very_dry")
    if f.crop_id == NO_CROP_ID:
        note = ("Na działce nie ma uprawy, więc nawadnianie nie ma sensu. Skup się na zatrzymaniu wody "
                "i okrywie gleby (punkty 3 i 4). Gdy posadzisz roślinę – uruchom raport ponownie "
                "z konkretną uprawą.")
    elif dry_now and f.in_season is False:
        month = MONTH_PL[f.month - 1] if f.month else "ten miesiąc"
        note = (f"Dzień oceny ({month}) wypada poza sezonem wzrostu tej uprawy, więc nawadnianie teraz nie ma "
                f"sensu. Sprawdź sytuację ponownie przed okresem krytycznym ({f.crop_phase_pl}). "
                "Teraz najwięcej da zatrzymanie wody z jesieni i zimy – działania z punktów 3 i 4.")
    elif dry_now and f.crop_sens >= HIGH_SENSITIVITY and retention:
        plan = irrigation_plan(f)
        how_often = f", co {_range(*plan.every)} dni" if plan.every else ""
        timeframe = (f"teraz (trwa najbardziej wrażliwa faza){how_often}, rano lub wieczorem"
                     if f.in_critical_phase
                     else f"w okresie krytycznym ({f.crop_phase_pl}){how_often}"
                     if f.crop_phase_pl else None)
        irrigation = [to_rec("irrigation_timing", 1, timeframe)]
        note = None
    elif dry_now:
        note = ("Mimo suszy ta uprawa dobrze znosi niedobory wody, więc nawadnianie zwykle się nie opłaca. "
                "Skup się na działaniach z punktów 3 i 4.")

    return Recommendations(retention=retention, agrotech=agrotech, irrigation=irrigation, irrigationNote=note)
