from src.ai.models import EventOption, GameEvent
from src.game.daily_generation_intent import (
    is_complete_daily_event,
    resolve_daily_generation_intent,
)


def _complete_event() -> GameEvent:
    return GameEvent(
        event_id="evt-today",
        revision=3,
        story_date="2026-08-16",
        event_description="今天的完整故事。",
        options=[
            EventOption(text="继续追查", effects={}),
            EventOption(text="暂时撤退", effects={}),
        ],
    )


def test_replace_without_current_event_resolves_to_generate_missing() -> None:
    resolution = resolve_daily_generation_intent("replace_current", None)

    assert resolution.resolved_mode == "generate_missing"
    assert resolution.base_event_id == ""
    assert resolution.base_revision == 0


def test_replace_with_complete_event_resolves_to_atomic_replacement() -> None:
    resolution = resolve_daily_generation_intent("replace_current", _complete_event())

    assert resolution.resolved_mode == "replace_current"
    assert resolution.base_event_id == "evt-today"
    assert resolution.base_revision == 3


def test_ensure_with_complete_event_returns_existing_story() -> None:
    resolution = resolve_daily_generation_intent("ensure_current", _complete_event())

    assert resolution.resolved_mode == "return_existing"


def test_incomplete_persisted_event_is_treated_as_missing() -> None:
    incomplete = {
        "event_id": "evt-partial",
        "revision": 2,
        "story_date": "2026-08-16",
        "event_description": "只有正文，没有可选择的行动。",
        "options": [],
    }

    assert is_complete_daily_event(incomplete) is False
    assert (
        resolve_daily_generation_intent("replace_current", incomplete).resolved_mode
        == "generate_missing"
    )
