"""Story Generator Best Story Text Fallback DB Test

验证当后续 Harness 校验失败或最终故事文本过短时，
会使用之前尝试中 Harness 已接受的最佳故事文本（best_story_text），
而不是直接 fallback 到 "平静的一天"。
Layer 4: DB 集成测试 — 生成链路完整性。
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from src.ai.harness.quality_level import QualityLevel
from src.ai.models import EventOption, GameEvent
from src.ai.story_exceptions import StoryGenerationFailure
from src.ai.story_generator import StoryGenerator


class TestStoryGeneratorBestStoryFallback:
    """最长 Harness 已接受 best_story_text 的 fallback 行为测试"""

    def _make_generator(self, level: QualityLevel = QualityLevel.MASTER):
        """辅助函数：创建带 mock client 的 StoryGenerator."""
        mock_client = MagicMock()
        return StoryGenerator(mock_client, quality_level=level), mock_client

    def test_accepted_story_survives_a_longer_critical_candidate(self):
        """后续更长的 CRITICAL 候选不得覆盖先前 Harness 已接受故事。"""
        gen, client = self._make_generator(QualityLevel.EXPERT)

        accepted_story = (
            "你在清晨的图书馆整理实验记录，窗外的雨声提醒你即将到来的合作评审。"
            "你把协议中的风险条款逐条标记，并联系林一凡确认技术接口、预算节奏和联调日期。"
            "午后，团队针对数据权限和样本交接展开讨论，你提出先完成小范围验证，再把结果带回项目会上复盘。"
            "傍晚离开实验室前，你写下明天要跟进的三项事项，也决定把尚未解决的顾虑坦诚告诉合作方。"
        ) * 6
        rejected_story = accepted_story + (
            "第二天的复盘让你确认了验证范围，也为下一次沟通准备了更清晰的备选方案。"
        )

        # 第一次候选被 Harness 接受；第二次更长但 CRITICAL，第三次为空。
        client.call.side_effect = [accepted_story, rejected_story, ""]

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

        # 仅 Harness 已接受的候选可以作为上下文回退。
        assert "平静" not in event.event_description
        assert len(event.event_description) > 50
        assert event.event_description == accepted_story
        assert event.event_description != rejected_story

    def test_generation_fails_closed_when_no_valid_story(self):
        """没有任何有效故事时不得伪造一个可玩的 fallback。"""
        gen, client = self._make_generator(QualityLevel.MASTER)

        # 所有调用都返回极短文本
        client.call.return_value = "短"

        mock_option_gen = MagicMock()
        mock_option_gen.generate_options_only.side_effect = Exception("option gen failed")

        gen._harness_enabled = False

        with patch("src.ai.quick_validator.quick_validate_story") as mock_quick:
            mock_quick.return_value = MagicMock(passed=True, issues=[], warnings=[])

            with pytest.raises(StoryGenerationFailure):
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

    def test_expert_uses_all_three_attempts_and_delivers_best_soft_candidate(self):
        """仅有软告警时应耗尽专家档三次预算，再按告警数和分数择优。"""
        gen, client = self._make_generator(QualityLevel.EXPERT)

        story_a = (
            "你在清晨的图书馆整理实验记录，窗外的雨声提醒你即将到来的合作评审。"
            "你把协议中的风险条款逐条标记，并联系林一凡确认技术接口、预算节奏和联调日期。"
            "午后，团队针对数据权限和样本交接展开讨论，你提出先完成小范围验证，再把结果带回项目会上复盘。"
            "傍晚离开实验室前，你写下明天要跟进的三项事项，也决定把尚未解决的顾虑坦诚告诉合作方。"
        ) * 6
        story_b = story_a.replace("清晨", "上午", 1)
        story_c = story_a.replace("清晨", "午后", 1)
        stories = iter([story_a, story_b, story_c])

        def stream_candidate(**kwargs):
            story = next(stories)
            callback = kwargs.get("stream_callback")
            if callback:
                callback(story)
            return story

        client.call.side_effect = stream_candidate

        gen._harness_enabled = True
        gen._validation_pipeline = MagicMock()
        gen._validation_pipeline.validate.side_effect = [
            SimpleNamespace(
                passed=True,
                score=99.0,
                critical_failures=[],
                high_warnings=[
                    SimpleNamespace(constraint_type="pacing"),
                    SimpleNamespace(constraint_type="style"),
                ],
                medium_notes=[],
                low_notes=[],
            ),
            SimpleNamespace(
                passed=True,
                score=91.0,
                critical_failures=[],
                high_warnings=[SimpleNamespace(constraint_type="pacing")],
                medium_notes=[],
                low_notes=[],
            ),
            SimpleNamespace(
                passed=True,
                score=83.0,
                critical_failures=[],
                high_warnings=[SimpleNamespace(constraint_type="pacing")],
                medium_notes=[],
                low_notes=[],
            ),
        ]
        gen._retry_controller = MagicMock()
        gen._diagnostics = MagicMock()
        gen._diagnostics.generate_report.return_value = {}
        gen._harness_metrics = MagicMock()

        option_generator = MagicMock()
        option_generator.generate_options_only.return_value = GameEvent(
            event_description="unused",
            options=[
                EventOption(text="继续核对", effects={}),
                EventOption(text="联系伙伴", effects={}),
            ],
        )

        streamed_chunks = []
        with patch("src.ai.quick_validator.quick_validate_story") as mock_quick:
            mock_quick.return_value = SimpleNamespace(
                passed=True,
                issues=[],
                warnings=[],
            )

            event = gen.generate_round_event(
                player_state={"game_id": 1, "current_week": 1},
                language="zh",
                round_number=0,
                round_context="",
                option_generator=option_generator,
                stream_callback=streamed_chunks.append,
            )

        assert client.call.call_count == 3
        assert event.event_description == story_b
        assert event.delivery_notice is not None
        assert event.delivery_notice.code == "SOFT_VALIDATION_FALLBACK"
        assert event.delivery_notice.attempts_used == 3
        assert "内部" not in event.delivery_notice.reason
        assert streamed_chunks == [story_b]
        option_generator.generate_options_only.assert_not_called()

    def test_hard_rejected_candidates_never_enter_soft_fallback_pool(self):
        """所有候选均有硬错误时仍须失败，且不能为拒绝稿生成选项。"""
        gen, client = self._make_generator(QualityLevel.EXPERT)
        rejected_story = (
            "你在会议室里见到一个与既有设定冲突的人物，对方要求你立刻放弃已经确认的计划。"
            "你没有接受这个要求，而是重新核对关系记录、时间线和当天必须完成的事项。"
        ) * 10
        def stream_rejected(**kwargs):
            callback = kwargs.get("stream_callback")
            if callback:
                callback(rejected_story)
            return rejected_story

        client.call.side_effect = stream_rejected
        gen._harness_enabled = False
        option_generator = MagicMock()

        streamed_chunks = []
        with patch("src.ai.quick_validator.quick_validate_story") as mock_quick:
            mock_quick.return_value = SimpleNamespace(
                passed=False,
                issues=["名单外命名角色：冲突人物"],
                warnings=[],
            )

            with pytest.raises(StoryGenerationFailure):
                gen.generate_round_event(
                    player_state={"game_id": 1, "current_week": 1},
                    language="zh",
                    round_number=0,
                    round_context="",
                    option_generator=option_generator,
                    stream_callback=streamed_chunks.append,
                )

        assert streamed_chunks == []
        option_generator.generate_options_only.assert_not_called()

    def test_every_harness_critical_failure_is_hard(self):
        """任何 Harness critical 类别都不能作为干净或软告警稿交付。"""
        gen, client = self._make_generator(QualityLevel.EXPERT)
        story = (
            "你在办公室核对今天的实验记录，并把会议结论逐项写入项目日志。"
            "同事随后与你确认下一步安排，你决定先验证关键假设，再继续推进合作。"
        ) * 10
        client.call.side_effect = [story, story, story]
        gen._soft_narrative_lengths = True
        gen._harness_enabled = True
        gen._validation_pipeline = MagicMock()
        critical = SimpleNamespace(
            constraint_type="third_person",
            evidence="叙事视角不符合要求",
        )
        gen._validation_pipeline.validate.return_value = SimpleNamespace(
            passed=False,
            score=20.0,
            critical_failures=[critical],
            high_warnings=[],
            medium_notes=[],
            low_notes=[],
        )
        gen._diagnostics = MagicMock()
        gen._diagnostics.generate_report.return_value = {}
        streamed_chunks = []

        with patch("src.ai.quick_validator.quick_validate_story") as mock_quick:
            mock_quick.return_value = SimpleNamespace(passed=True, issues=[], warnings=[])
            with pytest.raises(StoryGenerationFailure):
                gen.generate_round_event(
                    player_state={"game_id": 1, "current_week": 1},
                    language="zh",
                    round_number=0,
                    round_context="",
                    option_generator=MagicMock(),
                    stream_callback=streamed_chunks.append,
                )

        assert streamed_chunks == []

    def test_consistency_repair_is_rechecked_by_quick_validator(self):
        """一致性修订改变文本后，新的硬 quick finding 必须阻止交付。"""
        gen, client = self._make_generator(QualityLevel.EXPERT)
        initial_story = (
            "你在办公室核对今天的实验记录，并把会议结论逐项写入项目日志。"
            "同事随后与你确认下一步安排，你决定先验证关键假设，再继续推进合作。"
        ) * 10
        repaired_but_hard_invalid = initial_story.replace("同事", "名单外人物", 1)
        client.call.return_value = initial_story
        gen._soft_narrative_lengths = True
        gen._harness_enabled = False
        gen._validate_and_retry_story = MagicMock(return_value=repaired_but_hard_invalid)
        streamed_chunks = []

        with patch("src.ai.quick_validator.quick_validate_story") as mock_quick:
            mock_quick.side_effect = [
                SimpleNamespace(passed=True, issues=[], warnings=[]),
                SimpleNamespace(
                    passed=False,
                    issues=["名单外命名角色：名单外人物"],
                    warnings=[],
                ),
            ] * 3
            with pytest.raises(StoryGenerationFailure):
                gen.generate_round_event(
                    player_state={"game_id": 1, "current_week": 1},
                    language="zh",
                    round_number=0,
                    round_context="",
                    world_model=object(),
                    option_generator=MagicMock(),
                    stream_callback=streamed_chunks.append,
                )

        assert streamed_chunks == []
