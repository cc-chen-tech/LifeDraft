"""Story Generator Best Story Text Fallback DB Test

验证当所有 Harness 校验尝试都失败或最终故事文本过短时，
会使用之前尝试中生成的最佳故事文本（best_story_text），
而不是直接 fallback 到 "平静的一天"。
Layer 4: DB 集成测试 — 生成链路完整性。
"""

from unittest.mock import MagicMock, patch

from src.ai.harness.quality_level import QualityLevel
from src.ai.story_generator import StoryGenerator


class TestStoryGeneratorBestStoryFallback:
    """best_story_text fallback 行为测试"""

    def _make_generator(self, level: QualityLevel = QualityLevel.MASTER):
        """辅助函数：创建带 mock client 的 StoryGenerator."""
        mock_client = MagicMock()
        return StoryGenerator(mock_client, quality_level=level), mock_client

    def test_best_story_text_used_when_final_is_short(self):
        """最终 story_text 过短时，回退到 best_story_text"""
        gen, client = self._make_generator(QualityLevel.MASTER)

        long_story = (
            "这是一个很长的故事文本，远远超过了五十个字符的长度要求，"
            "讲述了主角在古代的冒险经历和各种奇遇，以及他如何克服困难。"
        )
        short_story = "短"

        # 第一次返回长文本（被记录为 best_story_text），
        # 第二次返回短文本（最终 story_text）
        client.call.side_effect = [long_story, short_story]

        mock_option_gen = MagicMock()
        mock_option_gen.generate_options_only.side_effect = Exception(
            "option gen failed"
        )

        # 模拟 Harness：第一次要求重试，第二次通过
        gen._harness_enabled = True
        gen._validation_pipeline = MagicMock()
        gen._validation_pipeline.validate.side_effect = [
            MagicMock(
                passed=False,
                score=50,
                critical_failures=["test"],
                detailed_checks={},
            ),
            MagicMock(
                passed=True,
                score=95,
                critical_failures=[],
                detailed_checks={},
            ),
        ]
        gen._retry_controller = MagicMock()
        gen._retry_controller.should_retry.side_effect = [
            (True, "fix it"),
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

        # 应使用 best_story_text（长故事），而非 fallback "平静的一天"
        assert "平静" not in event.event_description
        assert len(event.event_description) > 50
        assert event.event_description == long_story

    def test_fallback_used_when_no_best_story(self):
        """没有任何有效故事生成时才使用 fallback"""
        gen, client = self._make_generator(QualityLevel.MASTER)

        # 所有调用都返回极短文本
        client.call.return_value = "短"

        mock_option_gen = MagicMock()
        mock_option_gen.generate_options_only.side_effect = Exception(
            "option gen failed"
        )

        gen._harness_enabled = False

        with patch("src.ai.quick_validator.quick_validate_story") as mock_quick:
            mock_quick.return_value = MagicMock(passed=True, issues=[], warnings=[])

            event = gen.generate_round_event(
                player_state={"game_id": 1, "current_week": 1},
                language="zh",
                round_number=0,
                round_context="",
                option_generator=mock_option_gen,
            )

        # 当没有有效故事时，fallback 到 "平静的一天"
        assert (
            "平静" in event.event_description or "This day" in event.event_description
        )

    def test_best_story_tracks_longest_across_attempts(self):
        """best_story_text 应记录所有尝试中最长的文本"""
        gen, client = self._make_generator(QualityLevel.MASTER)

        medium_story = "中等长度的故事文本，描述了一些情节。" * 2
        long_story = "这是一个很长的故事文本，超过了很多字符。" * 5
        short_story = "短"

        # 第一次中等，第二次长（更新 best），第三次短（不更新 best）
        client.call.side_effect = [medium_story, long_story, short_story]

        mock_option_gen = MagicMock()
        mock_option_gen.generate_options_only.side_effect = Exception(
            "option gen failed"
        )

        gen._harness_enabled = True
        gen._validation_pipeline = MagicMock()
        gen._validation_pipeline.validate.side_effect = [
            MagicMock(
                passed=False, score=50, critical_failures=["fail"], detailed_checks={}
            ),
            MagicMock(
                passed=False, score=50, critical_failures=["fail"], detailed_checks={}
            ),
            MagicMock(passed=True, score=95, critical_failures=[], detailed_checks={}),
        ]
        gen._retry_controller = MagicMock()
        gen._retry_controller.should_retry.side_effect = [
            (True, "fix"),
            (True, "fix"),
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
