"""Tests for RoundFinalizer service."""

import threading
import time
from unittest.mock import MagicMock, patch

from src.game.round.finalizer import RoundFinalizer
import pytest

pytestmark = [pytest.mark.unit, pytest.mark.slow]



class TestRoundFinalizerInit:
    """Test RoundFinalizer initialization."""

    def test_init_with_all_dependencies(self):
        """Test initialization with all dependencies."""
        mock_get_state = MagicMock()
        mock_ai = MagicMock()
        mock_lang = MagicMock()
        mock_story = MagicMock()
        mock_char = MagicMock()

        finalizer = RoundFinalizer(
            player_state_getter=mock_get_state,
            ai_generator=mock_ai,
            language_getter=mock_lang,
            story_service=mock_story,
            character_creator=mock_char,
        )

        assert finalizer._get_player_state == mock_get_state
        assert finalizer.ai_generator == mock_ai
        assert finalizer._get_language == mock_lang
        assert finalizer.story_service == mock_story
        assert finalizer.character_creator == mock_char


class TestPlayerStateProperty:
    """Test player_state property."""

    def test_player_state_calls_getter(self):
        """Test that player_state property calls the getter."""
        mock_state = MagicMock()
        mock_get_state = MagicMock(return_value=mock_state)

        finalizer = RoundFinalizer(
            player_state_getter=mock_get_state,
            ai_generator=MagicMock(),
            language_getter=MagicMock(),
            story_service=MagicMock(),
            character_creator=MagicMock(),
        )

        result = finalizer.player_state
        mock_get_state.assert_called_once()
        assert result == mock_state


class TestLanguageProperty:
    """Test language property."""

    def test_language_calls_getter(self):
        """Test that language property calls the getter."""
        mock_get_lang = MagicMock(return_value="zh")

        finalizer = RoundFinalizer(
            player_state_getter=MagicMock(),
            ai_generator=MagicMock(),
            language_getter=mock_get_lang,
            story_service=MagicMock(),
            character_creator=MagicMock(),
        )

        result = finalizer.language
        mock_get_lang.assert_called_once()
        assert result == "zh"


class TestFinalizeWeek:
    """Test finalize_week method."""

    def test_finalize_week_without_callback(self):
        """Test finalize_week without status callback."""
        mock_state = MagicMock()
        mock_state.week = 1
        mock_state.get_game_date_info = MagicMock(return_value={"year": 1, "week": 1})
        mock_state.weekly_summaries = []
        mock_state.get_current_week_rounds = MagicMock(return_value=[{"story": "test"}])
        mock_state.character_settings = {}

        mock_ai = MagicMock()
        mock_ai.generate_weekly_summary = MagicMock(
            return_value={
                "summary": "Test summary",
                "bonus_effects": {"energy": 5, "mood": 3},
            }
        )

        finalizer = RoundFinalizer(
            player_state_getter=MagicMock(return_value=mock_state),
            ai_generator=mock_ai,
            language_getter=MagicMock(return_value="zh"),
            story_service=MagicMock(),
            character_creator=MagicMock(),
        )

        result = {}
        with patch.object(finalizer, "_apply_weekly_decay"):
            with patch.object(finalizer, "_check_and_fix_missing_attributes"):
                with patch(
                    "src.game.round.finalizer.WorldModelUpdater.synthesize_character_profiles"
                ):
                    finalizer.finalize_week(result)

        assert result["weekly_summary"] == "Test summary"
        assert result["bonus_effects"] == {"energy": 5, "mood": 3}

    def test_finalize_week_with_callback(self):
        """Test finalize_week with status callback."""
        mock_state = MagicMock()
        mock_state.week = 1
        mock_state.get_game_date_info = MagicMock(return_value={})
        mock_state.weekly_summaries = []
        mock_state.get_current_week_rounds = MagicMock(return_value=[])
        mock_state.character_settings = {}

        mock_callback = MagicMock()

        finalizer = RoundFinalizer(
            player_state_getter=MagicMock(return_value=mock_state),
            ai_generator=MagicMock(),
            language_getter=MagicMock(return_value="zh"),
            story_service=MagicMock(),
            character_creator=MagicMock(),
        )

        result = {}
        with patch.object(finalizer, "_apply_weekly_decay"):
            with patch("src.game.round.finalizer.WorldModelUpdater.synthesize_character_profiles"):
                finalizer.finalize_week(result, status_callback=mock_callback)

        mock_callback.assert_called_with("weekly_summary")

    def test_finalize_week_applies_bonus_effects(self):
        """Test that bonus effects are applied to player state."""
        mock_state = MagicMock()
        mock_state.week = 1
        mock_state.get_game_date_info = MagicMock(return_value={})
        mock_state.weekly_summaries = []
        mock_state.get_current_week_rounds = MagicMock(return_value=[{"story": "test"}])
        mock_state.character_settings = {}

        mock_ai = MagicMock()
        mock_ai.generate_weekly_summary = MagicMock(
            return_value={
                "summary": "Test",
                "bonus_effects": {"energy": 10, "mood": 5, "knowledge": 3, "wealth": 2},
            }
        )

        finalizer = RoundFinalizer(
            player_state_getter=MagicMock(return_value=mock_state),
            ai_generator=mock_ai,
            language_getter=MagicMock(return_value="zh"),
            story_service=MagicMock(),
            character_creator=MagicMock(),
        )

        result = {}
        with patch.object(finalizer, "_apply_weekly_decay"):
            with patch.object(finalizer, "_check_and_fix_missing_attributes"):
                with patch(
                    "src.game.round.finalizer.WorldModelUpdater.synthesize_character_profiles"
                ):
                    finalizer.finalize_week(result)

        mock_state.update.assert_called_once_with(energy=10, mood=5, knowledge=3)

    def test_finalize_week_does_not_wait_for_slow_enrichment_tasks(self):
        """Slow post-week enrichment must not block the choice response."""
        mock_state = MagicMock()
        mock_state.week = 3
        mock_state.get_game_date_info = MagicMock(return_value={})
        mock_state.weekly_summaries = [
            {"week": 0, "summary": "Week 0"},
            {"week": 1, "summary": "Week 1"},
            {"week": 2, "summary": "Week 2"},
        ]
        mock_state.get_current_week_rounds = MagicMock(return_value=[{"story": "test"}])
        mock_state.character_settings = {}
        mock_state.advance_week.side_effect = lambda: setattr(mock_state, "week", 4)

        mock_ai = MagicMock()
        mock_ai.ai_client = MagicMock()
        mock_ai.generate_weekly_summary = MagicMock(
            return_value={"summary": "Week summary", "bonus_effects": {}}
        )

        finalizer = RoundFinalizer(
            player_state_getter=MagicMock(return_value=mock_state),
            ai_generator=mock_ai,
            language_getter=MagicMock(return_value="zh"),
            story_service=MagicMock(),
            character_creator=MagicMock(),
        )

        def slow_profile_synthesis(*_args, **_kwargs):
            time.sleep(0.25)

        result = {}
        with patch.object(finalizer, "_apply_weekly_decay"):
            with patch.object(finalizer, "_check_and_fix_missing_attributes"):
                with patch(
                    "src.game.round.finalizer.WorldModelUpdater.synthesize_character_profiles",
                    side_effect=slow_profile_synthesis,
                ):
                    start = time.perf_counter()
                    finalizer.finalize_week(result)
                    duration = time.perf_counter() - start

        assert duration < 0.15
        assert result["weekly_summary"] == "Week summary"
        mock_state.advance_week.assert_called_once()


class TestGenerateWeeklySummary:
    """Test generate_weekly_summary method."""

    def test_generate_weekly_summary_no_state(self):
        """Test weekly summary when no player state."""
        finalizer = RoundFinalizer(
            player_state_getter=MagicMock(return_value=None),
            ai_generator=MagicMock(),
            language_getter=MagicMock(),
            story_service=MagicMock(),
            character_creator=MagicMock(),
        )

        result = finalizer.generate_weekly_summary()
        assert result == {"summary": "", "bonus_effects": {}}

    def test_generate_weekly_summary_no_rounds_zh(self):
        """Test weekly summary with no rounds in Chinese."""
        mock_state = MagicMock()
        mock_state.get_current_week_rounds = MagicMock(return_value=[])

        finalizer = RoundFinalizer(
            player_state_getter=MagicMock(return_value=mock_state),
            ai_generator=MagicMock(),
            language_getter=MagicMock(return_value="zh"),
            story_service=MagicMock(),
            character_creator=MagicMock(),
        )

        result = finalizer.generate_weekly_summary()
        assert "平静" in result["summary"]

    def test_generate_weekly_summary_no_rounds_en(self):
        """Test weekly summary with no rounds in English."""
        mock_state = MagicMock()
        mock_state.get_current_week_rounds = MagicMock(return_value=[])

        finalizer = RoundFinalizer(
            player_state_getter=MagicMock(return_value=mock_state),
            ai_generator=MagicMock(),
            language_getter=MagicMock(return_value="en"),
            story_service=MagicMock(),
            character_creator=MagicMock(),
        )

        result = finalizer.generate_weekly_summary()
        assert "quietly" in result["summary"]

    def test_generate_weekly_summary_with_rounds(self):
        """Test weekly summary with rounds."""
        mock_state = MagicMock()
        mock_state.get_current_week_rounds = MagicMock(
            return_value=[{"story": "Story 1", "choice": "Choice 1"}]
        )
        mock_state.character_settings = {"name": "Test"}
        mock_state.get_game_date_info = MagicMock(return_value={"year": 1})

        mock_ai = MagicMock()
        mock_ai.generate_weekly_summary = MagicMock(
            return_value={"summary": "Week summary", "bonus_effects": {}}
        )

        finalizer = RoundFinalizer(
            player_state_getter=MagicMock(return_value=mock_state),
            ai_generator=mock_ai,
            language_getter=MagicMock(return_value="zh"),
            story_service=MagicMock(),
            character_creator=MagicMock(),
        )

        result = finalizer.generate_weekly_summary()
        assert result["summary"] == "Week summary"

    def test_generate_weekly_summary_handles_exception(self):
        """Test weekly summary handles exceptions."""
        mock_state = MagicMock()
        mock_state.get_current_week_rounds = MagicMock(return_value=[{"story": "test"}])
        mock_state.character_settings = {}
        mock_state.get_game_date_info = MagicMock(return_value={})

        mock_ai = MagicMock()
        mock_ai.generate_weekly_summary = MagicMock(side_effect=Exception("AI error"))

        finalizer = RoundFinalizer(
            player_state_getter=MagicMock(return_value=mock_state),
            ai_generator=mock_ai,
            language_getter=MagicMock(return_value="zh"),
            story_service=MagicMock(),
            character_creator=MagicMock(),
        )

        result = finalizer.generate_weekly_summary()
        assert "充实" in result["summary"]


class TestCompressRoundStory:
    """Test compress_round_story method."""

    def test_compress_round_story(self):
        """Test story compression delegation."""
        mock_state = MagicMock()
        mock_state.pending_storylines = []
        mock_state.established_facts = []
        mock_state.character_habits = []

        mock_story_service = MagicMock()
        mock_story_service.compress_story = MagicMock(return_value={"summary": "compressed"})

        finalizer = RoundFinalizer(
            player_state_getter=MagicMock(return_value=mock_state),
            ai_generator=MagicMock(),
            language_getter=MagicMock(),
            story_service=mock_story_service,
            character_creator=MagicMock(),
        )

        finalizer.compress_round_story("test story", "test choice")
        mock_story_service.compress_story.assert_called_once_with(
            "test story", "test choice", [], [], []
        )

    def test_compress_round_story_no_state(self):
        """Test story compression with no state."""
        mock_story_service = MagicMock()
        mock_story_service.compress_story = MagicMock(return_value={"summary": "compressed"})

        finalizer = RoundFinalizer(
            player_state_getter=MagicMock(return_value=None),
            ai_generator=MagicMock(),
            language_getter=MagicMock(),
            story_service=mock_story_service,
            character_creator=MagicMock(),
        )

        finalizer.compress_round_story("test story", "test choice")
        mock_story_service.compress_story.assert_called_once_with(
            "test story", "test choice", [], [], []
        )


class TestGetRoundInfo:
    """Test get_round_info method."""

    def test_get_round_info_no_state(self):
        """Test round info with no state."""
        finalizer = RoundFinalizer(
            player_state_getter=MagicMock(return_value=None),
            ai_generator=MagicMock(),
            language_getter=MagicMock(),
            story_service=MagicMock(),
            character_creator=MagicMock(),
        )

        result = finalizer.get_round_info()
        assert result == {}

    def test_get_round_info_with_state(self):
        """Test round info with state."""
        mock_state = MagicMock()
        mock_state.week = 2
        mock_state.current_round = 3
        mock_state.rounds_per_week = 7
        mock_state.get_round_name = MagicMock(return_value="Wednesday")
        mock_state.get_current_week_rounds = MagicMock(return_value=[{}, {}, {}])

        finalizer = RoundFinalizer(
            player_state_getter=MagicMock(return_value=mock_state),
            ai_generator=MagicMock(),
            language_getter=MagicMock(),
            story_service=MagicMock(),
            character_creator=MagicMock(),
        )

        result = finalizer.get_round_info()
        assert result["week"] == 2
        assert result["current_round"] == 3
        assert result["rounds_per_week"] == 7
        assert result["round_name"] == "Wednesday"
        assert result["is_last_round"] is False
        assert result["week_rounds_completed"] == 3


class TestApplyWeeklyDecay:
    """Test _apply_weekly_decay method."""

    def test_apply_weekly_decay(self):
        """Test weekly decay is applied."""
        mock_state = MagicMock()

        finalizer = RoundFinalizer(
            player_state_getter=MagicMock(return_value=mock_state),
            ai_generator=MagicMock(),
            language_getter=MagicMock(),
            story_service=MagicMock(),
            character_creator=MagicMock(),
        )

        finalizer._apply_weekly_decay()
        mock_state.update.assert_called_once_with(mood=-2)

    def test_apply_weekly_decay_no_state(self):
        """Test weekly decay with no state."""
        finalizer = RoundFinalizer(
            player_state_getter=MagicMock(return_value=None),
            ai_generator=MagicMock(),
            language_getter=MagicMock(),
            story_service=MagicMock(),
            character_creator=MagicMock(),
        )

        # Should not raise
        finalizer._apply_weekly_decay()


class TestCheckAndFixMissingAttributes:
    """Test _check_and_fix_missing_attributes method."""

    def test_check_and_fix_missing_attributes(self):
        """Test attribute check delegation."""
        mock_state = MagicMock()
        mock_char_creator = MagicMock()

        finalizer = RoundFinalizer(
            player_state_getter=MagicMock(return_value=mock_state),
            ai_generator=MagicMock(),
            language_getter=MagicMock(),
            story_service=MagicMock(),
            character_creator=mock_char_creator,
        )

        finalizer._check_and_fix_missing_attributes()
        mock_char_creator.check_and_fix_missing_attributes.assert_called_once_with(mock_state)

    def test_check_and_fix_missing_attributes_no_state(self):
        """Test attribute check with no state."""
        finalizer = RoundFinalizer(
            player_state_getter=MagicMock(return_value=None),
            ai_generator=MagicMock(),
            language_getter=MagicMock(),
            story_service=MagicMock(),
            character_creator=MagicMock(),
        )

        # Should not raise
        finalizer._check_and_fix_missing_attributes()


class TestGenerateFamilyMembersDetails:
    """Test _generate_family_members_details method."""

    def test_generate_family_members_details(self):
        """Test family members generation delegation."""
        mock_state = MagicMock()
        mock_state.character_settings = {"name": "Test"}
        mock_state.player_name = "Player"

        mock_char_creator = MagicMock()
        mock_char_creator.generate_family_members_details = MagicMock(
            return_value=[{"name": "Mom", "role": "mother"}]
        )

        finalizer = RoundFinalizer(
            player_state_getter=MagicMock(return_value=mock_state),
            ai_generator=MagicMock(),
            language_getter=MagicMock(),
            story_service=MagicMock(),
            character_creator=mock_char_creator,
        )

        result = finalizer._generate_family_members_details([{"name": "Mom"}])
        assert len(result) == 1

    def test_generate_family_members_details_no_state(self):
        """Test family members generation with no state."""
        finalizer = RoundFinalizer(
            player_state_getter=MagicMock(return_value=None),
            ai_generator=MagicMock(),
            language_getter=MagicMock(),
            story_service=MagicMock(),
            character_creator=MagicMock(),
        )

        result = finalizer._generate_family_members_details([{"name": "Mom"}])
        assert result == []


class TestGenerateFourWeekSummary:
    """Test _generate_four_week_summary method."""

    def test_generate_four_week_summary(self):
        """Test 4-week summary generation."""
        mock_state = MagicMock()
        mock_state.weekly_summaries = [
            {"week": 1, "summary": "Week 1"},
            {"week": 2, "summary": "Week 2"},
            {"week": 3, "summary": "Week 3"},
            {"week": 4, "summary": "Week 4"},
        ]
        mock_state.four_week_summaries = []

        finalizer = RoundFinalizer(
            player_state_getter=MagicMock(return_value=mock_state),
            ai_generator=MagicMock(),
            language_getter=MagicMock(),
            story_service=MagicMock(),
            character_creator=MagicMock(),
        )

        finalizer._generate_four_week_summary(4)
        assert len(mock_state.four_week_summaries) == 1

    def test_generate_four_week_summary_insufficient_data(self):
        """Test 4-week summary with insufficient data."""
        mock_state = MagicMock()
        mock_state.weekly_summaries = [
            {"week": 1, "summary": "Week 1"},
        ]

        finalizer = RoundFinalizer(
            player_state_getter=MagicMock(return_value=mock_state),
            ai_generator=MagicMock(),
            language_getter=MagicMock(),
            story_service=MagicMock(),
            character_creator=MagicMock(),
        )

        finalizer._generate_four_week_summary(4)
        assert (
            not hasattr(mock_state, "four_week_summaries")
            or len(mock_state.four_week_summaries) == 0
        )


class TestGenerateYearlySummary:
    """Test _generate_yearly_summary method."""

    def test_generate_yearly_summary(self):
        """Test yearly summary generation."""
        mock_state = MagicMock()
        mock_state.four_week_summaries = [{"week": i * 4, "summaries": []} for i in range(12)]
        mock_state.yearly_summaries = []

        finalizer = RoundFinalizer(
            player_state_getter=MagicMock(return_value=mock_state),
            ai_generator=MagicMock(),
            language_getter=MagicMock(),
            story_service=MagicMock(),
            character_creator=MagicMock(),
        )

        finalizer._generate_yearly_summary(48)
        assert len(mock_state.yearly_summaries) == 1

    def test_generate_yearly_summary_insufficient_data(self):
        """Test yearly summary with insufficient data."""
        mock_state = MagicMock()
        mock_state.four_week_summaries = [
            {"week": 4, "summaries": []},
        ]

        finalizer = RoundFinalizer(
            player_state_getter=MagicMock(return_value=mock_state),
            ai_generator=MagicMock(),
            language_getter=MagicMock(),
            story_service=MagicMock(),
            character_creator=MagicMock(),
        )

        finalizer._generate_yearly_summary(48)
        assert not hasattr(mock_state, "yearly_summaries") or len(mock_state.yearly_summaries) == 0


class TestPostWeekEnrichmentSerialization:
    """P0-并发修复：富化任务共享 player_state，必须串行执行避免竞态。"""

    def _make_finalizer(self, mock_state):
        return RoundFinalizer(
            player_state_getter=MagicMock(return_value=mock_state),
            ai_generator=MagicMock(),
            language_getter=MagicMock(return_value="zh"),
            story_service=MagicMock(),
            character_creator=MagicMock(),
        )

    def test_enrichment_tasks_run_serially(self):
        """同一周的富化任务按顺序执行，不允许并行写共享状态。"""
        mock_state = MagicMock()
        finalizer = self._make_finalizer(mock_state)

        events: list[tuple[str, float]] = []
        order_lock = threading.Lock()

        def slow_task(name: str, delay: float):
            start = time.perf_counter()
            time.sleep(delay)
            with order_lock:
                events.append((name, start))

        def synth(*_a, **_k):
            slow_task("synthesize", 0.05)

        def items(week):
            slow_task("items", 0.05)

        def landmarks(week):
            slow_task("landmarks", 0.05)

        with patch(
            "src.game.round.finalizer.WorldModelUpdater.synthesize_character_profiles",
            side_effect=synth,
        ), patch.object(finalizer, "_extract_items_from_week", side_effect=items), patch.object(
            finalizer, "_extract_landmarks_from_week", side_effect=landmarks
        ):
            finalizer._run_post_week_enrichment_tasks(1)

        names = [name for name, _ in events]
        assert names == ["synthesize", "items", "landmarks"]
        # 严格串行：下一个任务开始时间不早于上一个任务开始+延迟
        starts = [start for _, start in events]
        assert starts[1] >= starts[0] + 0.04
        assert starts[2] >= starts[1] + 0.04

    def test_enrichment_failure_does_not_skip_other_tasks(self):
        """任一富化任务失败不应跳过其余任务。"""
        mock_state = MagicMock()
        finalizer = self._make_finalizer(mock_state)
        ran = {"items": False, "landmarks": False}

        def failing_synth(*_a, **_k):
            raise RuntimeError("synth boom")

        def items(week):
            ran["items"] = True

        def landmarks(week):
            ran["landmarks"] = True

        with patch(
            "src.game.round.finalizer.WorldModelUpdater.synthesize_character_profiles",
            side_effect=failing_synth,
        ), patch.object(finalizer, "_extract_items_from_week", side_effect=items), patch.object(
            finalizer, "_extract_landmarks_from_week", side_effect=landmarks
        ):
            finalizer._run_post_week_enrichment_tasks(1)

        assert ran["items"] and ran["landmarks"]
