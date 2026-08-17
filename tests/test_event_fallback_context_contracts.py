"""Provider-free round fallback context contracts."""

from typing import Any

from src.game.round.event_generator import RoundEventGenerator
import pytest

pytestmark = [pytest.mark.unit]



class _PlayerState:
    def __init__(self, player_name: str, week: int, character_settings: dict[str, Any]):
        self.player_name = player_name
        self.week = week
        self.character_settings = character_settings

    def to_dict(self) -> dict[str, Any]:
        return {"player_name": self.player_name, "character_settings": self.character_settings}


def _generator(state: _PlayerState, language: str) -> RoundEventGenerator:
    return RoundEventGenerator(
        player_state_getter=lambda: state,
        ai_generator=None,
        language_getter=lambda: language,
        character_introduction_service=None,
        summary_selector=None,
        relationship_service=None,
    )


def test_chinese_round_fallback_keeps_canonical_context_and_relationship_effect():
    state = _PlayerState(
        "林岚",
        4,
        {
            "occupation": "社区规划师",
            "era_description": "近未来城市",
            "relationships": {"key_people": [{"name": "周老师", "role": "导师"}]},
        },
    )

    event = _generator(state, "zh")._generate_fallback_event()

    assert "林岚" in event.event_description
    assert "近未来城市" in event.event_description
    assert "社区规划师" in event.event_description
    assert "周老师" in event.event_description
    assert event.options[0].text == "联系周老师确认下一步"
    assert event.options[0].effects["relationships"] == {"周老师": 2}


def test_english_round_fallback_keeps_canonical_context_and_relationship_effect():
    state = _PlayerState(
        "Alex",
        1,
        {
            "profession": "data analyst",
            "era_name": "near-future city",
            "relationships": {"key_people": [{"name": "Maya", "relationship": "mentor"}]},
        },
    )

    event = _generator(state, "en")._generate_fallback_event()

    assert "Alex" in event.event_description
    assert "near-future city" in event.event_description
    assert "data analyst" in event.event_description
    assert "Maya" in event.event_description
    assert event.options[0].text == "Check in with Maya"
    assert event.options[0].effects["relationships"] == {"Maya": 2}


def test_round_fallback_uses_generic_event_only_when_no_context_exists():
    event = _generator(_PlayerState("", 0, {}), "en")._generate_fallback_event()

    assert event.event_description == "A quiet day with nothing special happening."
    assert len(event.options) == 3
