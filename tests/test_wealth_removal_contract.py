"""Behavior contracts for the wealth-system removal."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError

from src.ai.models import EventOption
from src.api.schemas import GenerateSettingRequest
from src.game.achievements import AchievementEngine
from src.game.endings import EndingEvaluator
from src.game.game_initializer import GameInitializer
from src.game.life_review import LifeReviewGenerator
from src.game.state import PlayerState
from src.game.weekly_summary import WeeklySummaryGenerator

LEGACY_KEYS = {"wealth", "wealth_ledger", "_active_wealth_transaction_id"}


def _assert_no_legacy_keys(value):
    if isinstance(value, dict):
        assert LEGACY_KEYS.isdisjoint(value)
        for nested in value.values():
            _assert_no_legacy_keys(nested)
    elif isinstance(value, list):
        for nested in value:
            _assert_no_legacy_keys(nested)


def _state(**overrides):
    values = {
        "player_name": "契约测试",
        "energy": 60,
        "mood": 60,
        "knowledge": 60,
        "week": 10,
        "age": 25,
    }
    values.update(overrides)
    return PlayerState(**values)


def test_player_state_recursively_drops_legacy_wealth_keys():
    state = PlayerState.from_dict(
        {
            "player_name": "旧存档",
            "wealth": 88_000,
            "wealth_ledger": {"balance_snapshot": 88_000},
            "character_settings": {
                "wealth": {"wealth": 88_000},
                "family": {
                    "description": "经营一家小店",
                    "audit": [{"_active_wealth_transaction_id": "legacy-1"}],
                },
            },
            "round_history": [
                {"effects": {"energy": 3, "wealth": 500}, "wealth_ledger": {}}
            ],
        }
    )

    assert not hasattr(state, "wealth")
    dumped = state.to_dict()
    _assert_no_legacy_keys(dumped)
    assert dumped["character_settings"]["family"]["description"] == "经营一家小店"


def test_generated_event_effects_use_three_resource_allowlist():
    option = EventOption(
        text="承接临时项目",
        effects={
            "energy": -5,
            "mood": 2,
            "knowledge": 4,
            "wealth": 1_000,
            "relationships": {"合伙人": 5},
            "unexpected": 99,
        },
    )

    assert option.effects == {"energy": -5, "mood": 2, "knowledge": 4}


def test_setting_request_rejects_wealth_during_pydantic_validation():
    with pytest.raises(ValidationError):
        GenerateSettingRequest(
            setting_type="wealth",
            player_name="小林",
            life_vision="经营一家温暖的小店",
        )


def test_new_game_state_and_character_settings_have_no_wealth_keys():
    db = MagicMock()
    db.create_game.return_value = 42
    initializer = GameInitializer(game_db=db, language="zh")

    game_loop, game_id = initializer.initialize_game_from_settings(
        character_settings={
            "age": {"age": 26},
            "family": {"family_economy": "普通", "description": "经营一家小店"},
            "wealth": {"wealth": 50_000, "description": "多年积蓄"},
        },
        player_name="小林",
        life_vision="把小店经营下去",
    )

    assert game_id == 42
    _assert_no_legacy_keys(db.create_game.call_args.kwargs["initial_state"])
    _assert_no_legacy_keys(game_loop.player_state.to_dict())


def test_old_preset_response_is_recursively_sanitized(client):
    legacy_preset = {
        "preset_id": 7,
        "preset_name": "旧预设",
        "player_name": "阿青",
        "life_vision": "照顾家人与邻里",
        "character_settings": {
            "wealth": {"wealth": 12_000},
            "family": {
                "description": "靠手艺维生",
                "legacy": [{"wealth_ledger": {"transactions": []}}],
            },
        },
        "created_at": None,
    }
    db = MagicMock()
    db.load_character_preset.return_value = legacy_preset

    with patch("src.api.routers.presets.get_db", return_value=db):
        response = client.get("/api/presets/7")

    assert response.status_code == 200
    payload = response.json()
    _assert_no_legacy_keys(payload)
    assert payload["character_settings"]["family"]["description"] == "靠手艺维生"


def test_weekly_summary_keeps_qualitative_economics_without_wealth_state():
    generator = MagicMock()
    generator.generate_completion.return_value = (
        "这一周，小店客流有所回暖，但生活仍需精打细算。"
    )
    summary = WeeklySummaryGenerator(
        ai_generator=generator, language="zh"
    ).generate_summary(
        week=3,
        previous_state={"energy": 55, "mood": 55, "knowledge": 55, "wealth": 1},
        current_state=_state(energy=60, mood=58, knowledge=62),
        decisions=[{"choice": "调整营业时间"}],
    )

    assert summary["summary_text"] == "这一周，小店客流有所回暖，但生活仍需精打细算。"
    assert summary["changes"] == {"energy": 5, "mood": 3, "knowledge": 7}
    _assert_no_legacy_keys(summary["final_state"])


def test_ending_priority_and_public_stats_use_three_resources():
    evaluator = EndingEvaluator()

    assert (
        evaluator.evaluate_ending(_state(energy=39, mood=39, knowledge=39))[
            "ending_type"
        ]
        == "struggling"
    )
    assert (
        evaluator.evaluate_ending(_state(energy=65, mood=65, knowledge=81))[
            "ending_type"
        ]
        == "scholar"
    )
    social = _state(relationships={"甲": 71, "乙": 72, "丙": 73})
    assert evaluator.evaluate_ending(social)["ending_type"] == "social"
    balanced = evaluator.evaluate_ending(_state(energy=45, mood=45, knowledge=45))
    assert balanced["ending_type"] == "balanced"
    assert set(balanced["final_stats"]) == {
        "energy",
        "mood",
        "knowledge",
        "relationships",
    }
    assert "wealthy" not in evaluator.ENDING_TYPES


def test_achievement_rules_use_only_three_resources():
    engine = AchievementEngine(language="zh")
    ids = {definition["id"] for definition in engine.ALL_ACHIEVEMENTS}
    assert "steady_climber" not in ids
    assert "rags_to_riches" not in ids

    equilibrium = _state(energy=50, mood=54, knowledge=55)
    assert engine._check_condition("perfect_equilibrium", equilibrium)
    neutral = _state(energy=50, mood=50, knowledge=50)
    assert engine._check_condition("true_neutral", neutral)

    history = [
        {"effects": {"energy": 5, "mood": 5, "knowledge": 5}} for _ in range(5)
    ] + [{"effects": {"energy": -2, "mood": -2, "knowledge": -2}} for _ in range(5)]
    tragic = _state(mood=30, round_history=history)
    assert engine._check_condition("tragic_hero", tragic)

    legendary = _state(round_history=[{"effects": {}} for _ in range(50)])
    assert engine._check_condition("legendary_tale", legendary)


def test_life_review_resource_curves_expose_exactly_three_resources():
    state = _state(
        week=2,
        round_history=[
            {"effects": {"energy": -2, "mood": 3, "knowledge": 4, "wealth": 999}}
        ],
    )
    review = LifeReviewGenerator(language="zh").generate(state, [])

    assert set(review["resource_curves"]) == {"energy", "mood", "knowledge"}
