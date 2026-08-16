from __future__ import annotations

from config.feature_flags import reset_features, set_feature
from src.game.daily_timeline import build_daily_timeline
from src.game.state import PlayerState


def _daily_state(**updates) -> PlayerState:
    payload = {
        "player_name": "孙悟空",
        "timeline": build_daily_timeline(
            start_date="2026-08-01",
            day_index=6,
        ),
        "timeline_version": 2,
    }
    payload.update(updates)
    return PlayerState(**payload)


def _enable_projection() -> None:
    reset_features()
    set_feature("daily_world_projection_v1", True)


def test_projection_layer_overrides_legacy_derived_world_as_hard_context() -> None:
    _enable_projection()
    try:
        state = _daily_state(
            established_facts=[
                {
                    "subject": "孙悟空",
                    "category": "location",
                    "fact": "东海（途中）",
                    "established_week": 0,
                },
                {
                    "subject": "孙悟空",
                    "category": "role",
                    "fact": "旧任弼马温",
                    "established_week": 0,
                },
            ],
            character_habits=[{"character": "孙悟空", "habit": "每天清晨巡海"}],
            world_model_data={
                "character_locations": {
                    "孙悟空": {"location": "东海（途中）", "region": "东海"}
                },
                "career_records": {
                    "孙悟空": {"current_job": "旧任弼马温", "since_week": 0}
                },
                "active_commitments": [
                    {"description": "继续留在东海", "parties": ["孙悟空"]}
                ],
                "causal_chains": [
                    {"cause": "滞留东海", "expected_consequence": "无法返回花果山"}
                ],
            },
        )
        state.world_projection_state["applied_through_day_index"] = 5
        state.world_projection_state["projected_through_day_index"] = 5
        state.world_projection_state["world"].update(
            {
                "location_updates": [
                    {
                        "character": "孙悟空",
                        "location": "花果山",
                        "region": "傲来国",
                        "source": {
                            "event_id": "event-5",
                            "revision": 2,
                            "day_index": 5,
                        },
                    }
                ],
                "career_updates": [
                    {
                        "character": "孙悟空",
                        "current_job": "花果山守护者",
                        "source": {
                            "event_id": "event-5",
                            "revision": 2,
                            "day_index": 5,
                        },
                    }
                ],
            }
        )

        from src.game.world_projection_resolver import resolve_world_context

        resolved = resolve_world_context(state)

        assert (
            resolved.hard_world_model.character_locations["孙悟空"].location == "花果山"
        )
        assert (
            resolved.hard_world_model.career_records["孙悟空"].current_job
            == "花果山守护者"
        )
        assert resolved.hard_world_model.active_commitments == []
        assert resolved.hard_world_model.causal_chains == []
        assert resolved.hard_world_model.hard_established_facts == ()
        for legacy_text in (
            "东海（途中）",
            "旧任弼马温",
            "继续留在东海",
            "无法返回花果山",
            "每天清晨巡海",
        ):
            assert legacy_text in resolved.soft_context
    finally:
        reset_features()


def test_pending_gap_builds_deduplicated_canonical_tail_with_actual_choice() -> None:
    _enable_projection()
    try:
        record = {
            "day_index": 4,
            "event_id": "event-4",
            "revision": 3,
            "story_date": "2026-08-05",
            "event_description": "黑袍人抵达东海。",
            "options": [
                {"text": "留在东海", "effects": {}},
                {"text": "返回花果山", "effects": {}},
            ],
            "choice_option_index": 1,
            "choice": "返回花果山",
            "world_projection_status": "pending",
        }
        state = _daily_state(day_history=[record, dict(record)])
        state.world_projection_state["applied_through_day_index"] = 3
        state.world_projection_state["pending_from_day_index"] = 4

        from src.game.world_projection_resolver import resolve_world_context

        tail = resolve_world_context(state).canonical_tail

        assert "黑袍人抵达东海。" in tail
        assert "返回花果山" in tail
        assert "event-4" in tail
        assert "revision=3" in tail
        assert "2026-08-05" in tail
        assert tail.count("黑袍人抵达东海。") == 1
        assert "留在东海" not in tail
    finally:
        reset_features()


def test_current_accepted_unselected_story_after_watermark_is_in_canonical_tail() -> (
    None
):
    _enable_projection()
    try:
        state = _daily_state(day_history=[])
        state.world_projection_state["applied_through_day_index"] = 4
        state.current_event_data = {
            "day_index": 5,
            "event_id": "event-5",
            "revision": 2,
            "story_date": "2026-08-06",
            "event_description": "孙悟空已经抵达花果山。",
            "options": [
                {"text": "查看山门", "effects": {}},
                {"text": "拜访群猴", "effects": {}},
            ],
        }

        from src.game.world_projection_resolver import resolve_world_context

        tail = resolve_world_context(state).canonical_tail

        assert "孙悟空已经抵达花果山。" in tail
        assert "event-5" in tail
        assert "revision=2" in tail
        assert "玩家选择" not in tail
        assert "查看山门" not in tail
        assert "拜访群猴" not in tail
    finally:
        reset_features()


def test_day_zero_after_default_watermark_is_not_dropped_from_canonical_tail() -> None:
    _enable_projection()
    try:
        state = _daily_state(
            day_history=[
                {
                    "day_index": 0,
                    "event_id": "event-0",
                    "revision": 1,
                    "story_date": "2026-08-01",
                    "event_description": "第一天，孙悟空离开石室。",
                    "choice": "走向山门",
                }
            ]
        )

        from src.game.world_projection_resolver import resolve_world_context

        tail = resolve_world_context(state).canonical_tail

        assert "第一天，孙悟空离开石室。" in tail
        assert "走向山门" in tail
        assert "day_index=0" in tail
    finally:
        reset_features()


def test_immutable_base_fact_stays_hard_while_legacy_derived_facts_are_soft() -> None:
    _enable_projection()
    try:
        state = _daily_state(
            established_facts=[
                {
                    "subject": "孙悟空",
                    "category": "identity",
                    "fact": "孙悟空是从仙石中诞生的石猴",
                    "established_week": 0,
                },
                {
                    "subject": "孙悟空",
                    "category": "location",
                    "fact": "孙悟空仍在旧东海营地",
                    "established_week": 0,
                },
            ]
        )

        from src.game.world_projection_resolver import resolve_world_context

        resolved = resolve_world_context(state)

        assert [
            fact["fact"] for fact in resolved.hard_world_model.hard_established_facts
        ] == ["孙悟空是从仙石中诞生的石猴"]
        assert "孙悟空仍在旧东海营地" in resolved.soft_context
    finally:
        reset_features()


def test_old_pending_marker_below_applied_watermark_does_not_make_context_stale() -> (
    None
):
    _enable_projection()
    try:
        state = _daily_state(
            day_history=[
                {
                    "day_index": 2,
                    "event_id": "legacy-event",
                    "revision": 1,
                    "event_description": "很早以前已经接受的故事。",
                    "choice": "继续",
                    "world_projection_status": "failed_retryable",
                }
            ]
        )
        state.world_projection_state["applied_through_day_index"] = 10
        state.world_projection_state["pending_from_day_index"] = 2

        from src.game.world_projection_resolver import resolve_world_context

        resolved = resolve_world_context(state)

        assert resolved.canonical_tail == ""
        assert resolved.freshness.world_derivations_are_fresh is True
    finally:
        reset_features()


def test_flag_off_delegates_to_legacy_freshness_and_ignores_projection_authority() -> (
    None
):
    reset_features()
    state = _daily_state(
        day_history=[
            {
                "day_index": 5,
                "event_description": "孙悟空离开东海。",
                "choice": "返回花果山",
                "postprocessing_status": "pending",
            }
        ],
        world_model_data={
            "character_locations": {"孙悟空": {"location": "东海", "region": "东海"}}
        },
    )
    state.world_projection_state["applied_through_day_index"] = 5
    state.world_projection_state["world"]["location_updates"] = [
        {
            "character": "孙悟空",
            "location": "天宫",
            "region": "天界",
            "source": {"event_id": "event-5", "revision": 1, "day_index": 5},
        }
    ]

    from src.game.world_projection_resolver import resolve_world_context

    resolved = resolve_world_context(state)

    assert resolved.freshness.reason == "world_projection_pending"
    assert resolved.hard_world_model.character_locations == {}
    assert "东海" in resolved.soft_context
    assert "天宫" not in resolved.soft_context
    assert resolved.canonical_tail == ""
