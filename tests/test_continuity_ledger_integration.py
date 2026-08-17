"""P1-7 integration contracts for initialization, prompting, and validation."""

from __future__ import annotations

from unittest.mock import MagicMock

from src.ai.consistency_validator import ConsistencyValidator
from src.ai.story_generator import StoryGenerator
from src.game.continuity_ledger import ContinuityLedger
from src.game.game_initializer import GameInitializer
from src.game.state import PlayerState
from src.game.world_model import WorldModel
import pytest

pytestmark = [pytest.mark.integration]



def _settings() -> dict:
    return {
        "narrative_style_id": "realistic_modern",
        "era": {"year": 2026, "era_description": "2026年的上海"},
        "age": {"age": 28},
        "occupation": {"occupation": "纪录片剪辑师"},
        "relationships": {
            "key_people": [
                {"name": "苏晚晴", "role": "摄影师", "relationship": "合作伙伴"}
            ]
        },
    }


def test_game_initializer_persists_seeded_ledger_in_initial_state() -> None:
    db = MagicMock()
    db.create_game.return_value = 77

    loop, game_id = GameInitializer(db, language="zh").initialize_game_from_settings(
        character_settings=_settings(),
        player_name="林见微",
        life_vision="完成公益纪录片",
        user_id=5,
    )

    assert game_id == 77
    saved = db.create_game.call_args.kwargs["initial_state"]
    assert (
        saved["continuity_ledger"]["immutable_identities"]["林见微"]["age_baseline"]
        == 28
    )
    assert saved["continuity_ledger"]["immutable_identities"]["苏晚晴"]["roles"] == [
        "摄影师"
    ]
    assert loop.get_state().continuity_ledger == saved["continuity_ledger"]


def test_world_model_injects_authoritative_ledger_snapshot() -> None:
    state = PlayerState(
        player_name="林见微",
        age=28,
        week=1,
        character_settings=_settings(),
    )
    ledger = ContinuityLedger.from_player_state(state)
    ledger.record_committed_event(
        event_id="w0-r0",
        week=0,
        round_number=0,
        date_info={"year": 2026, "month": 1, "week_in_month": 1},
        summary="社区拍摄备案完成",
        choice="提交备案",
        story_text="社区拍摄备案完成。",
        fact_updates=[
            {
                "action": "new",
                "subject": "社区拍摄备案",
                "category": "completed_event",
                "fact": "备案完成",
            }
        ],
    )
    ledger.persist(state)

    world_model = WorldModel.from_player_state(state)
    constraints = world_model.build_constraints_text("zh")

    assert world_model.continuity_ledger is not None
    assert "权威连续性事实账本" in constraints
    assert "备案完成" in constraints


def test_legacy_save_is_seeded_and_persisted_when_world_model_is_built() -> None:
    state = PlayerState(
        player_name="林见微",
        age=28,
        week=2,
        character_settings=_settings(),
        continuity_ledger={},
    )

    WorldModel.from_player_state(state)

    identities = state.continuity_ledger["immutable_identities"]
    assert identities["林见微"]["age_baseline"] == 28
    assert identities["苏晚晴"]["roles"] == ["摄影师"]


def test_legacy_save_backfills_committed_rounds_before_next_generation() -> None:
    state = PlayerState(
        player_name="林岚",
        age=29,
        week=6,
        current_round=0,
        character_settings=_settings(),
        continuity_ledger={},
        round_history=[
            {
                "week": 3,
                "round": 0,
                "date_info": {"year": 2026, "month": 1, "week_in_month": 4},
                "summary": "影院改造第一阶段已经验收。",
                "choice": "验收改造并购买书架",
                "event_description": "林岚和陈越验收了改造第一阶段。",
                "story_continuation": "她支出二千元购买书架，空间开始投入使用。",
            },
            {
                "week": 5,
                "round": 0,
                "date_info": {"year": 2026, "month": 2, "week_in_month": 2},
                "summary": "第一场电影阅读活动已经举办。",
                "choice": "举办首场电影阅读活动",
                "event_description": "陈越负责放映，林涛负责书架区。",
                "story_continuation": "活动顺利结束，观众留下了反馈。",
            },
        ],
    )

    constraints = WorldModel.from_player_state(state).build_constraints_text("zh")

    timeline = state.continuity_ledger["timeline"]
    assert [entry["event_id"] for entry in timeline] == ["w3-r0", "w5-r0"]
    assert timeline[0]["choice"] == "验收改造并购买书架"
    assert "验收改造并购买书架" in constraints
    assert "举办首场电影阅读活动" in constraints


def test_consistency_validator_rejects_ledger_conflict_without_ai_call() -> None:
    class FailIfCalled:
        def call(self, **kwargs):
            raise AssertionError(
                "authoritative conflicts must be rejected before AI validation"
            )

    state = PlayerState(
        player_name="林见微",
        age=28,
        week=1,
        current_round=0,
        character_settings=_settings(),
    )
    ledger = ContinuityLedger.from_player_state(state)
    ledger.persist(state)
    world_model = WorldModel.from_player_state(state)

    result = ConsistencyValidator(FailIfCalled()).validate_story(
        story_text="2026年2月初，苏晚晴作为小学副校长主持全校大会。",
        world_model=world_model,
        player_state_dict=state.to_dict(),
        character_settings=state.character_settings,
        language="zh",
        run_ai_validation=False,
    )

    assert not result.passed
    assert result.has_critical_issues
    assert {issue.dimension for issue in result.issues} >= {"timeline", "identity"}
    assert "权威事实账本冲突" in result.fix_instructions
    conflict_codes = {
        conflict["code"] for conflict in state.continuity_ledger["conflicts"]
    }
    assert conflict_codes >= {"date_mismatch", "identity_role_conflict"}


def test_fast_story_generation_still_retries_authoritative_conflict() -> None:
    class RetryClient:
        def __init__(self) -> None:
            self.calls = []

        def call(self, **kwargs):
            self.calls.append(kwargs)
            return "2026年1月，摄影师苏晚晴继续与林见微推进纪录片拍摄。"

    state = PlayerState(
        player_name="林见微",
        age=28,
        week=1,
        current_round=0,
        character_settings=_settings(),
    )
    ledger = ContinuityLedger.from_player_state(state)
    ledger.persist(state)
    world_model = WorldModel.from_player_state(state)
    client = RetryClient()
    generator = StoryGenerator(client, quality_level="fast")  # type: ignore[arg-type]

    result = generator._validate_and_retry_story(
        story_text="2026年2月，苏晚晴作为小学副校长主持全校大会。",
        world_model=world_model,
        player_state=state.to_dict(),
        character_settings=state.character_settings,
        language="zh",
        original_prompt="请继续故事。",
        sys_prompt="系统提示",
    )

    assert len(client.calls) == 1
    assert "权威事实账本冲突" in client.calls[0]["user_prompt"]
    assert "摄影师苏晚晴" in result
