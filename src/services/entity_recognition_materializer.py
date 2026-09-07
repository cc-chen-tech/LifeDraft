"""Materialize recognized entities into a player's collection state."""

from typing import Any, Dict, Iterable, List, Optional, Set

from src.game.state import CharacterState, PlayerState
from src.game.state.item_state import ItemState
from src.game.state.landmark_state import LandmarkState
from src.services.collection_entity_types import (
    classify_known_entity_name,
    is_invalid_character_name,
)


def _first_context(entity: Dict[str, Any]) -> str:
    contexts = entity.get("appear_contexts")
    return str(contexts[0]) if isinstance(contexts, list) and contexts else ""


def _safe_int(
    value: Any,
    default: int,
    minimum: int,
    maximum: Optional[int] = None,
) -> int:
    if isinstance(value, bool):
        return default
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    parsed = max(minimum, parsed)
    return min(maximum, parsed) if maximum is not None else parsed


def _candidate_names(values: Iterable[Any]) -> Set[str]:
    return {
        str(value.get("name", "")).strip()
        for value in values
        if isinstance(value, dict) and str(value.get("name", "")).strip()
    }


def materialize_recognized_entities(
    player_state: PlayerState,
    entities: Dict[str, List[Dict[str, Any]]],
    source_event_id: str = "",
) -> Dict[str, List[str]]:
    """Add valid recognition output to ``player_state`` idempotently.

    ``source_event_id`` is accepted by the pipeline so callers can associate
    the report with a daily record.  State dictionaries are already keyed by
    entity name, so replaying a post-processing job is naturally idempotent.
    """

    del source_event_id  # reserved for a future provenance field in the state schema
    added_items: List[str] = []
    added_characters: List[str] = []
    added_landmarks: List[str] = []

    item_candidates = entities.get("items", []) or []
    character_candidates = entities.get("characters", []) or []
    landmark_candidates = entities.get("landmarks", []) or []
    candidate_types: Dict[str, Set[str]] = {}
    for entity_type, values in (
        ("item", item_candidates),
        ("character", character_candidates),
        ("landmark", landmark_candidates),
    ):
        for name in _candidate_names(values):
            candidate_types.setdefault(name, set()).add(entity_type)
    ambiguous_names = {
        name
        for name, types in candidate_types.items()
        if len(types) > 1 and classify_known_entity_name(name) is None
    }

    item_names = set(player_state.items)
    character_names = set(player_state.characters)
    landmark_names = set(player_state.landmarks)

    for item_data in item_candidates:
        if not isinstance(item_data, dict):
            continue
        item_name = str(item_data.get("name", "")).strip()
        item_kind = classify_known_entity_name(item_name)
        if (
            not item_name
            or item_name in item_names
            or item_kind in {"landmark", "non_person"}
            or item_name in character_names
            or item_name in landmark_names
            or item_name in ambiguous_names
        ):
            continue
        item = ItemState(
            name=item_name,
            description=str(item_data.get("description", "")),
            importance=item_data.get("importance", "normal"),
            category=item_data.get("category", "other"),
            acquired_week=player_state.week,
            acquired_context=_first_context(item_data),
            is_key_item=item_data.get("importance") == "critical",
            image_generated=False,
            description_generated=True,
        )
        player_state.add_item(item)
        item_names.add(item_name)
        added_items.append(item_name)

    character_settings = player_state.character_settings or {}
    player_name = player_state.player_name or character_settings.get("player_name", "")
    for character_data in character_candidates:
        if not isinstance(character_data, dict):
            continue
        character_name = str(character_data.get("name", "")).strip()
        if (
            not character_name
            or character_name == player_name
            or character_name in player_state.characters
            or character_name in item_names
            or character_name in landmark_names
            or character_name in ambiguous_names
            or is_invalid_character_name(character_name, tuple(character_names))
        ):
            continue
        character = CharacterState(
            name=character_name,
            role=character_data.get("role", "故事人物"),
            relationship_desc=character_data.get("description", ""),
            affinity=_safe_int(character_data.get("affinity", 50), 50, 0, 100),
        )
        player_state.add_character(character)
        character_names.add(character_name)
        added_characters.append(character_name)

    for landmark_data in landmark_candidates:
        if not isinstance(landmark_data, dict):
            continue
        landmark_name = str(landmark_data.get("name", "")).strip()
        landmark_kind = classify_known_entity_name(landmark_name)
        if (
            not landmark_name
            or landmark_name in landmark_names
            or landmark_kind in {"item", "non_person"}
            or landmark_name in item_names
            or landmark_name in character_names
            or landmark_name in ambiguous_names
        ):
            continue
        landmark = LandmarkState(
            name=landmark_name,
            description=str(landmark_data.get("description", "")),
            category=landmark_data.get("category", "other"),
            importance=landmark_data.get("importance", "normal"),
            first_appear_week=player_state.week,
            appear_count=_safe_int(landmark_data.get("appear_count", 1), 1, 1),
            last_appear_week=player_state.week,
            context=_first_context(landmark_data),
            is_key_location=landmark_data.get("importance") == "critical",
            image_generated=False,
        )
        player_state.add_landmark(landmark)
        landmark_names.add(landmark_name)
        added_landmarks.append(landmark_name)

    return {
        "added_items": added_items,
        "added_characters": added_characters,
        "added_landmarks": added_landmarks,
    }
