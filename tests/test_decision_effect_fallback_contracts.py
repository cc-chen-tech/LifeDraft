import pytest

from src.game.decisions import (
    _generate_fallback_result,
    calculate_character_effects,
    get_character_interaction_context,
    process_decision,
)
from src.game.state import CharacterState, PlayerState


class _FailingResultProvider:
    def generate_completion(self, **_kwargs: object) -> str:
        raise RuntimeError("provider unavailable")


def test_character_effects_derive_positive_negative_and_explicit_overrides() -> None:
    player = PlayerState()

    effects = calculate_character_effects(
        {
            "relationships": {"Alex River": 7, "Blair Stone": -5},
            "character_effects": {
                "Alex River": {"respect": 9},
                "Casey Reed": {"mood": 4},
            },
        },
        player,
    )

    assert effects["Alex River"] == {
        "affinity": 7,
        "trust": 2,
        "respect": 9,
        "mood": 3,
    }
    assert effects["Blair Stone"] == {
        "affinity": -5,
        "trust": -3,
        "respect": -2,
        "mood": -5,
    }
    assert effects["Casey Reed"] == {"mood": 4}


def test_interaction_context_includes_only_known_characters() -> None:
    player = PlayerState()
    player.characters["Alex River"] = CharacterState(
        name="Alex River", role="architect", affinity=68, trust=57
    ).model_dump()

    assert get_character_interaction_context(player, []) == ""
    assert get_character_interaction_context(player, ["missing"]) == ""

    context = get_character_interaction_context(player, ["Alex River", "missing"])

    assert context.startswith("【本次互动涉及的角色】")
    assert "Alex River" in context
    assert "architect" in context


def test_process_decision_rejects_invalid_option_indices() -> None:
    player = PlayerState()
    options = [{"text": "Choose", "effects": {}}]

    with pytest.raises(ValueError, match="Invalid option index: -1"):
        process_decision(player, "Event", -1, options, generate_result_text=False)

    with pytest.raises(ValueError, match="Invalid option index: 1"):
        process_decision(player, "Event", 1, options, generate_result_text=False)


def test_provider_free_decision_returns_localized_effect_fallback() -> None:
    player = PlayerState(week=2, current_round=1)
    option = {
        "text": "Practice after work",
        "effects": {"energy": -3, "mood": 2, "knowledge": 4},
    }

    result = process_decision(player, "A quiet evening", 0, [option], language="en")

    assert result["success"] is True
    assert "Energy -3" in result["result_text"]
    assert "Mood +2" in result["result_text"]
    assert "Knowledge +4" in result["result_text"]
    assert player.decision_history[-1]["choice"] == "Practice after work"


def test_failing_result_provider_degrades_to_chinese_fallback() -> None:
    player = PlayerState(week=3)
    option = {"text": "帮助邻居", "effects": {"mood": -2}}

    result = process_decision(
        player,
        "邻居需要帮助",
        0,
        [option],
        language="zh",
        ai_generator=_FailingResultProvider(),
    )

    assert result["success"] is True
    assert "情绪-2" in result["result_text"]


def test_fallback_result_omits_unchanged_resources() -> None:
    assert _generate_fallback_result({}, "en") == "Your choice has consequences: ."
    assert _generate_fallback_result({"knowledge": 2}, "zh") == "你的选择带来了后果：学识+2。"
