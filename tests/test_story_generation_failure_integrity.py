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

def test_round_generation_retries_when_provider_repeats_committed_story(monkeypatch) -> None:
    from src.ai.models import EventOption, GameEvent

    repeated_story = "林岚在小影院核对测量费与预算表，陈越记录每一笔待确认支出。" * 32
    distinct_story = "林岚和陈越约周师傅在影院门口确认施工时间，并把预算分成紧急与可延后两栏。" * 28
    client = Mock()
    client.call.side_effect = [repeated_story, distinct_story]
    option_generator = Mock()
    option_generator.generate_options_only.return_value = GameEvent(
        event_description=distinct_story,
        options=[
            EventOption(text="确认施工时间", effects={}),
            EventOption(text="延后施工并复核预算", effects={}),
        ],
    )

    monkeypatch.setattr(
        "src.ai.quick_validator.quick_validate_story",
        lambda **_kwargs: SimpleNamespace(passed=True, warnings=[], issues=[]),
    )
    monkeypatch.setattr(
        "src.ai.story_generator.validate_narrative_quality",
        lambda *_args, **_kwargs: [],
    )

    event = StoryGenerator(client).generate_round_event(
        player_state={"week": 1, "decision_history": [{"event": repeated_story}]},
        language="zh",
        round_number=1,
        round_context="",
        option_generator=option_generator,
        last_round_full_story=repeated_story,
    )

    assert event.event_description == distinct_story
    assert client.call.call_count == 2
    assert "重复" in client.call.call_args_list[1].kwargs["user_prompt"]


def test_round_generation_retries_when_provider_repeats_persisted_opening(monkeypatch) -> None:
    from src.ai.models import EventOption, GameEvent

    opening_story = "林澈在上海的咖啡馆与王天成讨论独立创作的第一步，并决定开始用户调研。" * 18
    distinct_story = "午后，林澈整理访谈提纲，决定先联系三位目标用户确认访谈时间。" * 24
    client = Mock()
    client.call.side_effect = [opening_story, distinct_story]
    option_generator = Mock()
    option_generator.generate_options_only.return_value = GameEvent(
        event_description=distinct_story,
        options=[
            EventOption(text="约访第一位用户", effects={}),
            EventOption(text="完善访谈提纲", effects={}),
        ],
    )

    monkeypatch.setattr(
        "src.ai.quick_validator.quick_validate_story",
        lambda **_kwargs: SimpleNamespace(passed=True, warnings=[], issues=[]),
    )
    monkeypatch.setattr(
        "src.ai.story_generator.validate_narrative_quality",
        lambda *_args, **_kwargs: [],
    )

    event = StoryGenerator(client).generate_round_event(
        player_state={"week": 0, "current_round": 0},
        language="zh",
        round_number=0,
        round_context="",
        character_settings={"opening_story": opening_story},
        option_generator=option_generator,
    )

    assert event.event_description == distinct_story
    assert client.call.call_count == 2
    assert "重复" in client.call.call_args_list[1].kwargs["user_prompt"]


def test_first_round_receives_persisted_opening_as_non_repeating_context() -> None:
    from src.ai.models import EventOption, GameEvent

    opening_story = "林澈在上海的咖啡馆与王天成讨论独立创作的第一步。"
    state = SimpleNamespace(
        week=0,
        current_round=0,
        round_history=[],
        last_round_full_story="",
        current_event_data=None,
        character_settings={"opening_story": opening_story},
        pending_storylines=[],
        established_facts=[],
        last_event_concluded=True,
        character_habits=[],
        foreshadowing_seeds=[],
        get_pending_scheduled_events=lambda *_args: [],
        get_round_context=lambda: "",
        to_dict=lambda: {"character_settings": {"opening_story": opening_story}},
        get_game_date_info=lambda: {},
    )
    ai_generator = Mock()
    ai_generator.generate_round_event.return_value = GameEvent(
        event_description="下午，林澈开始整理访谈提纲。",
        options=[
            EventOption(text="联系访谈对象", effects={}),
            EventOption(text="完善访谈提纲", effects={}),
        ],
    )
    introductions = Mock()
    introductions.maybe_generate_new_character.return_value = None
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

    generator.generate_round_event()

    context = ai_generator.generate_round_event.call_args.kwargs["round_context"]
    assert opening_story in context
    assert "不得复述" in context


def test_round_generation_rejects_provider_output_repeated_after_retry(monkeypatch) -> None:
    repeated_story = "林岚在小影院核对测量费与预算表，陈越记录每一笔待确认支出。" * 32
    client = Mock()
    client.call.side_effect = [repeated_story, repeated_story]
    option_generator = Mock()

    monkeypatch.setattr(
        "src.ai.quick_validator.quick_validate_story",
        lambda **_kwargs: SimpleNamespace(passed=True, warnings=[], issues=[]),
    )
    monkeypatch.setattr(
        "src.ai.story_generator.validate_narrative_quality",
        lambda *_args, **_kwargs: [],
    )

    with pytest.raises(StoryGenerationFailure, match="repeats committed story"):
        StoryGenerator(client).generate_round_event(
            player_state={"week": 1, "decision_history": [{"event": repeated_story}]},
            language="zh",
            round_number=1,
            round_context="",
            option_generator=option_generator,
            last_round_full_story=repeated_story,
        )

    assert client.call.call_count == 2
    option_generator.generate_options_only.assert_not_called()

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
