"""StoryGenerator 质量级别集成测试.

验证 StoryGenerator 能正确接收 quality_level，
并按级别控制校验和重试行为.
"""

from unittest.mock import MagicMock, patch

from src.ai.harness.quality_level import QualityLevel
import pytest

from src.ai.consistency_validator import ConsistencyIssue, ValidationResult
from src.ai.story_exceptions import StoryGenerationFailure
from src.ai.story_generator import StoryGenerator

pytestmark = [pytest.mark.unit]



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


def test_expert_mode_revalidates_every_candidate_for_the_same_round():
    """同一轮的新候选和手动重生成都不能复用旧候选的校验结论。"""
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

    with patch("src.ai.consistency_validator.ConsistencyValidator") as second_cls:
        second_validator = MagicMock()
        second_validator.validate_story.return_value = MagicMock(passed=True)
        second_cls.return_value = second_validator
        result2 = gen._validate_and_retry_story(
            story_text="测试故事2",
            world_model=MagicMock(),
            player_state=player_state,
            character_settings={},
            language="zh",
            original_prompt="prompt",
            sys_prompt="sys",
        )
        second_validator.validate_story.assert_called_once()
    assert result2 == "测试故事2"


def test_consistency_repair_is_revalidated_and_same_hard_issue_breaks() -> None:
    issue = ConsistencyIssue(
        dimension="identity",
        severity="CRITICAL",
        description="导师身份与权威关系网冲突",
        fix_suggestion="恢复既定导师身份",
    )
    failed = ValidationResult(
        passed=False,
        issues=[issue],
        fix_instructions="恢复既定导师身份",
    )
    generator = StoryGenerator(MagicMock(), quality_level=QualityLevel.EXPERT)
    story_call = MagicMock(return_value="修订后仍把名单外人物写成导师")

    with patch(
        "src.ai.consistency_validator.ConsistencyValidator.validate_story",
        side_effect=[failed, failed],
    ) as validate_story:
        with pytest.raises(StoryGenerationFailure):
            generator._validate_and_retry_story(
                story_text="初稿把名单外人物写成导师",
                world_model=MagicMock(),
                player_state={"game_id": 99, "week": 1, "current_round": 1},
                character_settings={},
                language="zh",
                original_prompt="继续故事",
                sys_prompt="系统",
                story_call=story_call,
            )

    assert story_call.call_count == 1
    assert validate_story.call_count == 2
