"""Contracts for deterministic world-model update reconciliation."""

from src.game.state import PlayerState
from src.game.world_model_updater import WorldModelUpdater
import pytest

pytestmark = [pytest.mark.unit]



def test_new_location_and_career_records_include_current_week_defaults() -> None:
    state = PlayerState(week=14)

    WorldModelUpdater.process_location_updates(
        state, [{"action": "confirm", "character": "Ada", "location": "上海", "reason": "入职"}]
    )
    WorldModelUpdater.process_career_updates(
        state,
        [{"action": "hire", "character": "Ada", "new_role": "编辑", "employer": "晨报", "level": "senior"}],
    )

    assert state.world_model_data["character_locations"]["Ada"] == {
        "location": "上海", "region": "上海", "since_week": 14,
        "travel_mode": "resident", "reason": "入职",
    }
    assert state.world_model_data["career_records"]["Ada"] == {
        "current_job": "编辑", "employer": "晨报", "level": "senior", "since_week": 14, "history": [],
    }


def test_commitment_reconciliation_matches_shared_party_and_action_words() -> None:
    state = PlayerState(week=14)
    state.world_model_data["active_commitments"] = [
        {"description": "答应参加母亲的仪式", "parties": ["Ada", "母亲"], "status": "pending"}
    ]

    WorldModelUpdater.process_commitment_updates(
        state,
        [{"action": "fulfilled", "description": "完成了和母亲约定的出席", "parties": ["母亲"]}],
    )

    assert state.world_model_data["active_commitments"][0]["status"] == "fulfilled"
    assert state.world_model_data["active_commitments"][0]["resolved_week"] == 14
