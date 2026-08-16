from copy import deepcopy
from types import SimpleNamespace

import pytest

from src.game.state import PlayerState
from src.game.world_projection_state import (
    apply_world_projection_patch,
    recompute_projection_watermarks,
)


def _projection(*, source_hash: str = "source-5", status: str = "ready"):
    return SimpleNamespace(
        projection_id=51,
        game_id=156,
        event_id="event-5",
        revision=2,
        day_index=5,
        source_hash=source_hash,
        status=status,
        created_at=None,
        story_patch_json={
            "fact_updates": [
                {
                    "action": "new",
                    "subject": "孙悟空",
                    "category": "location",
                    "fact": "孙悟空已经抵达东海",
                }
            ],
            "location_updates": [
                {
                    "action": "move",
                    "character": "孙悟空",
                    "to": "东海",
                    "from": "花果山",
                }
            ],
        },
        option_patches_json={
            "0": {},
            "1": {
                "commitment_updates": [
                    {
                        "action": "new",
                        "description": "帮助龙王寻找宝物",
                        "parties": ["孙悟空", "龙王"],
                    }
                ]
            },
        },
    )


def test_projection_materialization_preserves_provenance_and_is_idempotent() -> None:
    state = PlayerState(week=1)
    state.world_projection_state["applied_through_day_index"] = 4
    projection = _projection()

    assert apply_world_projection_patch(state, projection, option_index=1) is True
    first = deepcopy(state.world_projection_state)
    assert apply_world_projection_patch(state, projection, option_index=1) is False

    assert state.world_projection_state == first
    assert state.world_projection_state["applied_through_day_index"] == 5
    assert state.world_projection_state["applied_sources"] == [
        {
            "event_id": "event-5",
            "revision": 2,
            "day_index": 5,
            "source_hash": "source-5",
            "option_index": 1,
        }
    ]
    source = {
        "event_id": "event-5",
        "revision": 2,
        "day_index": 5,
    }
    world = state.world_projection_state["world"]
    assert world["fact_updates"][0]["source"] == source
    assert world["location_updates"][0]["source"] == source
    assert world["commitment_updates"][0]["source"] == source


def test_projection_replay_fences_source_and_selected_option() -> None:
    state = PlayerState()
    state.world_projection_state["applied_through_day_index"] = 4
    apply_world_projection_patch(state, _projection(), option_index=1)

    with pytest.raises(ValueError, match="world_projection_source_conflict"):
        apply_world_projection_patch(
            state, _projection(source_hash="replacement-source"), option_index=1
        )
    with pytest.raises(ValueError, match="world_projection_option_conflict"):
        apply_world_projection_patch(state, _projection(), option_index=0)


def test_recompute_watermarks_stops_at_first_non_ready_gap() -> None:
    state = PlayerState()
    state.world_projection_state["applied_through_day_index"] = 4
    rows = [
        SimpleNamespace(day_index=5, status="applied", created_at=None),
        SimpleNamespace(
            day_index=6, status="failed_retryable", created_at="2026-08-17T01:00:00"
        ),
        SimpleNamespace(day_index=7, status="ready", created_at=None),
    ]

    recompute_projection_watermarks(state, rows)

    assert state.world_projection_state["projected_through_day_index"] == 5
    assert state.world_projection_state["pending_from_day_index"] == 6
    assert state.world_projection_state["oldest_pending_at"] == "2026-08-17T01:00:00"


def test_recompute_watermarks_marks_an_absent_settled_day_pending() -> None:
    state = PlayerState(day_history=[{"day_index": 6, "choice_option_index": 0}])
    state.world_projection_state["applied_through_day_index"] = 5

    recompute_projection_watermarks(state, [])

    assert state.world_projection_state["projected_through_day_index"] == 5
    assert state.world_projection_state["pending_from_day_index"] == 6
    assert state.world_projection_state["oldest_pending_at"] is None
