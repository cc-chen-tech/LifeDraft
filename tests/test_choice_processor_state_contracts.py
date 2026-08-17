"""Deterministic state contracts for round choice processing."""

from src.game.round.choice_processor import RoundChoiceProcessor
from src.game.state import PlayerState
import pytest

pytestmark = [pytest.mark.unit]



class RecordingEffectsService:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, dict[object, object], dict[object, object]]] = []

    def generate_custom_choice_effects(
        self,
        event_description: str,
        custom_text: str,
        character_settings: dict[object, object],
        current_state: dict[object, object],
    ) -> dict[str, int]:
        self.calls.append(
            (event_description, custom_text, character_settings, current_state)
        )
        return {"knowledge": 1}


def _processor(state: PlayerState) -> RoundChoiceProcessor:
    return RoundChoiceProcessor(
        player_state_getter=lambda: state,
        ai_generator=object(),
        language_getter=lambda: "zh",
        story_service=object(),
        current_event_getter=lambda: None,
        current_event_setter=lambda event: None,
    )


def _state(**overrides: object) -> PlayerState:
    values: dict[str, object] = {
        "player_name": "林岚",
        "week": 3,
        "current_round": 2,
        "energy": 2,
        "mood": 99,
        "knowledge": 100,
        "character_settings": {},
    }
    values.update(overrides)
    return PlayerState(**values)


def test_effect_normalization_clamps_resources_and_reports_applied_deltas() -> None:
    state = _state()
    processor = _processor(state)

    effects, warnings = processor._normalize_effects_for_current_state(
        {"energy": -9, "mood": 6, "knowledge": 3}
    )

    assert effects == {"energy": -2, "mood": 1, "knowledge": 0}
    by_resource = {warning["resource"]: warning for warning in warnings}
    assert by_resource["energy"]["reason"] == "insufficient_resource"
    assert by_resource["energy"]["requested_delta"] == -9
    assert by_resource["energy"]["applied_delta"] == -2
    assert by_resource["mood"]["reason"] == "resource_cap"
    assert by_resource["mood"]["applied_delta"] == 1
    assert by_resource["knowledge"]["applied_delta"] == 0


def test_effect_normalization_without_state_returns_independent_input() -> None:
    requested = {"energy": -4, "mood": 3, "relationships": {"陈晓雨": 2}}
    processor = RoundChoiceProcessor(
        player_state_getter=lambda: None,
        ai_generator=object(),
        language_getter=lambda: "zh",
        story_service=object(),
        current_event_getter=lambda: None,
        current_event_setter=lambda event: None,
    )

    effects, warnings = processor._normalize_effects_for_current_state(requested)
    effects["energy"] = 0

    assert requested["energy"] == -4
    assert effects["mood"] == 3
    assert warnings == []


def test_custom_effects_without_state_delegate_empty_context() -> None:
    service = RecordingEffectsService()
    processor = RoundChoiceProcessor(
        player_state_getter=lambda: None,
        ai_generator=object(),
        language_getter=lambda: "zh",
        story_service=service,
        current_event_getter=lambda: None,
        current_event_setter=lambda event: None,
    )

    effects = processor._generate_custom_choice_effects("面试结束", "整理复盘")

    assert effects == {"knowledge": 1}
    assert service.calls == [("面试结束", "整理复盘", {}, {})]
