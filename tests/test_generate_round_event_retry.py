"""generate_round_event 重试循环测试.

验证不同 quality_level 下 generate_round_event 的尝试次数.
"""

from unittest.mock import MagicMock, patch
import json

import pytest

from src.ai.harness.quality_level import QualityLevel
from src.ai.quick_validator import QuickValidationResult
from src.ai.story_exceptions import StoryGenerationFailure
from src.ai.story_generator import StoryGenerator
from src.ai.story_validation import findings_from_legacy

pytestmark = pytest.mark.usefixtures("constraint_harness_disabled")


def _make_generator(level: QualityLevel):
    """辅助函数：创建带 mock client 的 StoryGenerator."""
    mock_client = MagicMock()
    target_lengths = {
        QualityLevel.FAST: 400,
        QualityLevel.EXPERT: 900,
        QualityLevel.MASTER: 1600,
    }
    sentence = "林岚在工作室核对当天的安排，并把需要决定的事项逐一记下。"
    mock_client.call.return_value = sentence * (target_lengths[level] // len(sentence) + 1)
    return StoryGenerator(mock_client, quality_level=level), mock_client


def _three_person_relationship_settings():
    return {
        "era": {
            "era_description": "2026年现代都市",
            "world_context": "互联网产品团队核对需求与测试材料。",
        },
        "relationships": {
            "key_people": [
                {"name": "陆昊然", "role": "导师"},
                {"name": "陈晓雨", "role": "同事"},
                {"name": "林一凡", "role": "朋友"},
            ]
        },
    }


def test_validation_people_include_protagonist_once():
    names = StoryGenerator._validation_people_names(
        player_state={"player_name": "孙悟空"},
        character_settings={
            "family": {"family_members": [{"name": "孙悟空", "role": "本人"}]},
            **_three_person_relationship_settings(),
        },
    )

    assert names == ["孙悟空", "陆昊然", "陈晓雨", "林一凡"]


def test_round_event_does_not_retry_majority_cast_with_heuristic_object_names():
    opening = (
        "陆昊然和陈晓雨同孙悟空核对方案。"
        "安神香是产品代号，雷火阵是风控模块，云梯果是测试数据集。"
    )
    detail = "他们逐页核对需求说明和测试记录，把需要补充的证据写在纸上。"
    story = opening + detail * 28
    assert 800 <= len(story) <= 1200

    mock_client = MagicMock()
    mock_client.call.return_value = story
    gen = StoryGenerator(mock_client, quality_level=QualityLevel.EXPERT)
    mock_option_gen = MagicMock()
    mock_option_gen.generate_options_only.return_value = MagicMock(
        options=[MagicMock(text="继续核对材料")]
    )
    statuses = []

    gen.generate_round_event(
        player_state={
            "game_id": 1,
            "player_name": "孙悟空",
            "current_week": 1,
        },
        language="zh",
        round_number=0,
        round_context="",
        character_settings=_three_person_relationship_settings(),
        option_generator=mock_option_gen,
        status_callback=statuses.append,
    )

    # Heuristic object names only produce a soft cast-coverage warning, so
    # the best-draft engine refines candidates within budget without ever
    # signalling a hard retry.
    assert mock_client.call.call_count == 3
    assert "retry" not in statuses
    mock_option_gen.generate_options_only.assert_not_called()


def test_fast_mode_single_attempt():
    """FAST 模式下 generate_round_event 只尝试 1 次."""
    gen, client = _make_generator(QualityLevel.FAST)

    with patch.object(gen, "generate_round_event") as mock_method:  # noqa: F841
        # 我们直接验证方法签名和内部逻辑，通过 spy 方式
        pass

    # 由于 generate_round_event 内部实现复杂，我们通过统计 client.call 调用次数来验证
    # 需要先 mock option_generator 等依赖
    mock_option_gen = MagicMock()
    mock_option_gen.generate_options_only.return_value = MagicMock(
        options=[MagicMock(text="选项1")]
    )

    gen.generate_round_event(
        player_state={"game_id": 1, "current_week": 1},
        language="zh",
        round_number=0,
        round_context="",
        option_generator=mock_option_gen,
    )

    assert client.call.call_count == 1


def test_fast_mode_rejects_a_deterministic_hard_validation_failure():
    invalid_story = "我在会议室核对当天的安排，并把需要决定的事项逐一记下。" * 22
    mock_client = MagicMock()
    mock_client.call.return_value = invalid_story
    gen = StoryGenerator(mock_client, quality_level=QualityLevel.FAST)
    mock_option_gen = MagicMock()

    with pytest.raises(StoryGenerationFailure):
        gen.generate_round_event(
            player_state={"game_id": 1, "current_week": 1},
            language="zh",
            round_number=0,
            round_context="",
            option_generator=mock_option_gen,
        )

    assert mock_client.call.call_count == 1
    mock_option_gen.generate_options_only.assert_not_called()


def test_expert_without_harness_uses_one_attempt_for_valid_story():
    """Harness 关闭时，EXPERT 的合格正文不会增加隐式尝试。"""
    gen, client = _make_generator(QualityLevel.EXPERT)
    mock_option_gen = MagicMock()
    mock_option_gen.generate_options_only.return_value = MagicMock(
        options=[MagicMock(text="选项1")]
    )

    gen.generate_round_event(
        player_state={"game_id": 1, "current_week": 1},
        language="zh",
        round_number=0,
        round_context="",
        option_generator=mock_option_gen,
    )

    assert client.call.call_count == 1


def test_master_without_harness_uses_one_attempt_for_valid_story():
    """Harness 关闭时，MASTER 的合格正文不会增加隐式尝试。"""
    gen, client = _make_generator(QualityLevel.MASTER)
    mock_option_gen = MagicMock()
    mock_option_gen.generate_options_only.return_value = MagicMock(
        options=[MagicMock(text="选项1")]
    )

    gen.generate_round_event(
        player_state={"game_id": 1, "current_week": 1},
        language="zh",
        round_number=0,
        round_context="",
        option_generator=mock_option_gen,
    )

    assert client.call.call_count == 1


def test_round_event_fails_closed_when_quick_validation_retry_still_drifts():
    """重试后仍然时代漂移时，不应伪造故事或把无效故事交给选项生成器。"""
    drifting_story = "林知远站在长安西市的木坊里，鲁师傅收下三百文铜钱，称他为林郎君。"
    mock_client = MagicMock()
    mock_client.call.side_effect = [drifting_story, drifting_story]
    gen = StoryGenerator(mock_client, quality_level=QualityLevel.EXPERT)
    mock_option_gen = MagicMock()

    with pytest.raises(StoryGenerationFailure):
        gen.generate_round_event(
            player_state={"game_id": 1, "current_week": 1},
            language="zh",
            round_number=1,
            round_context="",
            character_settings={
                "era": {
                    "era_description": "2024年现代上海",
                    "world_context": "现代社会，独立游戏制作人与创业团队",
                },
            },
            option_generator=mock_option_gen,
        )

    assert mock_client.call.call_count == 2
    mock_option_gen.generate_options_only.assert_not_called()


def test_quick_validation_repair_prompt_contains_the_rejected_draft():
    """Removing the rejected draft would turn a targeted repair into a blind rewrite."""
    invalid_story = (
        "我把当天的安排写在白板上，准备和陈越继续核对方案。"
        * 30
    )
    repaired_story = "林岚和陈越在会议室逐项核对方案，并记录下一步安排。" * 32
    mock_client = MagicMock()
    mock_client.call.side_effect = [invalid_story, repaired_story]
    gen = StoryGenerator(mock_client, quality_level=QualityLevel.EXPERT)
    mock_option_gen = MagicMock()
    mock_option_gen.generate_options_only.return_value = MagicMock(
        options=[MagicMock(text="继续核对")]
    )
    statuses = []

    gen.generate_round_event(
        player_state={"game_id": 1, "current_week": 1},
        language="zh",
        round_number=0,
        round_context="",
        option_generator=mock_option_gen,
        status_callback=statuses.append,
    )

    repair_prompt = mock_client.call.call_args_list[1].kwargs["user_prompt"]
    assert invalid_story in repair_prompt
    assert "上一稿全文" in repair_prompt
    attempt_statuses = [status for status in statuses if isinstance(status, dict)]
    assert attempt_statuses[:2] == [
        {
            "phase": "generating_story",
            "attempt": 1,
            "max_attempts": 3,
            "quality_level": "expert",
        },
        {
            "phase": "retry",
            "attempt": 2,
            "max_attempts": 3,
            "quality_level": "expert",
        },
    ]


def test_changed_hard_fingerprint_uses_remaining_expert_budget():
    story = "林岚和陈越在会议室逐项核对方案，并记录下一步安排。" * 32
    mock_client = MagicMock()
    mock_client.call.side_effect = [story, story, story]
    gen = StoryGenerator(mock_client, quality_level=QualityLevel.EXPERT)
    mock_option_gen = MagicMock()
    mock_option_gen.generate_options_only.return_value = MagicMock(
        options=[MagicMock(text="继续核对")]
    )

    def result(*issues: str) -> QuickValidationResult:
        return QuickValidationResult(
            passed=not issues,
            issues=list(issues),
            findings=findings_from_legacy(
                issues=issues,
                warnings=[],
                source="quick_validator",
            ),
        )

    with patch(
        "src.ai.quick_validator.quick_validate_story",
        side_effect=[
            result("缺少当天明确要求登场人物：陈晓雨"),
            result("现代故事开头使用了章回体标题"),
            result(),
        ],
    ):
        event = gen.generate_round_event(
            player_state={"game_id": 1, "current_week": 1},
            language="zh",
            round_number=0,
            round_context="",
            option_generator=mock_option_gen,
        )

    assert event.options
    assert mock_client.call.call_count == 3


def test_same_hard_fingerprint_on_second_consecutive_candidate_circuits_breaks():
    story = "林岚和陈越在会议室逐项核对方案，并记录下一步安排。" * 32
    mock_client = MagicMock()
    mock_client.call.side_effect = [story, story, story]
    gen = StoryGenerator(mock_client, quality_level=QualityLevel.EXPERT)
    mock_option_gen = MagicMock()

    def result(issue: str) -> QuickValidationResult:
        return QuickValidationResult(
            passed=False,
            issues=[issue],
            findings=findings_from_legacy(
                issues=[issue],
                warnings=[],
                source="quick_validator",
            ),
        )

    with patch(
        "src.ai.quick_validator.quick_validate_story",
        side_effect=[
            result("缺少当天明确要求登场人物：陈晓雨"),
            result("现代故事开头使用了章回体标题"),
            result("现代故事开头使用了章回体标题"),
        ],
    ):
        with pytest.raises(StoryGenerationFailure) as failure:
            gen.generate_round_event(
                player_state={"game_id": 1, "current_week": 1},
                language="zh",
                round_number=0,
                round_context="",
                option_generator=mock_option_gen,
            )

    assert "allowance exhausted" not in str(failure.value)
    assert mock_client.call.call_count == 3
    mock_option_gen.generate_options_only.assert_not_called()


def test_consistency_repair_hard_failure_cannot_fall_back_or_skip_validation():
    """完整生成路径不能吞掉修订复检失败后提交未校验的下一稿。"""
    story = "林岚和陈越在会议室逐项核对方案，并记录下一步安排。" * 32
    hard_result = json.dumps(
        {
            "should_retry": True,
            "retry_reason": "角色身份冲突",
            "issues": [
                {
                    "dimension": "identity",
                    "severity": "CRITICAL",
                    "description": "名单外人物被写成导师并接管职责",
                    "fix_suggestion": "删除名单外导师",
                }
            ],
        },
        ensure_ascii=False,
    )
    client = MagicMock()
    client.call.side_effect = [story, hard_result, story, hard_result, story]
    generator = StoryGenerator(client, quality_level=QualityLevel.EXPERT)
    options = MagicMock()

    with pytest.raises(StoryGenerationFailure, match="repeated consistency"):
        generator.generate_round_event(
            player_state={"game_id": 91, "current_week": 1, "current_round": 0},
            language="zh",
            round_number=0,
            round_context="",
            character_settings=_three_person_relationship_settings(),
            world_model=MagicMock(continuity_ledger=None),
            option_generator=options,
        )

    assert client.call.call_count == 4
    options.generate_options_only.assert_not_called()


def test_consistency_service_failure_cannot_be_treated_as_acceptance():
    story = "林岚和陈越在会议室逐项核对方案，并记录下一步安排。" * 32
    client = MagicMock()
    client.call.side_effect = [
        story,
        RuntimeError("validator unavailable"),
        story,
        RuntimeError("validator unavailable"),
        story,
    ]
    generator = StoryGenerator(client, quality_level=QualityLevel.EXPERT)
    options = MagicMock()

    with pytest.raises(StoryGenerationFailure):
        generator.generate_round_event(
            player_state={"game_id": 92, "current_week": 1, "current_round": 0},
            language="zh",
            round_number=0,
            round_context="",
            character_settings=_three_person_relationship_settings(),
            world_model=MagicMock(continuity_ledger=None),
            option_generator=options,
        )

    options.generate_options_only.assert_not_called()


def test_player_retry_prompt_carries_previous_safe_failure_reason():
    story = "林岚和陈越在会议室逐项核对方案，并记录下一步安排。" * 32
    mock_client = MagicMock()
    mock_client.call.return_value = story
    gen = StoryGenerator(mock_client, quality_level=QualityLevel.EXPERT)
    mock_option_gen = MagicMock()
    mock_option_gen.generate_options_only.return_value = MagicMock(
        options=[MagicMock(text="继续核对")]
    )

    gen.generate_round_event(
        player_state={
            "game_id": 1,
            "current_week": 1,
            "resume_view": {
                "phase": "generating",
                "previous_failure": {
                    "code": "HIGH_CONFIDENCE_UNKNOWN_PERSON",
                    "summary": "故事角色一致性检查连续未通过",
                    "detail": "上次失败稿没有保存。",
                },
            },
        },
        language="zh",
        round_number=0,
        round_context="",
        option_generator=mock_option_gen,
    )

    prompt = mock_client.call.call_args_list[0].kwargs["user_prompt"]
    assert "上次手动重试原因" in prompt
    assert "HIGH_CONFIDENCE_UNKNOWN_PERSON" in prompt
    assert "故事角色一致性检查连续未通过" in prompt


def test_round_event_fails_closed_after_cast_and_world_validation_failures():
    """AI 连续违反人物与世界约束后必须明确失败。"""
    drifting_story = (
        "夜之城的雨落在荒坂集团楼下，Viktor把神经接口推到林见微面前。"
        "马老板和方蕾催她立刻处理陌生债务。"
    )
    mock_client = MagicMock()
    mock_client.call.side_effect = [drifting_story, drifting_story]
    gen = StoryGenerator(mock_client, quality_level=QualityLevel.EXPERT)
    mock_option_gen = MagicMock()

    with pytest.raises(StoryGenerationFailure):
        gen.generate_round_event(
            player_state={
                "game_id": 1,
                "current_week": 1,
                "player_name": "林见微",
                "relationships": {"陆昊然": 50, "陈晓雨": 80, "林一凡": 45},
            },
            language="zh",
            round_number=0,
            round_context="上一轮林见微准备找导师复盘需求优先级。",
            character_settings={
                "era": {
                    "era_description": "2024年现代上海互联网公司",
                    "world_context": "普通产品经理成长线",
                },
                "relationships": {
                    "key_people": [
                        {"name": "陆昊然", "role": "导师", "relationship": "导师"},
                        {"name": "陈晓雨", "role": "闺蜜", "relationship": "闺蜜"},
                        {"name": "林一凡", "role": "同期", "relationship": "同期"},
                    ],
                },
            },
            option_generator=mock_option_gen,
        )

    assert mock_client.call.call_count == 2
    mock_option_gen.generate_options_only.assert_not_called()
