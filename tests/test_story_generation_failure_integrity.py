from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from src.ai.option_generator import OptionGenerator
from src.ai.story_exceptions import StoryGenerationFailure, StoryRewriteFailure
from src.ai.story_generator import StoryGenerator
from src.ai.story_rewriter import StoryRewriter
from src.game.round.event_generator import RoundEventGenerator


class FailingClient:
    def call(self, **_kwargs):
        raise RuntimeError("provider unavailable")


def test_round_story_generation_surfaces_provider_failure() -> None:
    with pytest.raises(StoryGenerationFailure, match="provider unavailable"):
        StoryGenerator(FailingClient()).generate_round_event(
            player_state={"player_name": "林岚", "week": 0, "current_round": 0},
            language="zh",
            round_number=0,
            round_context="",
            character_settings={},
            option_generator=OptionGenerator(FailingClient()),
        )


def test_rewrite_surfaces_provider_failure_instead_of_returning_original_story() -> None:
    with pytest.raises(StoryRewriteFailure, match="provider unavailable"):
        StoryRewriter(FailingClient()).rewrite_story_segment(
            "原始故事",
            "原始故事",
            "改写成八个自然段",
            {},
            "",
            language="zh",
        )


def test_round_event_generation_does_not_persist_fallback_after_provider_failure() -> None:
    state = SimpleNamespace(
        week=0,
        current_round=0,
        round_history=[],
        last_round_full_story="",
        current_event_data=None,
        character_settings={},
        pending_storylines=[],
        established_facts=[],
        last_event_concluded=False,
        character_habits=[],
        foreshadowing_seeds=[],
        get_pending_scheduled_events=lambda *_args: [],
        get_round_context=lambda: "",
        to_dict=lambda: {"character_settings": {}},
        get_game_date_info=lambda: {},
    )
    ai_generator = Mock()
    ai_generator.generate_round_event.side_effect = StoryGenerationFailure("provider unavailable")
    introductions = Mock()
    introductions.check_introduction_opportunity.return_value = None
    summaries = Mock()
    summaries.select_relevant_historical_summary.return_value = ("", "")
    relationships = Mock()
    relationships.get_triggered_events.return_value = []
    generator = RoundEventGenerator(
        player_state_getter=lambda: state,
        ai_generator=ai_generator,
        language_getter=lambda: "zh",
        character_introduction_service=introductions,
        summary_selector=summaries,
        relationship_service=relationships,
    )

    with pytest.raises(StoryGenerationFailure, match="provider unavailable"):
        generator.generate_round_event()

    assert state.current_event_data is None
