"""Canonical history adapter for collection entity recognition.

Daily timeline records live in ``day_history`` while the legacy round-based
timeline uses ``round_history``.  Keeping the selection and current-event
deduplication here prevents each caller from silently recognizing a different
story slice.
"""

from copy import deepcopy
from typing import Any, Dict, List, Mapping


def _has_story_content(entry: Mapping[str, Any]) -> bool:
    return any(
        entry.get(field)
        for field in (
            "event_description",
            "story_text",
            "story_continuation",
            "summary",
        )
    )


def _same_event(left: Mapping[str, Any], right: Mapping[str, Any]) -> bool:
    left_id = left.get("event_id")
    right_id = right.get("event_id")
    if left_id and right_id:
        if str(left_id) == str(right_id):
            return True

    left_text = left.get("event_description") or left.get("story_text")
    right_text = right.get("event_description") or right.get("story_text")
    if left_text and right_text and str(left_text) == str(right_text):
        return True

    return (
        left.get("week") == right.get("week")
        and left.get("round") == right.get("round")
        and _has_story_content(left)
        and _has_story_content(right)
    )


def build_entity_recognition_history(player_state: Any) -> List[Dict[str, Any]]:
    """Return the complete canonical story slice for collection recognition.

    ``day_history`` is authoritative whenever it has content.  Legacy saves
    without daily records continue to use ``round_history``.  The currently
    displayed event is appended only when it is not already committed in the
    selected history.
    """

    daily_history = getattr(player_state, "day_history", None) or []
    legacy_history = getattr(player_state, "round_history", None) or []
    has_daily_story = any(
        isinstance(entry, Mapping) and _has_story_content(entry)
        for entry in daily_history
    )
    source = daily_history if has_daily_story else legacy_history
    history = [deepcopy(dict(entry)) for entry in source if isinstance(entry, Mapping)]

    current_event = getattr(player_state, "current_event_data", None)
    if not isinstance(current_event, Mapping):
        return history

    event_description = current_event.get("event_description") or current_event.get(
        "story_text"
    )
    if not event_description:
        return history

    current_entry: Dict[str, Any] = {
        "week": getattr(player_state, "week", 0),
        "round": getattr(player_state, "current_round", 0),
        "event_description": str(event_description),
    }
    if current_event.get("event_id"):
        current_entry["event_id"] = current_event["event_id"]

    if not any(_same_event(entry, current_entry) for entry in history):
        history.append(current_entry)
    return history
