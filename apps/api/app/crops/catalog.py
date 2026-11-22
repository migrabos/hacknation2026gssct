"""SMSR crop categories + drought sensitivity from FAO-33 Ky.

Catalog IDs and Polish names match IUNG SMSR rows exactly
(https://susza.iung.pulawy.pl/progi/), plus the non-SMSR option `brak`
(„Brak uprawy” — bare / fallow / nothing sown). Weights from FAO-33 Ky via
`fao.ky_to_sensitivity`. Live drought flag: `smsr.evaluate_smsr`.

Also carries seasonMonths / criticalMonths / kcMid (FAO-56) for irrigation timing.
"""

from __future__ import annotations

from typing import TypedDict

from app.crops.fao import effective_ky, fao_ky, ky_to_sensitivity
from app.schemas.evidence import RiskLevel


class CropEntry(TypedDict):
    id: str
    namePl: str
    droughtSensitivity: float
    faoKy: float | None          # strictly FAO-33, or None
    effectiveKy: float | None    # FAO or assumed orientation value
    kyFromFao: bool
    criticalPhasePl: str
    # Months (1–12) when the crop stands in the field and uses water – outside them watering is pointless.
    seasonMonths: tuple[int, ...]
    # Months of the most water-sensitive phase (subset of seasonMonths; same as criticalPhasePl).
    criticalMonths: tuple[int, ...]
    # Mid-season crop coefficient Kc (FAO-56, Allen et al. 1998, Table 12; rounded group value):
    # crop water need ≈ ET0 × Kc. Orientation value for the group, not variety-level.
    kcMid: float
    # Initial / early-season Kc (FAO-56 Table 12 orientation); used outside critical months.
    kcIni: float


def _crop(
    id_: str,
    name_pl: str,
    critical: str,
    *,
    season: tuple[int, ...],
    critical_months: tuple[int, ...],
    kc_mid: float,
    kc_ini: float | None = None,
) -> CropEntry:
    fao = fao_ky(id_)
    ky = effective_ky(id_)
    return {
        "id": id_,
        "namePl": name_pl,
        "droughtSensitivity": ky_to_sensitivity(ky),
        "faoKy": fao,
        "effectiveKy": ky,
        "kyFromFao": fao is not None,
        "criticalPhasePl": critical,
        "seasonMonths": season,
        "criticalMonths": critical_months,
        "kcMid": kc_mid,
        "kcIni": kc_ini if kc_ini is not None else round(kc_mid * 0.4, 2),
    }


# Exact SMSR categories (MRiRW 2019 / IUNG), in regulation table order.
CROPS: dict[str, CropEntry] = {
    "zboza_ozime": _crop(
        "zboza_ozime", "Zboża ozime",
        "najbardziej wrażliwe od strzelania w źdźbło do kłoszenia (V–VI)",
        season=(3, 4, 5, 6, 7), critical_months=(5, 6), kc_mid=1.15, kc_ini=0.4,
    ),
    "zboza_jare": _crop(
        "zboza_jare", "Zboża jare",
        "płytsze korzenie – wrażliwe na suchą wiosnę, zwłaszcza w V–VI",
        season=(4, 5, 6, 7), critical_months=(5, 6), kc_mid=1.15, kc_ini=0.3,
    ),
    "kukurydza_ziarno": _crop(
        "kukurydza_ziarno", "Kukurydza na ziarno",
        "najbardziej wrażliwa w lipcu i sierpniu (kwitnienie, zawiązywanie ziarna)",
        season=(5, 6, 7, 8, 9), critical_months=(7, 8), kc_mid=1.2, kc_ini=0.3,
    ),
    "kukurydza_kiszonka": _crop(
        "kukurydza_kiszonka", "Kukurydza na kiszonkę",
        "najbardziej wrażliwa w lipcu i sierpniu (kwitnienie, przyrost biomasy)",
        season=(5, 6, 7, 8, 9), critical_months=(7, 8), kc_mid=1.2, kc_ini=0.3,
    ),
    "rzepak": _crop(
        "rzepak", "Rzepak i rzepik",
        "wrażliwy przy wschodach jesienią (IX–X) i kwitnieniu wiosną (IV–V)",
        season=(3, 4, 5, 6, 9, 10), critical_months=(4, 5, 9, 10), kc_mid=1.1, kc_ini=0.35,
    ),
    "ziemniak": _crop(
        "ziemniak", "Ziemniak",
        "najbardziej wrażliwy od zawiązywania bulw (VI–VIII)",
        season=(5, 6, 7, 8, 9), critical_months=(6, 7, 8), kc_mid=1.15, kc_ini=0.5,
    ),
    "burak": _crop(
        "burak", "Burak cukrowy",
        "najbardziej wrażliwy w lipcu i sierpniu (przyrost korzenia)",
        season=(4, 5, 6, 7, 8, 9, 10), critical_months=(7, 8), kc_mid=1.2, kc_ini=0.35,
    ),
    "chmiel": _crop(
        "chmiel", "Chmiel",
        "najbardziej wrażliwy latem przy wzroście szyszek (VI–VIII)",
        season=(5, 6, 7, 8, 9), critical_months=(6, 7, 8), kc_mid=1.05, kc_ini=0.35,
    ),
    "tyton": _crop(
        "tyton", "Tytoń",
        "najbardziej wrażliwy od sadzenia do zbioru liści (V–VIII)",
        season=(5, 6, 7, 8, 9), critical_months=(6, 7, 8), kc_mid=1.1, kc_ini=0.4,
    ),
    "warzywa": _crop(
        "warzywa", "Warzywa gruntowe",
        "wrażliwe przez cały sezon (IV–IX), zwłaszcza przy sadzeniu i wzroście",
        season=(4, 5, 6, 7, 8, 9), critical_months=(4, 5, 6, 7, 8, 9), kc_mid=1.05, kc_ini=0.5,
    ),
    "krzewy": _crop(
        "krzewy", "Krzewy owocowe",
        "płytkie korzenie – wrażliwe od kwitnienia do zbioru (V–VIII)",
        season=(4, 5, 6, 7, 8), critical_months=(5, 6, 7, 8), kc_mid=0.9, kc_ini=0.5,
    ),
    "drzewa": _crop(
        "drzewa", "Drzewa owocowe",
        "najbardziej wrażliwe od kwitnienia do wzrostu owoców (V–VIII)",
        season=(4, 5, 6, 7, 8, 9), critical_months=(5, 6, 7, 8), kc_mid=0.95, kc_ini=0.5,
    ),
    "truskawki": _crop(
        "truskawki", "Truskawki",
        "płytkie korzenie – wrażliwe od kwitnienia do zbioru (V–VII)",
        season=(4, 5, 6, 7, 8), critical_months=(5, 6, 7), kc_mid=0.85, kc_ini=0.4,
    ),
    "straczkowe": _crop(
        "straczkowe", "Rośliny strączkowe",
        "najbardziej wrażliwe w kwitnieniu i zawiązywaniu strąków (VI–VII)",
        season=(4, 5, 6, 7, 8), critical_months=(6, 7), kc_mid=1.15, kc_ini=0.4,
    ),
    # Not an SMSR row — farmer has nothing sown (ugór / odłóg / przed siewem).
    "brak": {
        "id": "brak",
        "namePl": "Brak uprawy",
        "droughtSensitivity": 0.0,
        "faoKy": None,
        "effectiveKy": None,
        "kyFromFao": False,
        "criticalPhasePl": "brak uprawy – nie ma fazy krytycznej",
        "seasonMonths": (),
        "criticalMonths": (),
        "kcMid": 0.0,
        "kcIni": 0.0,
    },
}

# Legacy ids → SMSR ids (saved links / rehearsal plots / old fixtures).
CROP_ALIASES: dict[str, str] = {
    "pszenica": "zboza_ozime",
    "zboza": "zboza_ozime",
    "kukurydza": "kukurydza_ziarno",
    "sad": "drzewa",
    "jagodowe": "truskawki",
}

VALID_CROP_IDS = frozenset(CROPS.keys())
NO_CROP_ID = "brak"

# Crops typically on orchard / berry land (EGiB sad, plantacja).
ORCHARD_CROPS = frozenset({"drzewa", "krzewy", "truskawki"})


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
    """GET /crops — same shape as `Crop` in apps/web/lib/types.ts.

    „Brak uprawy” is listed first so farmers without a sown crop find it quickly;
    the rest stay in SMSR regulation order.
    """
    def row(c: CropEntry) -> dict:
        return {
            "id": c["id"],
            "name": c["namePl"],
            "droughtSensitivity": sensitivity_level(c["droughtSensitivity"]),
        }

    brak = CROPS.get(NO_CROP_ID)
    rest = [c for c in CROPS.values() if c["id"] != NO_CROP_ID]
    return ([row(brak)] if brak else []) + [row(c) for c in rest]
