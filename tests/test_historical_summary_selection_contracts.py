"""Deterministic contracts for historical-summary relevance selection."""

from config.feature_flags import reset_features, set_feature
from src.game.daily_timeline import build_daily_timeline
from src.game.historical_summary_selector import HistoricalSummarySelector
from src.game.state import PlayerState
import pytest

pytestmark = [pytest.mark.unit]



class TestHistoricalSummarySelectionContracts:
    def test_daily_relevance_uses_projection_commitments_not_legacy_world_data(self):
        set_feature("daily_world_projection_v1", True)
        try:
            state = PlayerState(
                week=30,
                timeline=build_daily_timeline(start_date="2026-08-01", day_index=2),
                timeline_version=2,
                world_model_data={
                    "active_commitments": [
                        {
                            "status": "pending",
                            "description": "继续留在旧东海",
                            "parties": ["老龙王"],
                        }
                    ]
                },
                weekly_summaries=[
                    {"week": 28, "summary": "老龙王提醒继续留在旧东海。"},
                    {"week": 29, "summary": "群猴等待孙悟空守护花果山。"},
                ],
            )
            state.world_projection_state["world"]["commitment_updates"] = [
                {
                    "description": "守护花果山",
                    "parties": ["孙悟空", "群猴"],
                    "status": "pending",
                    "source": {
                        "event_id": "event-0",
                        "revision": 1,
                        "day_index": 0,
                    },
                }
            ]

            weekly, yearly = (
                HistoricalSummarySelector.select_relevant_historical_summary(state)
            )

            assert weekly == "群猴等待孙悟空守护花果山。"
            assert yearly is None
        finally:
            reset_features()

    def test_last_story_character_mentions_select_weekly_and_yearly_context(self):
        state = PlayerState(
            week=60,
            character_settings={
                "relationships": {"key_people": [{"name": "林小鹿"}]},
                "family": {"family_members": [{"name": "李父"}]},
            },
            last_round_full_story="林小鹿陪主角回家探望李父。",
            weekly_summaries=[{"week": 56, "summary": "林小鹿探望李父。"}],
            yearly_summaries=[{"end_week": 48, "summary": "李父与林小鹿熟识。"}],
        )

        weekly, yearly = HistoricalSummarySelector.select_relevant_historical_summary(
            state
        )

        assert weekly == "林小鹿探望李父。"
        assert yearly == "李父与林小鹿熟识。"

    def test_pending_commitment_and_active_seed_contribute_keywords(self):
        state = PlayerState(
            week=30,
            pending_storylines=[],
            world_model_data={
                "active_commitments": [
                    {
                        "status": "pending",
                        "description": "提交论文",
                        "parties": ["导师"],
                    },
                    {
                        "status": "completed",
                        "description": "不应参与匹配",
                        "parties": ["路人"],
                    },
                ]
            },
            foreshadowing_seeds=[
                {"status": "active", "related_characters": ["编辑"]},
                {"status": "resolved", "related_characters": ["不应参与"]},
            ],
            weekly_summaries=[
                {"week": 28, "summary": "导师催促提交论文，编辑正在校对。"}
            ],
            yearly_summaries=[],
        )

        weekly, yearly = HistoricalSummarySelector.select_relevant_historical_summary(
            state
        )

        assert weekly == "导师催促提交论文，编辑正在校对。"
        assert yearly is None

    def test_relevance_scoring_prefers_nearer_summary_when_keyword_hits_are_weaker(
        self,
    ):
        state = PlayerState(
            week=20,
            pending_storylines=[
                {"description": "创业", "related_characters": ["张三"]}
            ],
            weekly_summaries=[
                {"week": 1, "summary": "张三支持主角创业。"},
                {"week": 19, "summary": "张三出现。"},
            ],
            yearly_summaries=[],
        )

        weekly, yearly = HistoricalSummarySelector.select_relevant_historical_summary(
            state
        )

        assert weekly == "张三出现。"
        assert yearly is None

    def test_current_and_future_matching_summaries_are_not_selected(self):
        state = PlayerState(
            week=10,
            pending_storylines=[
                {"description": "创业", "related_characters": ["张三"]}
            ],
            weekly_summaries=[
                {"week": 10, "summary": "张三开始创业。"},
                {"week": 11, "summary": "张三未来创业。"},
            ],
            yearly_summaries=[
                {"end_week": 10, "summary": "张三今年创业。"},
                {"end_week": 11, "summary": "张三明年创业。"},
            ],
        )

        weekly, yearly = HistoricalSummarySelector.select_relevant_historical_summary(
            state
        )

        assert weekly is None
        assert yearly is None
