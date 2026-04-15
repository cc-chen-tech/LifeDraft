"""StoryGenerator 质量级别集成测试.

验证 StoryGenerator 能正确接收 quality_level，
并按级别控制校验和重试行为.
"""

from unittest.mock import MagicMock, patch
import pytest

from src.ai.story_generator import StoryGenerator
from src.ai.harness.quality_level import QualityLevel


def test_story_generator_accepts_quality_level():
    """StoryGenerator 构造时接收 quality_level 参数."""
    mock_client = MagicMock()
    gen = StoryGenerator(mock_client, quality_level=QualityLevel.FAST)
    assert gen.quality_level == QualityLevel.FAST


def test_fast_mode_skips_ai_consistency_check():
    """FAST 模式下 _validate_and_retry_story 直接返回原文本."""
    mock_client = MagicMock()
    gen = StoryGenerator(mock_client, quality_level=QualityLevel.FAST)

    result = gen._validate_and_retry_story(
        story_text="测试故事",
        world_model=MagicMock(),
        player_state={"week": 1, "current_round": 1},
        character_settings={},
        language="zh",
        original_prompt="prompt",
        sys_prompt="sys",
    )
    assert result == "测试故事"


def test_expert_mode_keeps_consistency_guard():
    """EXPERT 模式下 _validate_and_retry_story 保持防循环守卫."""
    mock_client = MagicMock()
    gen = StoryGenerator(mock_client, quality_level=QualityLevel.EXPERT)

    player_state = {"week": 1, "current_round": 1}

    # 第一次调用应进入校验逻辑（被 patch 拦截）
    with patch("src.ai.consistency_validator.ConsistencyValidator") as mock_validator_cls:
        mock_validator = MagicMock()
        mock_validator.validate_story.return_value = MagicMock(passed=True)
        mock_validator_cls.return_value = mock_validator

        result = gen._validate_and_retry_story(
            story_text="测试故事",
            world_model=MagicMock(),
            player_state=player_state,
            character_settings={},
            language="zh",
            original_prompt="prompt",
            sys_prompt="sys",
        )
        assert result == "测试故事"
        # 验证 ConsistencyValidator 确实被构造了
        mock_validator_cls.assert_called_once()

    # 第二次调用同一 round 应被守卫跳过
    result2 = gen._validate_and_retry_story(
        story_text="测试故事2",
        world_model=MagicMock(),
        player_state=player_state,
        character_settings={},
        language="zh",
        original_prompt="prompt",
        sys_prompt="sys",
    )
    assert result2 == "测试故事2"
