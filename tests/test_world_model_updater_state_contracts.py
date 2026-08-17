"""No-double contracts for pure world-model updater state transitions."""

from types import SimpleNamespace

from src.game.world_model_updater import WorldModelUpdater
import pytest

pytestmark = [pytest.mark.unit]



def _state(week: int, data: dict) -> SimpleNamespace:
    return SimpleNamespace(week=week, world_model_data=data)


def test_location_move_and_existing_confirm_preserve_real_state():
    state = _state(6, {"character_locations": {"王五": {"location": "深圳", "region": "深圳"}}})

    WorldModelUpdater.process_location_updates(
        state,
        [
            {"action": "move", "character": "李四", "to": "上海", "mode": "travel"},
            {"action": "confirm", "character": "王五", "location": "东莞"},
        ],
    )

    assert state.world_model_data["character_locations"]["李四"]["since_week"] == 6
    assert state.world_model_data["character_locations"]["李四"]["travel_mode"] == "travel"
    assert state.world_model_data["character_locations"]["王五"]["location"] == "东莞"


def test_career_transition_keeps_history_and_falls_back_invalid_level():
    state = _state(
        8,
        {"career_records": {"李四": {"current_job": "助理", "employer": "甲公司", "level": "junior", "since_week": 2, "history": []}}},
    )

    WorldModelUpdater.process_career_updates(
        state,
        [{"action": "promote", "character": "李四", "new_role": "经理", "employer": "乙公司", "level": "invalid"}],
    )

    record = state.world_model_data["career_records"]["李四"]
    assert record["current_job"] == "经理"
    assert record["history"][0]["job"] == "助理"
    assert record["since_week"] == 8


def test_resolved_commitment_and_causal_chain_age_out():
    state = _state(
        30,
        {
            "active_commitments": [{"description": "答应参加仪式", "parties": ["王五"], "status": "pending"}],
            "causal_chains": [{"cause": "帮助王五", "resolved": False}],
        },
    )

    WorldModelUpdater.process_commitment_updates(
        state, [{"action": "fulfilled", "description": "参加仪式", "parties": ["王五"]}]
    )
    state.week = 41
    WorldModelUpdater.process_commitment_updates(state, [{"action": "new"}])
    WorldModelUpdater.process_causal_updates(state, [{"action": "resolved", "cause": "帮助王五", "resolution": "获赠谢礼"}])
    state.week = 62
    WorldModelUpdater.process_causal_updates(state, [{"action": "new"}])

    assert state.world_model_data["active_commitments"] == []
    assert state.world_model_data["causal_chains"] == []
