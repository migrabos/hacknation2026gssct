"""Fixed crop IDs + drought sensitivity weights (0–1, higher = more sensitive)."""

from __future__ import annotations

from typing import TypedDict


class CropEntry(TypedDict):
    id: str
    namePl: str
    droughtSensitivity: float


CROPS: dict[str, CropEntry] = {
    "kukurydza": {
        "id": "kukurydza",
        "namePl": "Kukurydza",
        "droughtSensitivity": 0.75,
    },
    "ziemniak": {
        "id": "ziemniak",
        "namePl": "Ziemniak",
        "droughtSensitivity": 0.70,
    },
    "warzywa": {
        "id": "warzywa",
        "namePl": "Warzywa",
        "droughtSensitivity": 0.85,
    },
    "zboza": {
        "id": "zboza",
        "namePl": "Zboża",
        "droughtSensitivity": 0.45,
    },
    "rzepak": {
        "id": "rzepak",
        "namePl": "Rzepak",
        "droughtSensitivity": 0.55,
    },
}

VALID_CROP_IDS = frozenset(CROPS.keys())


def get_crop(crop_id: str) -> CropEntry:
    if crop_id not in CROPS:
        raise ValueError(
            f"Nieznany cropId '{crop_id}'. Dozwolone: {', '.join(sorted(VALID_CROP_IDS))}."
        )
    return CROPS[crop_id]


def list_crops() -> list[dict]:
    return [dict(c) for c in CROPS.values()]
