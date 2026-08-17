"""Provider-free regression contracts for world-model update guards."""

from src.game.state import PlayerState
from src.game.world_model_updater import WorldModelUpdater
import pytest

pytestmark = [pytest.mark.unit]



def test_incomplete_world_model_updates_do_not_create_partial_records() -> None:
    state = PlayerState(week=19)

    WorldModelUpdater.process_location_updates(
        state,
        [
            {"action": "move"},
            {"character": "林岚"},
            {"action": "move", "character": "林岚"},
        ],
    )
    WorldModelUpdater.process_career_updates(
        state,
        [{"action": "promote"}, {"character": "林岚"}],
    )
    WorldModelUpdater.process_commitment_updates(
        state,
        [{"action": "new"}, {"action": "fulfilled"}],
    )
    WorldModelUpdater.process_causal_updates(
        state,
        [
            {"action": "new", "cause": "签署合同"},
            {"action": "resolved"},
        ],
    )

    assert state.world_model_data["character_locations"] == {}
    assert state.world_model_data["career_records"] == {}
    assert state.world_model_data["active_commitments"] == []
    assert state.world_model_data["causal_chains"] == []


def test_scheduled_event_cleanup_only_removes_stale_terminal_events() -> None:
    state = PlayerState(week=30)
    state.scheduled_events = [
        {"event_id": "pending", "status": "pending", "scheduled_week": 1},
        {"event_id": "old-triggered", "status": "triggered", "scheduled_week": 19},
        {"event_id": "recent-merged", "status": "merged", "scheduled_week": 20},
        {"event_id": "old-skipped", "status": "skipped", "scheduled_week": 18},
    ]

    assert WorldModelUpdater.cleanup_triggered_scheduled_events(None) == 0
    assert WorldModelUpdater.cleanup_triggered_scheduled_events(state) == 2
    assert [event["event_id"] for event in state.scheduled_events] == [
        "pending",
        "recent-merged",
    ]


def test_preset_role_substitute_is_not_promoted_from_story_effects() -> None:
    state = PlayerState(
        relationships={},
        character_settings={
            "relationships": {
                "key_people": [{"name": "陆昊然", "role": "导师", "affinity": 60}]
            }
        },
    )

    WorldModelUpdater.sync_story_characters_to_settings(
        state,
        story_text="新导师苏婉清把复盘文档递给主角，要求她不要再找陆昊然确认需求。",
        relationships_in_effects={"苏婉清": 70},
    )

    assert [person["name"] for person in state.character_settings["relationships"]["key_people"]] == [
        "陆昊然"
    ]
    assert state.relationships == {}
