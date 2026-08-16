from __future__ import annotations

from config.feature_flags import reset_features, set_feature
from src.ai.long_story_context import LongStoryContextBuilder, StoryContextSettings
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


def test_gap_downgrades_projection_mutable_world_and_unknown_legacy_facts() -> None:
    _enable_projection()
    try:
        mutable_categories = (
            "situation",
            "promise",
            "state_change",
            "relationship",
            "decision",
            "unknown_mutable",
        )
        state = _daily_state(
            day_history=[
                {
                    "day_index": 1,
                    "event_id": "event-1",
                    "revision": 1,
                    "event_description": "新一天已经接受但投影尚未追平。",
                }
            ],
            established_facts=[
                {
                    "subject": "孙悟空",
                    "category": "identity",
                    "fact": "孙悟空是石猴",
                },
                *[
                    {
                        "subject": "孙悟空",
                        "category": category,
                        "fact": f"legacy-{category}",
                    }
                    for category in mutable_categories
                ],
            ],
        )
        source = {"event_id": "event-0", "revision": 1, "day_index": 0}
        state.world_projection_state["applied_through_day_index"] = 0
        state.world_projection_state["pending_from_day_index"] = 1
        state.world_projection_state["world"].update(
            {
                "fact_updates": [
                    {
                        "subject": "孙悟空",
                        "category": "situation",
                        "fact": "projection-old-situation",
                        "source": source,
                    }
                ],
                "habit_updates": [
                    {
                        "character": "孙悟空",
                        "habit": "projection-old-habit",
                        "source": source,
                    }
                ],
                "location_updates": [
                    {
                        "character": "孙悟空",
                        "location": "projection-old-location",
                        "source": source,
                    }
                ],
                "career_updates": [
                    {
                        "character": "孙悟空",
                        "current_job": "projection-old-career",
                        "source": source,
                    }
                ],
                "commitment_updates": [
                    {
                        "description": "projection-old-commitment",
                        "parties": ["孙悟空"],
                        "status": "pending",
                        "source": source,
                    }
                ],
                "causal_updates": [
                    {
                        "cause": "projection-old-cause",
                        "expected_consequence": "projection-old-consequence",
                        "source": source,
                    }
                ],
            }
        )

        from src.game.world_projection_resolver import resolve_world_context

        resolved = resolve_world_context(state)

        assert resolved.hard_world_model.character_locations == {}
        assert resolved.hard_world_model.career_records == {}
        assert resolved.hard_world_model.active_commitments == []
        assert resolved.hard_world_model.causal_chains == []
        assert resolved.hard_world_model.hard_character_habits == []
        assert [
            fact["fact"] for fact in resolved.hard_world_model.hard_established_facts
        ] == ["孙悟空是石猴"]
        for text in (
            "projection-old-location",
            "projection-old-career",
            "projection-old-commitment",
            "projection-old-cause",
            "projection-old-habit",
            "projection-old-situation",
            *[f"legacy-{category}" for category in mutable_categories],
        ):
            assert text in resolved.soft_context
    finally:
        reset_features()


def test_canonical_tail_budget_prefers_newest_complete_accepted_record(
    monkeypatch,
) -> None:
    class CharacterCounter:
        def count(self, text: str) -> int:
            return len(text)

    monkeypatch.setattr(
        "src.game.world_projection_resolver.LongStoryContextBuilder",
        lambda: LongStoryContextBuilder(
            token_counter=CharacterCounter(),
            settings=StoryContextSettings(
                input_token_budget=110,
                snapshot_target_tokens=20,
                dynamic_token_reserve=0,
            ),
        ),
    )
    _enable_projection()
    try:
        state = _daily_state(
            day_history=[
                {
                    "day_index": 0,
                    "event_id": "event-old",
                    "revision": 1,
                    "event_description": "旧" * 20,
                    "choice": "旧选择",
                },
                {
                    "day_index": 1,
                    "event_id": "event-new",
                    "revision": 1,
                    "event_description": "最新完整故事",
                    "choice": "最新选择",
                },
            ]
        )

        from src.game.world_projection_resolver import resolve_world_context

        tail = resolve_world_context(state).canonical_tail

        assert "最新完整故事" in tail
        assert "最新选择" in tail
        assert "event-new" in tail
        assert "event-old" not in tail
    finally:
        reset_features()


def test_oversized_tail_still_reports_stale_from_first_eligible_day(
    monkeypatch,
) -> None:
    class CharacterCounter:
        def count(self, text: str) -> int:
            return len(text)

    monkeypatch.setattr(
        "src.game.world_projection_resolver.LongStoryContextBuilder",
        lambda: LongStoryContextBuilder(
            token_counter=CharacterCounter(),
            settings=StoryContextSettings(
                input_token_budget=20,
                snapshot_target_tokens=5,
                dynamic_token_reserve=0,
            ),
        ),
    )
    _enable_projection()
    try:
        state = _daily_state(
            day_history=[
                {
                    "day_index": 0,
                    "event_id": "oversized",
                    "revision": 1,
                    "event_description": "无法放入预算" * 30,
                }
            ]
        )

        from src.game.world_projection_resolver import resolve_world_context

        resolved = resolve_world_context(state)

        assert resolved.canonical_tail == ""
        assert resolved.freshness.stale_from_day_index == 0
    finally:
        reset_features()


def test_malformed_projection_records_are_soft_and_never_break_constraints() -> None:
    _enable_projection()
    try:
        state = _daily_state()
        state.world_projection_state["world"]["commitment_updates"] = [
            {
                "description": "坏承诺仍可作为软提示",
                "parties": None,
                "status": "pending",
                "source": {"event_id": "event-0", "revision": 1, "day_index": 0},
            }
        ]

        from src.game.world_projection_resolver import resolve_world_context

        resolved = resolve_world_context(state)

        assert resolved.hard_world_model.active_commitments == []
        assert "坏承诺仍可作为软提示" in resolved.soft_context
        resolved.hard_world_model.build_constraints_text("zh")
        from src.game.historical_summary_selector import HistoricalSummarySelector

        HistoricalSummarySelector.select_relevant_historical_summary(state)
    finally:
        reset_features()


def test_projection_career_beats_initial_occupation_and_legacy_ledger_role() -> None:
    _enable_projection()
    try:
        state = _daily_state(
            character_settings={
                "occupation": {"occupation": "弼马温", "employer": "天庭"}
            }
        )
        state.world_projection_state["applied_through_day_index"] = 0
        state.world_projection_state["world"]["career_updates"] = [
            {
                "character": "孙悟空",
                "current_job": "花果山守护者",
                "employer": "花果山",
                "level": "lead",
                "source": {"event_id": "event-0", "revision": 1, "day_index": 0},
            }
        ]

        from src.game.world_projection_resolver import resolve_world_context

        resolved = resolve_world_context(state)
        constraints = resolved.hard_world_model.build_constraints_text("zh")

        assert (
            resolved.hard_world_model.career_records["孙悟空"].current_job
            == "花果山守护者"
        )
        assert "花果山守护者" in constraints
        assert "弼马温" not in constraints
        assert "弼马温" in resolved.soft_context
    finally:
        reset_features()
