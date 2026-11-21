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


CROPS: dict[str, CropEntry] = {
    "kukurydza": {"id": "kukurydza", "namePl": "Kukurydza", "droughtSensitivity": 0.75,
                  "criticalPhasePl": "najbardziej wrażliwa w lipcu i sierpniu (kwitnienie, zawiązywanie ziarna)"},
    "ziemniak": {"id": "ziemniak", "namePl": "Ziemniaki", "droughtSensitivity": 0.70,
                 "criticalPhasePl": "najbardziej wrażliwe od zawiązywania bulw (VI–VIII)"},
    "warzywa": {"id": "warzywa", "namePl": "Warzywa", "droughtSensitivity": 0.85,
                "criticalPhasePl": "wrażliwe przez cały sezon, zwłaszcza przy sadzeniu i wzroście"},
    "burak": {"id": "burak", "namePl": "Buraki cukrowe", "droughtSensitivity": 0.60,
              "criticalPhasePl": "najbardziej wrażliwe w lipcu i sierpniu (przyrost korzenia)"},
    "rzepak": {"id": "rzepak", "namePl": "Rzepak", "droughtSensitivity": 0.55,
               "criticalPhasePl": "wrażliwy przy wschodach jesienią i kwitnieniu wiosną"},
    "pszenica": {"id": "pszenica", "namePl": "Pszenica", "droughtSensitivity": 0.50,
                 "criticalPhasePl": "najbardziej wrażliwa od strzelania w źdźbło do kłoszenia (V–VI)"},
    "zboza": {"id": "zboza", "namePl": "Inne zboża (żyto, jęczmień, pszenżyto)", "droughtSensitivity": 0.45,
              "criticalPhasePl": "najbardziej wrażliwe od strzelania w źdźbło do kłoszenia (V–VI)"},
    "uzytki_zielone": {"id": "uzytki_zielone", "namePl": "Łąka / pastwisko", "droughtSensitivity": 0.55,
                       "criticalPhasePl": "odrost po pokosach latem słabnie przy braku wody"},
}

VALID_CROP_IDS = frozenset(CROPS.keys())


def sensitivity_level(x: float) -> RiskLevel:
    if x >= 0.65:
        return "high"
    if x >= 0.5:
        return "medium"
    return "low"


def get_crop(crop_id: str) -> CropEntry:
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
