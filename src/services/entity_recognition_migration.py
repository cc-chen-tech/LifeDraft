"""Repair persisted collection entities without calling an LLM."""

from copy import deepcopy
from typing import Any, Dict, List, Tuple

from src.game.state import PlayerState
from src.services.collection_entity_types import (
    classify_known_entity_name,
    is_invalid_character_name,
)
from src.services.entity_recognition_history import build_entity_recognition_history
from src.services.entity_recognition_materializer import materialize_recognized_entities
from src.services.entity_recognition_service import EntityRecognitionService


def repair_collection_state(
    state_data: Dict[str, Any],
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Return repaired state and an auditable change report.

    The repair is deterministic: it removes high-confidence cross-category
    entries and backfills only names found by the recognition service's
    explicit object/place vocabulary.  It intentionally does not invent new
    people from old prose.
    """

    before = deepcopy(state_data)
    state = PlayerState.from_dict(deepcopy(state_data))

    removed_characters: List[str] = []
    removed_items: List[str] = []
    removed_landmarks: List[str] = []

    valid_person_names = tuple(
        name for name in state.characters if classify_known_entity_name(name) is None
    )
    for name in list(state.characters):
        if is_invalid_character_name(name, valid_person_names):
            state.characters.pop(name, None)
            state.relationships.pop(name, None)
            removed_characters.append(name)

    # Older saves can retain a relationship entry after a malformed character
    # record was removed.  Keep the compatibility map aligned with the NPC
    # collection as well.
    for name in list(state.relationships):
        if is_invalid_character_name(name, valid_person_names):
            state.relationships.pop(name, None)

    for name in list(state.items):
        if classify_known_entity_name(name) in {"landmark", "non_person"}:
            state.items.pop(name, None)
            removed_items.append(name)

    for name in list(state.landmarks):
        if classify_known_entity_name(name) in {"item", "non_person"}:
            state.landmarks.pop(name, None)
            removed_landmarks.append(name)

    history = build_entity_recognition_history(state)
    service = EntityRecognitionService(None)
    recognized = service.recognize_from_history(
        round_history=history,
        existing_items=list(state.items),
        existing_characters=list(state.characters),
        existing_landmarks=list(state.landmarks),
        min_appearances=1,
        language="zh",
    )
    recognized_without_people = {
        "items": recognized.get("items", []),
        "characters": [],
        "landmarks": recognized.get("landmarks", []),
    }
    materialized = materialize_recognized_entities(state, recognized_without_people)

    repaired = state.to_dict()
    report = {
        "removed_characters": removed_characters,
        "removed_items": removed_items,
        "removed_landmarks": removed_landmarks,
        "added_items": materialized["added_items"],
        "added_landmarks": materialized["added_landmarks"],
        "would_change": repaired != before,
    }
    return repaired, report
