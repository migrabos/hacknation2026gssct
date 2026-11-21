"""Fixed action IDs + Polish copy + eligibility metadata.

Order in report: retention → agrotech → irrigation (last, optional).
"""

from __future__ import annotations

from typing import Literal, TypedDict

ActionKind = Literal["retention", "agrotech", "irrigation"]


class ActionEntry(TypedDict):
    id: str
    kind: ActionKind
    titlePl: str
    whyTemplatePl: str
    # Causes that boost eligibility
    triggers: list[str]
    # Base priority within kind (1 = highest)
    basePriority: int


ACTIONS: dict[str, ActionEntry] = {
    "small_pond": {
        "id": "small_pond",
        "kind": "retention",
        "titlePl": "Małe oczko / zbiornik retencyjny",
        "whyTemplatePl": "Zatrzymuje wodę opadową na działce i łagodzi krótkie niedobory.",
        "triggers": ["precip_deficit", "runoff"],
        "basePriority": 1,
    },
    "buffer_strips": {
        "id": "buffer_strips",
        "kind": "retention",
        "titlePl": "Strefy buforowe / pasy zieleni",
        "whyTemplatePl": "Spowalnia spływ powierzchniowy i zwiększa infiltrację na skraju pola.",
        "triggers": ["runoff"],
        "basePriority": 2,
    },
    "ditch_retention": {
        "id": "ditch_retention",
        "kind": "retention",
        "titlePl": "Retencja w rowach melioracyjnych",
        "whyTemplatePl": "Kontrolowane spiętrzanie w rowach wydłuża czas zatrzymania wody.",
        "triggers": ["runoff", "precip_deficit"],
        "basePriority": 3,
    },
    "residues": {
        "id": "residues",
        "kind": "agrotech",
        "titlePl": "Pozostawianie resztek pożniwnych",
        "whyTemplatePl": "Mulcz ogranicza parowanie i poprawia strukturę gleby.",
        "triggers": ["low_soil_storage", "precip_deficit"],
        "basePriority": 1,
    },
    "cover_crops": {
        "id": "cover_crops",
        "kind": "agrotech",
        "titlePl": "Międzyplony / okrywa roślinna",
        "whyTemplatePl": "Żywa okrywa chroni glebę i wspiera retencję w profilu glebowym.",
        "triggers": ["low_soil_storage", "runoff"],
        "basePriority": 2,
    },
    "reduce_tillage": {
        "id": "reduce_tillage",
        "kind": "agrotech",
        "titlePl": "Ograniczenie intensywnej uprawy",
        "whyTemplatePl": "Mniejsza intensywność uprawy chroni strukturę i pojemność wodną gleby.",
        "triggers": ["low_soil_storage"],
        "basePriority": 3,
    },
    "irrigation_timing": {
        "id": "irrigation_timing",
        "kind": "irrigation",
        "titlePl": "Nawadnianie — tylko w krytycznych fazach",
        "whyTemplatePl": "Przy silnym niedoborze i wrażliwej uprawie rozważ podlewanie w kluczowych fazach wzrostu.",
        "triggers": ["precip_deficit", "crop_sensitivity"],
        "basePriority": 1,
    },
}

VALID_ACTION_IDS = frozenset(ACTIONS.keys())
RETENTION_IDS = frozenset(a["id"] for a in ACTIONS.values() if a["kind"] == "retention")
AGROTECH_IDS = frozenset(a["id"] for a in ACTIONS.values() if a["kind"] == "agrotech")
IRRIGATION_IDS = frozenset(a["id"] for a in ACTIONS.values() if a["kind"] == "irrigation")


def get_action(action_id: str) -> ActionEntry:
    if action_id not in ACTIONS:
        raise KeyError(f"Unknown action id: {action_id}")
    return ACTIONS[action_id]


def list_actions() -> list[dict]:
    return [dict(a) for a in ACTIONS.values()]
