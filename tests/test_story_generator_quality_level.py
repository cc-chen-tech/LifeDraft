"""StoryGenerator 质量级别集成测试.

验证 StoryGenerator 能正确接收 quality_level，
并按级别控制校验和重试行为.
"""

from unittest.mock import MagicMock, patch

from src.ai.harness.quality_level import QualityLevel
import pytest

from src.ai.consistency_validator import ConsistencyIssue, ValidationResult
from src.ai.models import EventOption, GameEvent
from src.ai.story_validation import FindingSeverity, ValidationFinding
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
        evidence="哪吒封存龙骨后仍被写成坚持保留龙骨",
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
    retry_prompt = story_call.call_args.kwargs["user_prompt"]
    assert issue.description in retry_prompt
    assert issue.evidence in retry_prompt


def test_outer_story_retry_reuses_failed_consistency_findings() -> None:
    issue = ValidationFinding(
        code="CONSISTENCY_FAILED",
        severity=FindingSeverity.HARD,
        confidence=0.95,
        source="consistency_validator",
        message="孙悟空已经离开东海，却又被写到东海渊底",
        evidence="孙悟空驾云坠入东海渊底",
        repair_instruction="必须先交代返回东海的过程",
    )
    first_story = "初稿把孙悟空写回东海渊底，且没有交代移动过程。" * 35
    second_story = "第二稿严格遵守既有位置记录，先交代移动过程再推进事件。" * 35

    class PromptAwareClient:
        def __init__(self) -> None:
            self.calls: list[dict[str, object]] = []

        def call(self, **kwargs: object) -> str:
            self.calls.append(kwargs)
            return first_story if len(self.calls) == 1 else second_story

    client = PromptAwareClient()
    option_generator = MagicMock()
    option_generator.generate_options_only.return_value = GameEvent(
        event_description=second_story,
        options=[
            EventOption(text="先核对移动记录", effects={}),
            EventOption(text="询问同伴", effects={}),
            EventOption(text="确认下一步风险", effects={}),
        ],
    )
    generator = StoryGenerator(client, quality_level=QualityLevel.EXPERT)

    # The first validation failure is injected, and the outer loop must carry
    # its concrete finding into the next prose request.
    with patch.object(
        generator,
        "_validate_and_retry_story",
        side_effect=[
            StoryGenerationFailure(
                "consistency repair still contains hard findings",
                findings=[issue],
                circuit_break=False,
            ),
            second_story,
        ],
    ) as validate_story:
        event = generator.generate_round_event(
            player_state={"week": 0, "current_round": 0},
            language="zh",
            round_number=0,
            round_context="",
            option_generator=option_generator,
            world_model=object(),
        )

    assert event.event_description == second_story
    assert validate_story.call_count == 2
    assert len(client.calls) == 2
    second_prompt = str(client.calls[1]["user_prompt"])
    assert issue.message in second_prompt
    assert issue.evidence in second_prompt
    assert issue.repair_instruction in second_prompt
