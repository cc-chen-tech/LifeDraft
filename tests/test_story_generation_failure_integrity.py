from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from src.ai.option_generator import OptionGenerator
from src.ai.story_exceptions import StoryGenerationFailure, StoryRewriteFailure
from src.ai.story_generator import StoryGenerator
from src.ai.story_rewriter import StoryRewriter
from src.game.round.event_generator import RoundEventGenerator
from src.game.story_service import StoryService


class FailingClient:
    def call(self, **_kwargs):
        raise RuntimeError("provider unavailable")


class FailingStoryGenerator:
    ai_client = FailingClient()

    def generate_completion(self, **_kwargs):
        raise RuntimeError("provider unavailable")

    def generate_completion_json(self, **_kwargs):
        raise RuntimeError("provider unavailable")


class InvalidEffectsStoryGenerator:
    ai_client = FailingClient()

    def generate_completion_json(self, **_kwargs):
        return {"energy": "-5", "mood": 3, "knowledge": 0, "wealth": 0}


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


@pytest.mark.parametrize(
    "provider_story",
    [
        "林岚在会议室整理资料。",
        "  \n林岚在会议室整理资料。\n\n",
    ],
)
def test_rewrite_rejects_output_without_a_player_visible_change(provider_story: str) -> None:
    client = Mock()
    client.call.return_value = provider_story

    with pytest.raises(StoryRewriteFailure, match="did not change"):
        StoryRewriter(client).rewrite_story_segment(
            "林岚在会议室整理资料。",
            "林岚在会议室整理资料。",
            "把环境改得更有压迫感。",
            {},
            "",
            language="zh",
        )


def test_choice_continuation_surfaces_provider_failure_instead_of_fake_prose() -> None:
    service = StoryService(FailingStoryGenerator(), language="zh")

    with pytest.raises(RuntimeError, match="provider unavailable"):
        service.generate_story_continuation(
            event_description="林岚正在准备活动。",
            chosen_option="按计划举办活动",
            effects={"mood": 5},
        )


def test_custom_choice_effects_surface_provider_failure_instead_of_fake_effects() -> None:
    service = StoryService(FailingStoryGenerator(), language="zh")

    with pytest.raises(RuntimeError, match="provider unavailable"):
        service.generate_custom_choice_effects(
            event_description="林岚正在准备活动。",
            custom_text="邀请陈越安排放映。",
        )


def test_custom_choice_effects_reject_non_integer_provider_payload() -> None:
    service = StoryService(InvalidEffectsStoryGenerator(), language="zh")

    with pytest.raises(RuntimeError, match="invalid effect payload"):
        service.generate_custom_choice_effects(
            event_description="林岚正在准备活动。",
            custom_text="邀请陈越安排放映。",
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


@pytest.mark.parametrize(
    "generation_result",
    [RuntimeError("provider returned malformed payload"), None],
)
def test_round_event_generation_never_persists_template_fallback_after_unexpected_failure(
    generation_result: object,
) -> None:
    """Unexpected generator failures must reach the UI as errors, not fake prose."""
    state = SimpleNamespace(
        week=0,
        current_round=0,
        round_history=[],
        last_round_full_story="",
        current_event_data=None,
        character_settings={
            "era": {"era_description": "小型独立影院面临转型压力。"},
            "traits": {"traits_description": "林岚是一个务实坚韧的创业者"},
        },
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
    if isinstance(generation_result, Exception):
        ai_generator.generate_round_event.side_effect = generation_result
    else:
        ai_generator.generate_round_event.return_value = generation_result

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

    with pytest.raises(StoryGenerationFailure):
        generator.generate_round_event()

    assert state.current_event_data is None
