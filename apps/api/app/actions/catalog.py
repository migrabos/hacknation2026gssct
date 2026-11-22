"""Fixed action IDs + Polish copy + eligibility metadata.

Order in report: retention → agrotech → irrigation (last, optional).
IDs must match `ActionId` in apps/web/lib/types.ts. Do not invent new ones outside this catalog.
"""

from __future__ import annotations

from typing import Literal, TypedDict

ActionKind = Literal["retention", "agrotech", "irrigation"]
Cost = Literal["low", "medium", "high"]


class ActionEntry(TypedDict):
    id: str
    kind: ActionKind
    titlePl: str
    descriptionPl: str
    costLevel: Cost
    timeframePl: str
    # Causes that make the action eligible
    triggers: list[str]
    # Base priority within kind (1 = highest)
    basePriority: int


ACTIONS: dict[str, ActionEntry] = {
    "buffer_strips": {
        "id": "buffer_strips", "kind": "retention",
        "titlePl": "Pas zieleni na dole pola",
        "descriptionPl": "Zostaw lub wysiej pas trawy albo krzewów (szerokość 5–10 m) wzdłuż dolnej krawędzi działki "
                         "lub w poprzek spadku.",
        "costLevel": "low", "timeframePl": "jesień lub wiosna",
        "triggers": ["runoff"], "basePriority": 1,
    },
    "ditch_retention": {
        "id": "ditch_retention", "kind": "retention",
        "titlePl": "Zatrzymaj wodę w rowie",
        "descriptionPl": "Na rowie melioracyjnym przy działce ustaw zastawkę lub próg, żeby woda z roztopów "
                         "i ulew nie odpływała od razu. Uzgodnij to ze spółką wodną.",
        "costLevel": "medium", "timeframePl": "przed zimą",
        "triggers": [], "basePriority": 2,  # Selected from mapped ditch evidence in rank.py.
    },
    "small_pond": {
        "id": "small_pond", "kind": "retention",
        "titlePl": "Małe oczko wodne lub zbiornik",
        "descriptionPl": "W najniższym, podmokłym miejscu działki zrób małe oczko, które zbiera wodę deszczową "
                         "i z roztopów.",
        "costLevel": "high", "timeframePl": "po zbiorach",
        "triggers": ["precip_deficit", "runoff"], "basePriority": 3,
    },
    "cover_crops": {
        "id": "cover_crops", "kind": "agrotech",
        "titlePl": "Międzyplon po zbiorach",
        "descriptionPl": "Po zbiorach wysiej międzyplon (np. gorczycę, facelię). Okrywa glebę, ogranicza parowanie "
                         "i dodaje próchnicy.",
        "costLevel": "low", "timeframePl": "sierpień–wrzesień",
        "triggers": ["low_soil_storage", "runoff", "bare_soil"], "basePriority": 1,
    },
    "residues": {
        "id": "residues", "kind": "agrotech",
        "titlePl": "Zostaw resztki pożniwne",
        "descriptionPl": "Pozostaw rozdrobnione resztki roślin na powierzchni pola, zamiast je usuwać lub palić.",
        "costLevel": "low", "timeframePl": "po zbiorach",
        "triggers": ["precip_deficit", "low_soil_storage", "bare_soil"], "basePriority": 2,
    },
    "reduce_tillage": {
        "id": "reduce_tillage", "kind": "agrotech",
        "titlePl": "Mniej orki",
        "descriptionPl": "Zamiast głębokiej orki stosuj płytką uprawę bezorkową tam, gdzie to możliwe.",
        "costLevel": "medium", "timeframePl": "od następnego sezonu",
        "triggers": ["low_soil_storage", "runoff"], "basePriority": 3,
    },
    "irrigation_timing": {
        "id": "irrigation_timing", "kind": "irrigation",
        "titlePl": "Podlewanie tylko w kluczowym momencie",
        "descriptionPl": "Jeśli masz dostęp do wody, podlewaj w najbardziej wrażliwej fazie uprawy – "
                         "rzadziej, ale pełną dawką. Ile litrów i co ile dni – niżej.",
        "costLevel": "high", "timeframePl": "w najbliższych 2–3 tygodniach",
        "triggers": ["precip_deficit", "crop_sensitivity"], "basePriority": 1,
    },
}

VALID_ACTION_IDS = frozenset(ACTIONS.keys())


def get_action(action_id: str) -> ActionEntry:
    if action_id not in ACTIONS:
        raise KeyError(f"Unknown action id: {action_id}")
    return ACTIONS[action_id]
