"""generate_round_event 重试循环测试.

验证不同 quality_level 下 generate_round_event 的尝试次数.
"""

from unittest.mock import MagicMock, patch

import pytest

from src.ai.harness.quality_level import QualityLevel
from src.ai.story_exceptions import StoryGenerationFailure
from src.ai.story_generator import StoryGenerator

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
