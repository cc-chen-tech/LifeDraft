"""Story Generator Best Story Text Fallback DB Test

验证当后续 Harness 校验失败或最终故事文本过短时，
会使用之前尝试中 Harness 已接受的最佳故事文本（best_story_text），
而不是直接 fallback 到 "平静的一天"。
Layer 4: DB 集成测试 — 生成链路完整性。
"""

from unittest.mock import MagicMock, patch

import pytest

from src.ai.harness.quality_level import QualityLevel
from src.ai.story_exceptions import StoryGenerationFailure
from src.ai.story_generator import StoryGenerator


class TestStoryGeneratorBestStoryFallback:
    """最长 Harness 已接受 best_story_text 的 fallback 行为测试"""

    def _make_generator(self, level: QualityLevel = QualityLevel.MASTER):
        """辅助函数：创建带 mock client 的 StoryGenerator."""
        mock_client = MagicMock()
        return StoryGenerator(mock_client, quality_level=level), mock_client

    def test_best_story_text_used_when_final_is_short(self):
        """后续失败时，回退到先前 Harness 已接受的 best_story_text"""
        gen, client = self._make_generator(QualityLevel.EXPERT)

        long_story = (
            "你在清晨的图书馆整理实验记录，窗外的雨声提醒你即将到来的合作评审。"
            "你把协议中的风险条款逐条标记，并联系林一凡确认技术接口、预算节奏和联调日期。"
            "午后，团队针对数据权限和样本交接展开讨论，你提出先完成小范围验证，再把结果带回项目会上复盘。"
            "傍晚离开实验室前，你写下明天要跟进的三项事项，也决定把尚未解决的顾虑坦诚告诉合作方。"
        ) * 6
        short_story = "短"

        # 第一次返回 Harness 已接受的长文本；后续 CRITICAL 与空文本均不得覆盖它。
        client.call.side_effect = [long_story, short_story, ""]

        mock_option_gen = MagicMock()
        mock_option_gen.generate_options_only.side_effect = Exception("option gen failed")

        # 模拟 Harness：第一次接受；第二次 CRITICAL 后重试，第三次为空。
        gen._harness_enabled = True
        gen._validation_pipeline = MagicMock()
        gen._validation_pipeline.validate.side_effect = [
            MagicMock(
                passed=True,
                score=95,
                critical_failures=[],
                detailed_checks={},
            ),
            MagicMock(
                passed=False,
                score=50,
                critical_failures=["test"],
                detailed_checks={},
            ),
        ]
        gen._retry_controller = MagicMock()
        gen._retry_controller.should_retry.side_effect = [
            (False, None),
            (True, "fix it"),
        ]
        gen._diagnostics = MagicMock()
        gen._diagnostics.generate_report.return_value = {}
        gen._harness_metrics = MagicMock()

        with patch("src.ai.quick_validator.quick_validate_story") as mock_quick:
            mock_quick.return_value = MagicMock(passed=True, issues=[], warnings=[])

            event = gen.generate_round_event(
                player_state={"game_id": 1, "current_week": 1},
                language="zh",
                round_number=0,
                round_context="",
                option_generator=mock_option_gen,
            )

        # 应使用 best_story_text（长故事），而非 fallback "平静的一天"
        assert "平静" not in event.event_description
        assert len(event.event_description) > 50
        assert event.event_description == long_story

    def test_failure_is_surfaced_when_no_valid_story_exists(self):
        """An empty provider result must fail instead of persisting template prose."""
        gen, client = self._make_generator(QualityLevel.MASTER)

        # 所有调用都返回极短文本
        client.call.return_value = "短"

        mock_option_gen = MagicMock()
        mock_option_gen.generate_options_only.side_effect = Exception("option gen failed")

        gen._harness_enabled = False

        with patch("src.ai.quick_validator.quick_validate_story") as mock_quick:
            mock_quick.return_value = MagicMock(passed=True, issues=[], warnings=[])

            with pytest.raises(StoryGenerationFailure, match="failed before producing a valid event"):
                gen.generate_round_event(
                    player_state={"game_id": 1, "current_week": 1},
                    language="zh",
                    round_number=0,
                    round_context="",
                    option_generator=mock_option_gen,
                )

    def test_best_story_tracks_longest_across_attempts(self):
        """best_story_text 应记录所有 Harness 已接受尝试中最长的文本"""
        gen, client = self._make_generator(QualityLevel.EXPERT)

        medium_story = (
            "你在清晨的图书馆整理实验记录，窗外的雨声提醒你即将到来的合作评审。"
            "你把协议中的风险条款逐条标记，并联系林一凡确认技术接口、预算节奏和联调日期。"
            "午后，团队针对数据权限和样本交接展开讨论，你提出先完成小范围验证，再把结果带回项目会上复盘。"
            "傍晚离开实验室前，你写下明天要跟进的三项事项，也决定把尚未解决的顾虑坦诚告诉合作方。"
        ) * 6
        long_story = medium_story + (
            "第二天的复盘让你确认了验证范围，也为下一次沟通准备了更清晰的备选方案。"
        ) * 2
        # 两个 Harness 已接受候选后，空文本不得覆盖其中较长的一个。
        client.call.side_effect = [medium_story, long_story, ""]

        mock_option_gen = MagicMock()
        mock_option_gen.generate_options_only.side_effect = Exception("option gen failed")

        gen._harness_enabled = True
        gen._validation_pipeline = MagicMock()
        gen._validation_pipeline.validate.side_effect = [
            MagicMock(passed=True, score=95, critical_failures=[], detailed_checks={}),
            MagicMock(passed=True, score=95, critical_failures=[], detailed_checks={}),
        ]
        gen._retry_controller = MagicMock()
        gen._retry_controller.should_retry.side_effect = [
            (False, None),
            (False, None),
        ]
        gen._diagnostics = MagicMock()
        gen._diagnostics.generate_report.return_value = {}
        gen._harness_metrics = MagicMock()

        with patch("src.ai.quick_validator.quick_validate_story") as mock_quick:
            mock_quick.return_value = MagicMock(passed=True, issues=[], warnings=[])

            event = gen.generate_round_event(
                player_state={"game_id": 1, "current_week": 1},
                language="zh",
                round_number=0,
                round_context="",
                option_generator=mock_option_gen,
            )

        # 应使用最长文本（第二次的结果）
        assert event.event_description == long_story
        assert len(event.event_description) > len(medium_story)
