from unittest.mock import patch

from src.game.historical_summary_selector import HistoricalSummarySelector
from src.game.narrative_manager import NarrativeManager
from src.game.state import PlayerState


class TestHistoricalSummarySelectorFieldContracts:
    """Contract tests for deterministic summary selection behavior."""

    def test_future_week_summaries_are_skipped(self):
        state = PlayerState(
            week=10,
            pending_storylines=[{"description": "创业", "related_characters": ["张三"]}],
            world_model_data={"active_commitments": []},
            character_settings={},
            foreshadowing_seeds=[],
            weekly_summaries=[
                {"week": 10, "summary": "本周刚完成"},
                {"week": 12, "summary": "未来故事"},
            ],
            yearly_summaries=[],
        )

        weekly, yearly = HistoricalSummarySelector.select_relevant_historical_summary(state)

        assert weekly is None
        assert yearly is None

    def test_keywords_match_only_for_recent_valid_weekly_summary(self):
        state = PlayerState(
            week=20,
            pending_storylines=[
                {"description": "创业", "created_week": 1, "importance": "high", "status": "active", "related_characters": []}
            ],
            world_model_data={"active_commitments": []},
            character_settings={},
            foreshadowing_seeds=[],
            weekly_summaries=[
                {"week": 2, "summary": "主角去北京创业"},
                {"week": 18, "summary": "无关内容"},
            ],
            yearly_summaries=[],
            last_round_full_story="",
        )

        weekly, _ = HistoricalSummarySelector.select_relevant_historical_summary(state)
        assert weekly == "主角去北京创业"

    def test_no_eligible_keywords_results_none(self):
        state = PlayerState(
            week=20,
            pending_storylines=[],
            world_model_data={"active_commitments": []},
            character_settings={},
            foreshadowing_seeds=[],
            weekly_summaries=[
                {"week": 1, "summary": "完全不同的描述"},
            ],
            yearly_summaries=[
                {"end_week": 4, "summary": "也完全不同"},
            ],
            last_round_full_story="",
        )

        with patch("src.game.historical_summary_selector.random.random", return_value=1.0):
            weekly, yearly = HistoricalSummarySelector.select_relevant_historical_summary(state)
        assert weekly is None
        assert yearly is None

    def test_random_fallback_can_select_recent_weekly_summary(self):
        state = PlayerState(
            week=30,
            pending_storylines=[],
            world_model_data={"active_commitments": []},
            character_settings={},
            foreshadowing_seeds=[],
            weekly_summaries=[
                {"week": 20, "summary": "过去第20周"},
            ],
            yearly_summaries=[],
            last_round_full_story="",
        )

        with patch("src.game.historical_summary_selector.random.random", return_value=0.0):
            weekly, yearly = HistoricalSummarySelector.select_relevant_historical_summary(state)

        assert weekly == "过去第20周"
        assert yearly is None


class TestNarrativeManagerFieldContracts:
    """Contract tests for overdue and foreshadowing edge behavior."""

    def test_escalate_overdue_storylines_time_sensitive_threshold(self):
        player = PlayerState(week=10)
        player.pending_storylines = [
            {
                "description": "三天后必须完成一项约定",
                "created_week": 1,
                "importance": "high",
                "status": "active",
                "related_characters": [],
                "last_mentioned_week": 7,
            }
        ]

        escalated = NarrativeManager.escalate_overdue_storylines(player)

        assert escalated == 1
        assert player.pending_storylines[0]["overdue"] is True
        assert player.pending_storylines[0]["overdue_since_week"] == 10

    def test_escalate_overdue_storylines_non_time_sensitive_threshold(self):
        player = PlayerState(week=10)
        player.pending_storylines = [
            {
                "description": "主线线索平静发展",
                "created_week": 1,
                "importance": "high",
                "status": "active",
                "related_characters": [],
                "last_mentioned_week": 5,
            }
        ]

        escalated = NarrativeManager.escalate_overdue_storylines(player)

        assert escalated == 1
        assert player.pending_storylines[0]["overdue"] is True

    def test_escalate_overdue_storylines_skip_medium_importance(self):
        player = PlayerState(week=10)
        player.pending_storylines = [
            {
                "description": "三天后必须完成一项约定",
                "created_week": 1,
                "importance": "medium",
                "status": "active",
                "related_characters": [],
                "last_mentioned_week": 1,
            }
        ]

        escalated = NarrativeManager.escalate_overdue_storylines(player)

        assert escalated == 0
        assert "overdue" not in player.pending_storylines[0]

    def test_select_foreshadowing_seed_activates_with_metrics(self):
        player = PlayerState(week=10)
        player.pending_storylines = []
        player.foreshadowing_seeds = [
            {
                "description": "神秘的旧约记账本现身",
                "planted_week": 2,
                "maturity_weeks": 8,
                "obfuscation_level": 0,
                "related_characters": ["主角"],
                "related_storylines": [],
                "narrative_weight": "major",
                "activated": False,
                "seed_type": "mystery",
            }
        ]

        with patch("src.game.narrative_manager.random.random", return_value=0.0):
            activated = NarrativeManager.select_foreshadowing_seed(player)

        assert activated is not None
        assert activated["activated"] is True
        assert player.foreshadowing_metrics["total_activated"] == 1
        assert player.foreshadowing_metrics["avg_recovery_distance"] == 8
        assert player.foreshadowing_metrics["recovery_distances"] == [8]

    def test_select_foreshadowing_seed_none_when_not_matured(self):
        player = PlayerState(week=3)
        player.pending_storylines = []
        player.foreshadowing_seeds = [
            {
                "description": "太早的种子",
                "planted_week": 2,
                "maturity_weeks": 10,
                "obfuscation_level": 0,
                "related_characters": [],
                "related_storylines": [],
                "narrative_weight": "supporting",
                "activated": False,
                "seed_type": "mystery",
            }
        ]

        activated = NarrativeManager.select_foreshadowing_seed(player)

        assert activated is None
        assert player.foreshadowing_seeds[0]["activated"] is False
