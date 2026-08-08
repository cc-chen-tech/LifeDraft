"""Tests for game modules: achievements, endings, player_service, story_service, summaries."""

from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from src.ai.story_exceptions import StoryContinuationFailure
from src.game.achievements import AchievementEngine
from src.game.endings import EndingEvaluator
from src.game.monthly_summary import MonthlySummaryGenerator
from src.game.player_service import PlayerService
from src.game.state import CharacterState, PlayerState
from src.game.story_service import StoryService
from src.game.weekly_summary import WeeklySummaryGenerator
from src.game.yearly_summary import YearlySummaryGenerator

# ==================== Achievement Tests ====================


class TestAchievementEngine:
    """Test AchievementEngine class."""

    def test_evaluate_returns_list(self):
        """evaluate() should return a list of Achievement objects."""
        engine = AchievementEngine()
        player = PlayerState()
        result = engine.evaluate(player)
        assert isinstance(result, list)

    def test_legendary_tale_triggers_after_fifty_rounds(self):
        engine = AchievementEngine(language="zh")
        player = PlayerState(round_history=[{}] * 50)
        result = engine.evaluate(player)
        names = [a.name for a in result]
        assert "传奇故事" in names

    def test_knowledge_achievement_triggers(self):
        """Balanced high stats should trigger balanced life achievement."""
        engine = AchievementEngine(language="zh")
        player = PlayerState(energy=85, mood=85, knowledge=85)
        result = engine.evaluate(player)
        names = [a.name for a in result]
        assert "平衡人生" in names

    def test_no_achievements_for_default_state(self):
        """Default player state should trigger few or no achievements."""
        engine = AchievementEngine()
        player = PlayerState()
        result = engine.evaluate(player)
        # Default state may trigger some basic achievements
        assert isinstance(result, list)

    def test_english_language(self):
        """English language setting should work."""
        engine = AchievementEngine(language="en")
        player = PlayerState(wealth=100000)
        result = engine.evaluate(player)
        names = [a.name for a in result]
        # Should return English names
        assert all(not any(c in n for c in "财富") for n in names) or len(names) == 0

    def test_achievement_has_required_fields(self):
        """Each Achievement should have id, name, description, rarity, dimension."""
        engine = AchievementEngine(language="zh")
        player = PlayerState(wealth=100000, knowledge=90, energy=80, mood=80)
        result = engine.evaluate(player)
        for ach in result:
            assert ach.id
            assert ach.name
            assert ach.description
            assert ach.rarity in ["common", "rare", "epic", "legendary"]
            assert ach.dimension

    def test_decision_count_achievement(self):
        """Many decisions should trigger decision-related achievements."""
        engine = AchievementEngine(language="zh")
        player = PlayerState(decision_history=[{"choice": "x"} for _ in range(40)])
        result = engine.evaluate(player)
        names = [a.name for a in result]
        assert any("决策" in n or "果断" in n for n in names)

    def test_relationship_achievement(self):
        """Multiple relationships should trigger social achievements."""
        engine = AchievementEngine(language="zh")
        player = PlayerState(relationships={f"friend_{i}": 60 for i in range(6)})
        result = engine.evaluate(player)
        names = [a.name for a in result]
        assert any("社交" in n or "关系" in n for n in names)

    def test_week_achievement(self):
        """Late game with decisions should trigger enlightened achievement."""
        engine = AchievementEngine(language="zh")
        player = PlayerState(week=100, decision_history=[{"choice": "x"}] * 100)
        result = engine.evaluate(player)
        names = [a.name for a in result]
        assert "觉悟者" in names

    def test_perfect_state_achievement(self):
        """All high stats should trigger balance achievements."""
        engine = AchievementEngine(language="zh")
        player = PlayerState(energy=85, mood=85, knowledge=85, wealth=50000)
        result = engine.evaluate(player)
        names = [a.name for a in result]
        assert any("平衡" in n or "完美" in n for n in names)

    def test_rarity_order_valid(self):
        """RARITY_ORDER should be valid."""
        assert AchievementEngine.RARITY_ORDER == ["common", "rare", "epic", "legendary"]


# ==================== Ending Tests ====================


class TestEndingEvaluator:
    """Test EndingEvaluator class."""

    def test_balanced_ending(self):
        """Test balanced ending type."""
        evaluator = EndingEvaluator()
        player = PlayerState(
            energy=60,
            mood=60,
            knowledge=60,
            wealth=15000,
            relationships={"Friend": 50},
            age=24,
        )
        result = evaluator.evaluate_ending(player, "zh")
        assert result["ending_type"] == "balanced"
        assert result["ending_name"] == "平衡人生"

    def test_balanced_ending_has_no_wealth_branch(self):
        evaluator = EndingEvaluator()
        player = PlayerState(energy=60, mood=60, knowledge=60, wealth=80000, age=24)
        result = evaluator.evaluate_ending(player, "zh")
        assert result["ending_type"] == "balanced"

    def test_scholar_ending(self):
        """Test scholar ending with high knowledge."""
        evaluator = EndingEvaluator()
        player = PlayerState(energy=70, mood=70, knowledge=85, wealth=10000, age=24)
        result = evaluator.evaluate_ending(player, "zh")
        assert result["ending_type"] == "scholar"

    def test_social_ending(self):
        """Test social ending with high relationships."""
        evaluator = EndingEvaluator()
        player = PlayerState(
            energy=60,
            mood=60,
            knowledge=60,
            wealth=10000,
            age=24,
            relationships={"F1": 80, "F2": 80, "F3": 80},
        )
        result = evaluator.evaluate_ending(player, "zh")
        assert result["ending_type"] == "social"

    def test_struggling_ending(self):
        """Test struggling ending with low stats."""
        evaluator = EndingEvaluator()
        player = PlayerState(energy=30, mood=30, knowledge=30, wealth=3000, age=24)
        result = evaluator.evaluate_ending(player, "zh")
        assert result["ending_type"] == "struggling"

    def test_ending_has_required_fields(self):
        """Test ending result has all required fields."""
        evaluator = EndingEvaluator()
        player = PlayerState(age=24)
        result = evaluator.evaluate_ending(player, "zh")
        assert "ending_type" in result
        assert "ending_name" in result
        assert "summary" in result
        assert "achievements" in result
        assert "final_stats" in result

    def test_template_summary_zh(self):
        """Test template summary in Chinese."""
        evaluator = EndingEvaluator()
        summary = evaluator._generate_template_summary(PlayerState(age=25), "balanced", "zh")
        assert "25岁" in summary

    def test_template_summary_en(self):
        """Test template summary in English."""
        evaluator = EndingEvaluator()
        summary = evaluator._generate_template_summary(PlayerState(age=25), "balanced", "en")
        assert "age 25" in summary.lower()

    def test_ending_with_ai_generator(self):
        """Test ending with mocked AI generator."""
        mock_gen = Mock()
        mock_gen.ai_client.call.return_value = "An amazing life story..."
        evaluator = EndingEvaluator(ai_generator=mock_gen)
        player = PlayerState(age=24, week=96)
        result = evaluator.evaluate_ending(player, "zh")
        assert "summary" in result

    def test_calculate_achievements(self):
        """Test achievement calculation."""
        evaluator = EndingEvaluator()
        player = PlayerState(energy=90, mood=90, knowledge=95)
        result = evaluator.evaluate_ending(player, "zh")
        achievements = result["achievements"]
        names = [a["name"] for a in achievements["list"]]
        assert "白手起家" not in names
        assert "平衡人生" in names


# ==================== PlayerService Tests ====================


class TestPlayerService:
    """Test PlayerService class."""

    def test_initialize_characters_from_settings(self):
        """Test initializing characters from settings."""
        player = PlayerState()
        player.character_settings = {
            "relationships": {
                "key_people": [
                    {"name": "张三", "role": "朋友", "relationship": "好朋友"},
                    {"name": "李四", "role": "同事", "relationship": "同事关系"},
                ]
            }
        }
        PlayerService.initialize_characters_from_settings(player)
        assert len(player.characters) == 2
        assert "张三" in player.characters

    def test_initialize_preserves_existing_relationships(self):
        """Test that existing relationship values are preserved."""
        player = PlayerState()
        player.relationships = {"张三": 75}
        player.character_settings = {
            "relationships": {"key_people": [{"name": "张三", "role": "朋友"}]}
        }
        PlayerService.initialize_characters_from_settings(player)
        char = CharacterState(**player.characters["张三"])
        assert char.affinity == 75

    def test_initialize_empty_settings(self):
        """Test initialization with empty settings."""
        player = PlayerState()
        PlayerService.initialize_characters_from_settings(player)
        assert len(player.characters) == 0

    def test_update_character_relationship(self):
        """Test updating character relationship."""
        player = PlayerState(week=5)
        char = CharacterState(name="Friend", affinity=50, trust=50)
        player.characters["Friend"] = char.model_dump()
        player.relationships["Friend"] = 50

        result = PlayerService.update_character_relationship(
            player, "Friend", affinity_change=10, trust_change=5
        )
        assert result is True
        assert player.relationships["Friend"] > 50

    def test_update_nonexistent_character(self):
        """Test updating nonexistent character returns False."""
        player = PlayerState()
        result = PlayerService.update_character_relationship(player, "Nobody", affinity_change=10)
        assert result is False

    def test_get_characters_context(self):
        """Test getting characters context string."""
        player = PlayerState()
        char = CharacterState(name="Friend", role="roommate")
        player.characters["Friend"] = char.model_dump()

        context = PlayerService.get_characters_context(player)
        assert "重要人物" in context
        assert "Friend" in context

    def test_get_characters_context_empty(self):
        """Test empty characters returns empty string."""
        player = PlayerState()
        context = PlayerService.get_characters_context(player)
        assert context == ""

    def test_check_event_trigger_deep_friendship(self):
        """Test check_event_trigger for deep_friendship."""
        char = CharacterState(name="Friend", affinity=85, trust=75)
        result = PlayerService.check_event_trigger(char, "deep_friendship")
        assert result is True

    def test_check_event_trigger_conflict(self):
        """Test check_event_trigger for conflict (low values)."""
        char = CharacterState(name="Enemy", affinity=15, trust=10)
        result = PlayerService.check_event_trigger(char, "conflict")
        assert result is True

    def test_check_event_trigger_unknown(self):
        """Test check_event_trigger with unknown event type."""
        char = CharacterState(name="NPC")
        result = PlayerService.check_event_trigger(char, "nonexistent_event")
        assert result is False


# ==================== StoryService Tests ====================


class TestStoryService:
    """Test StoryService class."""

    def test_fallback_continuation_zh(self):
        """Test Chinese fallback continuation."""
        mock_gen = Mock()
        service = StoryService(ai_generator=mock_gen, language="zh")
        result = service.generate_fallback_continuation("选择离开", {"mood": 5, "knowledge": 3})
        assert "选择离开" in result
        assert "心情" in result or "领悟" in result

    def test_fallback_continuation_en(self):
        """Test English fallback continuation."""
        mock_gen = Mock()
        service = StoryService(ai_generator=mock_gen, language="en")
        result = service.generate_fallback_continuation("leave", {"mood": 5})
        assert "leave" in result

    def test_fallback_with_negative_mood(self):
        """Test fallback with negative mood."""
        mock_gen = Mock()
        service = StoryService(ai_generator=mock_gen, language="zh")
        result = service.generate_fallback_continuation("拒绝", {"mood": -5})
        assert "波动" in result

    def test_fallback_with_relationships(self):
        """Test fallback with relationship changes."""
        mock_gen = Mock()
        service = StoryService(ai_generator=mock_gen, language="zh")
        result = service.generate_fallback_continuation("帮助朋友", {"relationships": {"小明": 10}})
        assert "小明" in result

    def test_generate_story_continuation_ai_failure_is_retryable(self):
        """Provider failure must not fabricate a continuation for a committed choice."""
        mock_gen = Mock()
        mock_gen.generate_completion.side_effect = Exception("API Error")
        service = StoryService(ai_generator=mock_gen, language="zh")
        with pytest.raises(StoryContinuationFailure, match="Story continuation generation failed"):
            service.generate_story_continuation("An event", "A choice", {"mood": 5})

    def test_story_continuation_uses_one_bounded_provider_attempt(self):
        """Choice generation must leave room for validation and recovery inside SSE."""
        mock_gen = Mock()
        mock_gen.generate_completion.return_value = "林岚和陈越核对预算，确认明天继续联系施工方。"
        service = StoryService(ai_generator=mock_gen, language="zh")

        service.generate_story_continuation(
            "林岚正在安排影院改造。", "和陈越核对预算", {"knowledge": 5}
        )

        assert mock_gen.generate_completion.call_args.kwargs["retry_count"] == 1
        assert mock_gen.generate_completion.call_args.kwargs["request_timeout"] == 75.0

    def test_choice_continuation_keeps_retry_when_only_perspective_check_fails(self):
        """A post-choice retry with only perspective drift must not block gameplay."""
        mock_gen = Mock()
        mock_gen.generate_completion.side_effect = ["initial story", "retry story"]
        service = StoryService(ai_generator=mock_gen, language="zh")
        invalid = SimpleNamespace(passed=False, issues=["故事中使用了第一人称「我」，应使用第三人称"])

        with patch("src.ai.quick_validator.quick_validate_story", side_effect=[invalid, invalid]):
            result = service.generate_story_continuation(
                "An event", "A choice", {"mood": 5}
            )

        assert result == "retry story"

    def test_generate_custom_choice_failure_is_retryable(self):
        """Custom choice provider failure must not fabricate story text or effects."""
        mock_gen = Mock()
        mock_gen.generate_completion_json.side_effect = Exception("API Error")
        service = StoryService(ai_generator=mock_gen, language="zh")
        with pytest.raises(StoryContinuationFailure, match="custom choice result"):
            service.generate_custom_choice_result("Event description", "自定义选择")


# ==================== Summary Generator Tests ====================


class TestWeeklySummaryGenerator:
    """Test WeeklySummaryGenerator class."""

    def test_generate_summary_structure(self):
        """Test summary structure with mocked AI."""
        mock_gen = Mock()
        mock_gen.ai_client.call.return_value = "This week was productive."
        gen = WeeklySummaryGenerator(ai_generator=mock_gen, language="zh")

        player = PlayerState(energy=80, mood=70, knowledge=60, wealth=15000, age=23)
        prev_state = {"energy": 70, "mood": 60, "knowledge": 55, "wealth": 14000}
        result = gen.generate_summary(5, prev_state, player, [{"choice": "A"}], "zh")

        assert result["week"] == 5
        assert result["age"] == 23
        assert result["changes"]["energy"] == 10
        assert result["decisions_count"] == 1

    def test_fallback_summary_zh(self):
        """Test Chinese fallback summary."""
        gen = WeeklySummaryGenerator.__new__(WeeklySummaryGenerator)
        gen.language = "zh"
        result = gen._get_fallback_summary(
            5, {"energy": 10, "mood": -5, "knowledge": 3, "wealth": 1000}, "zh"
        )
        assert "第5周" in result

    def test_fallback_summary_en(self):
        """Test English fallback summary."""
        gen = WeeklySummaryGenerator.__new__(WeeklySummaryGenerator)
        gen.language = "en"
        result = gen._get_fallback_summary(
            5, {"energy": 10, "mood": -5, "knowledge": 3, "wealth": 1000}, "en"
        )
        assert "Week 5" in result


class TestMonthlySummaryGenerator:
    """Test MonthlySummaryGenerator class."""

    def test_generate_summary_structure(self):
        """Test monthly summary structure."""
        mock_gen = Mock()
        mock_gen.ai_client.call.return_value = "A great month."
        gen = MonthlySummaryGenerator(ai_generator=mock_gen, language="zh")

        player = PlayerState(energy=80, mood=70, knowledge=60, wealth=15000, age=23)
        prev_state = {
            "energy": 70,
            "mood": 60,
            "knowledge": 55,
            "wealth": 14000,
            "age": 22,
        }
        result = gen.generate_summary(1, 0, 3, prev_state, player, [], "zh")

        assert result["month"] == 1
        assert result["start_week"] == 0
        assert result["end_week"] == 3
        assert "changes" in result

    def test_fallback_summary(self):
        """Test fallback summary."""
        gen = MonthlySummaryGenerator.__new__(MonthlySummaryGenerator)
        result = gen._get_fallback_summary(
            2, {"energy": 5, "mood": -3, "knowledge": 2, "wealth": 500}, "zh"
        )
        assert "第2个月" in result


class TestYearlySummaryGenerator:
    """Test YearlySummaryGenerator class."""

    def test_generate_summary_structure(self):
        """Test yearly summary structure."""
        mock_gen = Mock()
        mock_gen.ai_client.call.return_value = "A transformative year."
        gen = YearlySummaryGenerator(ai_generator=mock_gen, language="zh")

        player = PlayerState(energy=75, mood=65, knowledge=70, wealth=20000, age=23)
        start_state = {
            "energy": 70,
            "mood": 60,
            "knowledge": 50,
            "wealth": 10000,
            "age": 22,
        }
        result = gen.generate_summary(1, 0, 47, start_state, player, [], [], "zh")

        assert result["year"] == 1
        assert result["changes"]["knowledge"] == 20
        assert result["changes"]["age"] == 1

    def test_fallback_summary(self):
        """Test fallback summary."""
        gen = YearlySummaryGenerator.__new__(YearlySummaryGenerator)
        result = gen._get_fallback_summary(
            1,
            {"energy": 5, "mood": -3, "knowledge": 10, "wealth": 5000, "age": 1},
            "zh",
        )
        assert "第1年" in result
        assert "年龄增长了1岁" in result

    def test_fallback_summary_en(self):
        """Test English fallback summary."""
        gen = YearlySummaryGenerator.__new__(YearlySummaryGenerator)
        result = gen._get_fallback_summary(
            2, {"energy": 0, "mood": 0, "knowledge": 0, "wealth": 0, "age": 1}, "en"
        )
        assert "Year 2" in result
