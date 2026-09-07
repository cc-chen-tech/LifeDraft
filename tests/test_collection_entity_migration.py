"""Regression tests for repairing already-persisted collection state."""

import pytest

from src.game.state import PlayerState

pytestmark = pytest.mark.unit


def test_repair_collection_state_removes_cross_category_people_and_backfills_daily_entities() -> (
    None
):
    from src.services.entity_recognition_migration import repair_collection_state

    state = PlayerState(
        player_name="唐三藏",
        relationships={"金箍棒": 20, "孙悟空": 80},
        characters={
            "孙悟空": {"name": "孙悟空"},
            "杨戬": {"name": "杨戬"},
            "金箍棒": {"name": "金箍棒"},
            "花果山": {"name": "花果山"},
            "杨戬立": {"name": "杨戬立"},
            "金纹": {"name": "金纹"},
        },
        day_history=[
            {
                "event_id": "day-1",
                "day_index": 0,
                "event_description": "孙悟空在花果山取出金箍棒，杨戬守在山门。",
            }
        ],
    )

    repaired, report = repair_collection_state(state.model_dump())

    assert set(repaired["characters"]) == {"孙悟空", "杨戬"}
    assert "金箍棒" not in repaired["relationships"]
    assert "金箍棒" in repaired["items"]
    assert "花果山" in repaired["landmarks"]
    assert set(report["removed_characters"]) == {"金箍棒", "花果山", "杨戬立", "金纹"}
    assert report["would_change"] is True


def test_repair_collection_state_uses_legacy_compatibility_loader() -> None:
    """迁移旧档时必须兼容可为空的历史字符串字段。"""
    from src.services.entity_recognition_migration import repair_collection_state

    state = PlayerState(
        player_name="唐三藏",
        last_round_full_story="",
        day_history=[
            {"day_index": 0, "story_date": "2026-08-01"},
        ],
        round_history=[
            {
                "week": 0,
                "round": 0,
                "event_description": "孙悟空在花果山取回金箍棒。",
            }
        ],
    ).model_dump()
    state["last_round_full_story"] = None

    repaired, report = repair_collection_state(state)

    assert repaired["last_round_full_story"] == ""
    assert "金箍棒" in repaired["items"]
    assert "花果山" in repaired["landmarks"]
    assert report["would_change"] is True
