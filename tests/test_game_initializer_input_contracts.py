import pytest

from config.settings import settings
from src.game.game_initializer import (
    GameInitializer,
    _coerce_initial_wealth_amount,
    _initial_wealth_from_settings,
    extract_initial_wealth_from_settings,
)


def test_initial_wealth_coercion_handles_numeric_formatted_and_invalid_values() -> None:
    assert _coerce_initial_wealth_amount(True) is None
    assert _coerce_initial_wealth_amount(-50) == 0
    assert _coerce_initial_wealth_amount(125.9) == 125
    assert _coerce_initial_wealth_amount(1_500_000) == 1_000_000
    assert _coerce_initial_wealth_amount(None) is None
    assert _coerce_initial_wealth_amount(()) is None
    assert _coerce_initial_wealth_amount("  ") is None
    assert _coerce_initial_wealth_amount("￥") is None
    assert _coerce_initial_wealth_amount("3.75万") == 37_500
    assert _coerce_initial_wealth_amount("¥12,345元") == 12_345
    assert _coerce_initial_wealth_amount("middle class") is None


def test_explicit_wealth_uses_first_numeric_supported_field() -> None:
    assert extract_initial_wealth_from_settings({"wealth": "middle class"}) is None
    assert (
        extract_initial_wealth_from_settings(
            {
                "wealth": {
                    "wealth": "not numeric",
                    "starting_wealth": "3.2万",
                    "initial_wealth_amount": 44_000,
                }
            }
        )
        == 32_000
    )
    assert (
        extract_initial_wealth_from_settings(
            {
                "wealth": {
                    "wealth": "20,000元",
                    "starting_wealth": "3.2万",
                }
            }
        )
        == 20_000
    )


def test_initial_wealth_falls_back_to_configured_default_without_numeric_value() -> None:
    assert _initial_wealth_from_settings({"wealth": {"initial_wealth": False}}) == (
        settings.INITIAL_WEALTH
    )
    assert _initial_wealth_from_settings({}) == settings.INITIAL_WEALTH


def test_relationship_normalization_canonicalizes_supported_and_invalid_shapes() -> None:
    initializer = GameInitializer()
    people = [{"name": "Alex River", "role": "architect"}]

    assert initializer._normalize_relationships_settings(people) == {
        "key_people": people
    }
    assert initializer._normalize_relationships_settings(None) == {"key_people": []}
    assert initializer._normalize_relationships_settings("Alex River") == {
        "key_people": []
    }
    assert initializer._normalize_relationships_settings(
        {"key_people": ("Alex River",), "source": "generated"}
    ) == {"key_people": [], "source": "generated"}
    assert initializer._normalize_relationships_settings(
        {"key_people": people, "source": "generated"}
    ) == {"key_people": people, "source": "generated"}


def test_game_initialization_rejects_missing_required_inputs_before_persistence() -> None:
    initializer = GameInitializer()

    with pytest.raises(ValueError, match="character_settings is required"):
        initializer.initialize_game_from_settings({}, "Alex River", "Build a studio")

    with pytest.raises(ValueError, match="player_name is required"):
        initializer.initialize_game_from_settings(
            {"relationships": {}}, "", "Build a studio"
        )
