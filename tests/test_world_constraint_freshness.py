from src.game.daily_timeline import build_daily_timeline
from src.game.state import PlayerState
from src.game.world_constraint_freshness import (
    build_validation_world_model,
    derive_legacy_freshness,
)
from src.ai.story_generator import StoryGenerator


def _empty_world_patch() -> dict:
    return {
        "fact_updates": [],
        "habit_updates": [],
        "location_updates": [],
        "career_updates": [],
        "commitment_updates": [],
        "causal_updates": [],
        "foreshadowing_seeds": [],
    }


def test_suspicious_empty_world_updates_make_legacy_constraints_stale() -> None:
    history = [
        {
            "day_index": 4,
            "event_description": "黑袍人抵达东海，完成了与孙悟空的约定。",
            "choice": "进入龙宫",
            "postprocessing_status": "complete",
            "postprocessing": {"world": _empty_world_patch()},
        }
    ]

    freshness = derive_legacy_freshness(
        history,
        {"character_locations": {"黑袍人": {"location": "花果山"}}},
    )

    assert freshness.stale_from_day_index == 4
    assert freshness.reason == "suspicious_empty_world_projection"
    assert freshness.world_derivations_are_fresh is False


def test_pending_projection_makes_derived_constraints_stale_immediately() -> None:
    freshness = derive_legacy_freshness(
        [
            {
                "day_index": 7,
                "event_description": "孙悟空离开花果山。",
                "choice": "前往东海",
                "postprocessing_status": "pending",
            }
        ]
    )

    assert freshness.stale_from_day_index == 7
    assert freshness.reason == "world_projection_pending"


def test_stale_location_commitment_and_causal_state_is_soft_context_only() -> None:
    state = PlayerState(
        player_name="孙悟空",
        timeline=build_daily_timeline(start_date="2026-08-08", day_index=8),
        timeline_version=2,
        day_history=[
            {
                "day_index": 7,
                "event_description": "孙悟空离开花果山，抵达东海。",
                "choice": "进入龙宫",
                "postprocessing_status": "pending",
            }
        ],
        world_model_data={
            "character_locations": {
                "孙悟空": {"location": "花果山", "region": "傲来国"}
            },
            "career_records": {
                "孙悟空": {"current_job": "美猴王", "since_week": 0}
            },
            "active_commitments": [
                {"description": "留在花果山", "parties": ["孙悟空"]}
            ],
            "causal_chains": [
                {
                    "cause": "留守花果山",
                    "expected_consequence": "不能前往东海",
                }
            ],
        },
    )

    view = build_validation_world_model(state)

    assert view.world_model.character_locations == {}
    assert view.world_model.active_commitments == []
    assert view.world_model.causal_chains == []
    assert "孙悟空离开花果山，抵达东海。" in view.soft_context
    assert "进入龙宫" in view.soft_context
    assert "花果山" in view.soft_context
    assert "留在花果山" in view.soft_context
    assert "不能前往东海" in view.soft_context
    assert "孙悟空" in view.world_model.career_records


def test_dict_generation_entrypoint_uses_filtered_validation_model() -> None:
    model = StoryGenerator._build_world_model_from_state_dict(
        {
            "week": 1,
            "current_round": 0,
            "player_name": "孙悟空",
            "timeline": build_daily_timeline(
                start_date="2026-08-08",
                day_index=8,
            ),
            "day_history": [
                {
                    "day_index": 7,
                    "event_description": "孙悟空离开花果山。",
                    "choice": "前往东海",
                    "postprocessing_status": "failed",
                }
            ],
            "character_settings": {},
            "world_model_data": {
                "character_locations": {
                    "孙悟空": {"location": "花果山", "region": "傲来国"}
                },
                "active_commitments": [
                    {"description": "留在花果山", "parties": ["孙悟空"]}
                ],
                "causal_chains": [
                    {
                        "cause": "留守花果山",
                        "expected_consequence": "不能前往东海",
                    }
                ],
            },
        }
    )

    assert model.character_locations == {}
    assert model.active_commitments == []
    assert model.causal_chains == []
