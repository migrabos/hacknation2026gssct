"""Fixed crop IDs + drought sensitivity weights (0–1, higher = more sensitive)."""

from __future__ import annotations

from typing import TypedDict

from app.schemas.evidence import RiskLevel


class CropEntry(TypedDict):
    id: str
    namePl: str
    droughtSensitivity: float
    # Farmer-language note on when the crop needs water most (shown as evidence comparison)
    criticalPhasePl: str
    # Months (1–12) when the crop stands in the field and uses water – outside them watering is pointless.
    seasonMonths: tuple[int, ...]
    # Months of the most water-sensitive phase (subset of seasonMonths; same as criticalPhasePl).
    criticalMonths: tuple[int, ...]
    # Mid-season crop coefficient Kc (FAO-56, Allen et al. 1998, Table 12; rounded group value):
    # crop water need ≈ ET0 × Kc. Orientation value for the group, not variety-level.
    kcMid: float


# Groups follow the IUNG drought-monitoring crop groups (System Monitoringu Suszy Rolniczej):
# split by what changes the water story (winter vs spring sowing, critical phase), not by species.
# Weights ordered after FAO-33 yield response factors (Ky): maize 1.25, spring wheat 1.15,
# peas 1.15, potato 1.1, winter wheat 1.05, sugar beet 1.0.
CROPS: dict[str, CropEntry] = {
    "zboza_ozime": {"id": "zboza_ozime", "namePl": "Zboża ozime (pszenica, pszenżyto, żyto, jęczmień ozimy)",
                    "droughtSensitivity": 0.45,
                    "criticalPhasePl": "najbardziej wrażliwe od strzelania w źdźbło do kłoszenia (V–VI)",
                    "seasonMonths": (3, 4, 5, 6, 7), "criticalMonths": (5, 6), "kcMid": 1.15},
    "zboza_jare": {"id": "zboza_jare", "namePl": "Zboża jare (jęczmień jary, owies, pszenica jara)",
                   "droughtSensitivity": 0.60,
                   "criticalPhasePl": "płytsze korzenie – wrażliwe na suchą wiosnę, zwłaszcza w V–VI",
                   "seasonMonths": (4, 5, 6, 7), "criticalMonths": (5, 6), "kcMid": 1.15},
    "kukurydza": {"id": "kukurydza", "namePl": "Kukurydza (na ziarno i kiszonkę)", "droughtSensitivity": 0.75,
                  "criticalPhasePl": "najbardziej wrażliwa w lipcu i sierpniu (kwitnienie, zawiązywanie ziarna)",
                  "seasonMonths": (5, 6, 7, 8, 9), "criticalMonths": (7, 8), "kcMid": 1.2},
    "rzepak": {"id": "rzepak", "namePl": "Rzepak", "droughtSensitivity": 0.55,
               "criticalPhasePl": "wrażliwy przy wschodach jesienią (IX–X) i kwitnieniu wiosną (IV–V)",
               "seasonMonths": (3, 4, 5, 6, 9, 10), "criticalMonths": (4, 5, 9, 10), "kcMid": 1.1},
    "burak": {"id": "burak", "namePl": "Buraki cukrowe", "droughtSensitivity": 0.60,
              "criticalPhasePl": "najbardziej wrażliwe w lipcu i sierpniu (przyrost korzenia)",
              "seasonMonths": (4, 5, 6, 7, 8, 9, 10), "criticalMonths": (7, 8), "kcMid": 1.2},
    "ziemniak": {"id": "ziemniak", "namePl": "Ziemniaki", "droughtSensitivity": 0.75,
                 "criticalPhasePl": "najbardziej wrażliwe od zawiązywania bulw (VI–VIII)",
                 "seasonMonths": (5, 6, 7, 8, 9), "criticalMonths": (6, 7, 8), "kcMid": 1.15},
    "straczkowe": {"id": "straczkowe", "namePl": "Strączkowe (groch, bobik, soja, łubin)",
                   "droughtSensitivity": 0.60,
                   "criticalPhasePl": "najbardziej wrażliwe w kwitnieniu i zawiązywaniu strąków (VI–VII)",
                   "seasonMonths": (4, 5, 6, 7, 8), "criticalMonths": (6, 7), "kcMid": 1.15},
    "warzywa": {"id": "warzywa", "namePl": "Warzywa gruntowe", "droughtSensitivity": 0.85,
                "criticalPhasePl": "wrażliwe przez cały sezon (IV–IX), zwłaszcza przy sadzeniu i wzroście",
                "seasonMonths": (4, 5, 6, 7, 8, 9), "criticalMonths": (4, 5, 6, 7, 8, 9), "kcMid": 1.05},
    "sad": {"id": "sad", "namePl": "Sad (jabłonie, wiśnie, śliwy)", "droughtSensitivity": 0.80,
            "criticalPhasePl": "najbardziej wrażliwy od kwitnienia do wzrostu owoców (V–VIII)",
            "seasonMonths": (4, 5, 6, 7, 8, 9), "criticalMonths": (5, 6, 7, 8), "kcMid": 0.95},
    "jagodowe": {"id": "jagodowe", "namePl": "Truskawki i krzewy owocowe", "droughtSensitivity": 0.85,
                 "criticalPhasePl": "płytkie korzenie – wrażliwe od kwitnienia do zbioru (V–VII)",
                 "seasonMonths": (4, 5, 6, 7, 8), "criticalMonths": (5, 6, 7), "kcMid": 0.9},
    "uzytki_zielone": {"id": "uzytki_zielone", "namePl": "Łąka / pastwisko", "droughtSensitivity": 0.55,
                       "criticalPhasePl": "odrost po pokosach latem (V–VIII) słabnie przy braku wody",
                       "seasonMonths": (4, 5, 6, 7, 8, 9), "criticalMonths": (5, 6, 7, 8), "kcMid": 0.95},
}

# Old IDs (before the IUNG-group split) — still accepted so saved links / rehearsal plots keep working.
CROP_ALIASES: dict[str, str] = {
    "pszenica": "zboza_ozime",
    "zboza": "zboza_ozime",
}

VALID_CROP_IDS = frozenset(CROPS.keys())


def sensitivity_level(x: float) -> RiskLevel:
    if x >= 0.65:
        return "high"
    if x >= 0.5:
        return "medium"
    return "low"


MONTH_PL = ("styczeń", "luty", "marzec", "kwiecień", "maj", "czerwiec", "lipiec", "sierpień",
            "wrzesień", "październik", "listopad", "grudzień")


def in_season(crop: CropEntry, month: int) -> bool:
    return month in crop["seasonMonths"]


def in_critical_phase(crop: CropEntry, month: int) -> bool:
    return month in crop["criticalMonths"]


def get_crop(crop_id: str) -> CropEntry:
    crop_id = CROP_ALIASES.get(crop_id, crop_id)
    if crop_id not in CROPS:
        raise ValueError(
            f"Nieznany cropId '{crop_id}'. Dozwolone: {', '.join(sorted(VALID_CROP_IDS))}."
        )
    return CROPS[crop_id]


def list_crops() -> list[dict]:
    """GET /crops — same shape as `Crop` in apps/web/lib/types.ts."""
    return [
        {"id": c["id"], "name": c["namePl"], "droughtSensitivity": sensitivity_level(c["droughtSensitivity"])}
        for c in CROPS.values()
    ]
