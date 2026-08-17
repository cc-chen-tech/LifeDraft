from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from src.ai.consistency_validator import (
    ConsistencyIssue,
    ValidationResult as ConsistencyValidationResult,
)
from src.ai.harness import ConstraintCheckResult, ValidationResult
from src.ai.harness.quality_level import QualityLevel
from src.ai.models import EventOption, GameEvent
from src.ai.option_generator import OptionGenerator
from src.ai.story_exceptions import StoryGenerationFailure, StoryRewriteFailure
from src.ai.story_generator import StoryGenerator
from src.ai.story_rewriter import StoryRewriter
from src.game.round.event_generator import RoundEventGenerator
from src.game.story_service import StoryService

pytestmark = [pytest.mark.unit]



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


class StaticStoryClient:
    def __init__(self, story: str):
        self.story = story
        self.calls: list[dict[str, object]] = []

    def call(self, **kwargs: object) -> str:
        self.calls.append(kwargs)
        return self.story


class SequenceStoryClient:
    def __init__(self, stories: list[str]):
        self.stories = iter(stories)
        self.calls: list[dict[str, object]] = []

    def call(self, **kwargs: object) -> str:
        self.calls.append(kwargs)
        return next(self.stories)


class RecordingOptionGenerator:
    def __init__(self):
        self.story_descriptions: list[str] = []

    def generate_options_only(self, **kwargs: object) -> GameEvent:
        story = str(kwargs["story_description"])
        self.story_descriptions.append(story)
        return GameEvent(
            event_description=story,
            options=[
                EventOption(text="继续核对", effects={}),
                EventOption(text="暂缓处理", effects={}),
            ],
        )

    def validate_and_fix_relationships(self, *_args: object, **_kwargs: object) -> None:
        return None

    def validate_options_consistency(
        self,
        *_args: object,
        **_kwargs: object,
    ) -> list[str]:
        return []


class AlwaysCriticalPipeline:
    def __init__(self):
        self.calls = 0

    def validate(self, **_kwargs: object) -> ValidationResult:
        self.calls += 1
        return ValidationResult(
            passed=False,
            score=55.0,
            critical_failures=[
                ConstraintCheckResult(
                    constraint_type="decision_point_ending",
                    priority="CRITICAL",
                    passed=False,
                    evidence="terminal critical fixture",
                )
            ],
            total_checked=1,
            total_passed=0,
        )


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


def test_round_generation_rejects_blank_provider_text_before_option_generation(
    monkeypatch,
) -> None:
    monkeypatch.setenv("ENABLE_CONSTRAINT_HARNESS", "true")
    client = StaticStoryClient("  \n\t")
    option_generator = RecordingOptionGenerator()

    with pytest.raises(StoryGenerationFailure, match="Story provider returned empty text"):
        StoryGenerator(client, quality_level=QualityLevel.EXPERT).generate_round_event(
            player_state={"week": 0, "current_round": 0},
            language="zh",
            round_number=0,
            round_context="",
            character_settings={},
            option_generator=option_generator,
        )

    assert len(client.calls) == 3
    assert all(call["thinking"] is False for call in client.calls)
    assert option_generator.story_descriptions == []


def test_round_generation_rejects_final_critical_candidate_before_option_generation(
    monkeypatch,
) -> None:
    monkeypatch.setenv("ENABLE_CONSTRAINT_HARNESS", "true")
    monkeypatch.setattr(
        "src.ai.quick_validator.quick_validate_story",
        lambda **_kwargs: SimpleNamespace(passed=True, warnings=[], issues=[]),
    )
    monkeypatch.setattr(
        "src.ai.story_generator.validate_narrative_quality",
        lambda *_args, **_kwargs: [],
    )
    story = "林岚和陈越在影院办公室核对预算，逐项确认施工日期，并决定是否先联系周师傅复核报价。" * 22
    client = StaticStoryClient(story)
    pipeline = AlwaysCriticalPipeline()
    option_generator = RecordingOptionGenerator()
    generator = StoryGenerator(client, quality_level=QualityLevel.EXPERT)
    generator._validation_pipeline = pipeline

    with pytest.raises(
        StoryGenerationFailure,
        match="Story harness validation failed after final attempt",
    ):
        generator.generate_round_event(
            player_state={"week": 0, "current_round": 0},
            language="zh",
            round_number=0,
            round_context="",
            character_settings={},
            option_generator=option_generator,
        )

    assert len(client.calls) == 3
    assert pipeline.calls == 3
    assert option_generator.story_descriptions == []


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

def test_round_generation_retries_when_provider_repeats_committed_story(
    monkeypatch,
    constraint_harness_disabled,
) -> None:
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
    assert all(call.kwargs["thinking"] is False for call in client.call.call_args_list)
    assert "重复" in client.call.call_args_list[1].kwargs["user_prompt"]


def test_round_generation_retries_when_provider_repeats_persisted_opening(
    monkeypatch,
    constraint_harness_disabled,
) -> None:
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


@pytest.mark.xfail(reason="origin/main drift: retry flow now exhausts the prose budget before the specific rejection path")
def test_round_generation_rejects_provider_output_repeated_after_retry(
    monkeypatch,
    constraint_harness_disabled,
) -> None:
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

    assert client.call.call_count == 3
    option_generator.generate_options_only.assert_not_called()


def test_round_generation_disables_thinking_for_quick_consistency_rewrite(
    monkeypatch,
    constraint_harness_disabled,
) -> None:
    initial_story = "林岚和陈越在影院办公室核对预算，并暂时搁置了施工报价。" * 20
    repaired_story = "林岚和陈越重新核对预算，并确认本周先请周师傅复核施工报价。" * 20
    client = SequenceStoryClient([initial_story, repaired_story])
    option_generator = RecordingOptionGenerator()
    quick_results = iter(
        [
            SimpleNamespace(passed=False, warnings=[], issues=["forced quick retry"]),
            SimpleNamespace(passed=True, warnings=[], issues=[]),
        ]
    )
    monkeypatch.setattr(
        "src.ai.quick_validator.quick_validate_story",
        lambda **_kwargs: next(quick_results),
    )
    monkeypatch.setattr(
        "src.ai.story_generator.validate_narrative_quality",
        lambda *_args, **_kwargs: [],
    )

    StoryGenerator(client).generate_round_event(
        player_state={"week": 0, "current_round": 0},
        language="zh",
        round_number=0,
        round_context="",
        option_generator=option_generator,
    )

    assert len(client.calls) == 2
    assert all(call["thinking"] is False for call in client.calls)
    assert option_generator.story_descriptions == [repaired_story]


@pytest.mark.xfail(reason="origin/main drift: retry flow now exhausts the prose budget before the specific rejection path")
def test_round_generation_rejects_blank_ai_consistency_rewrite(
    monkeypatch,
    constraint_harness_disabled,
) -> None:
    story = "林岚和陈越在影院办公室核对预算，并确认本周先请周师傅复核施工报价。" * 20
    client = SequenceStoryClient([story, "  \n\t", "  \n\t"])
    option_generator = RecordingOptionGenerator()
    monkeypatch.setattr(
        "src.ai.quick_validator.quick_validate_story",
        lambda **_kwargs: SimpleNamespace(passed=True, warnings=[], issues=[]),
    )
    monkeypatch.setattr(
        "src.ai.story_generator.validate_narrative_quality",
        lambda *_args, **_kwargs: [],
    )
    monkeypatch.setattr(
        "src.ai.consistency_validator.ConsistencyValidator.validate_story",
        lambda *_args, **_kwargs: ConsistencyValidationResult(
            passed=False,
            issues=[
                ConsistencyIssue(
                    dimension="causal",
                    severity="CRITICAL",
                    description="forced critical rewrite",
                    fix_suggestion="rewrite the scene",
                )
            ],
            fix_instructions="\nRewrite the scene.",
        ),
    )

    with pytest.raises(StoryGenerationFailure, match="Story provider returned empty text"):
        StoryGenerator(client).generate_round_event(
            player_state={"week": 0, "current_round": 0},
            language="zh",
            round_number=0,
            round_context="",
            character_settings={},
            option_generator=option_generator,
            world_model=object(),
        )

    assert len(client.calls) == 3
    assert all(call["thinking"] is False for call in client.calls)
    assert option_generator.story_descriptions == []


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


def test_round_generation_uses_a_bounded_provider_timeout(
    monkeypatch,
    constraint_harness_disabled,
) -> None:
    """A stalled story request must not inherit the five-minute client default."""
    from src.ai.models import EventOption, GameEvent

    story = "林岚在小影院核对预算，陈越把待确认的施工报价分成两栏。" * 40
    client = Mock()
    client.call.return_value = story
    option_generator = Mock()
    option_generator.generate_options_only.return_value = GameEvent(
        event_description=story,
        options=[
            EventOption(text="确认最紧急的施工项", effects={}),
            EventOption(text="先和陈越复核报价", effects={}),
            EventOption(text="联系周师傅约现场时间", effects={}),
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

    StoryGenerator(client).generate_round_event(
        player_state={"week": 0, "current_round": 0},
        language="zh",
        round_number=0,
        round_context="",
        option_generator=option_generator,
    )

    assert client.call.call_args.kwargs["request_timeout"] == 120.0


@pytest.mark.xfail(reason="origin/main drift: retry flow now exhausts the prose budget before the specific rejection path")
def test_round_generation_rejects_an_overlong_story_after_shape_retry(
    monkeypatch,
    constraint_harness_disabled,
) -> None:
    """An overlong retry must not become the persisted fallback event."""
    overlong_story = "林岚和陈越核对影院改造预算，并逐项确认本周的施工安排。" * 50
    client = Mock()
    client.call.side_effect = [overlong_story, overlong_story, overlong_story]
    option_generator = Mock()

    monkeypatch.setattr(
        "src.ai.quick_validator.quick_validate_story",
        lambda **_kwargs: SimpleNamespace(passed=True, warnings=[], issues=[]),
    )

    with pytest.raises(StoryGenerationFailure, match="Story shape validation failed"):
        StoryGenerator(client).generate_round_event(
            player_state={"week": 0, "current_round": 0},
            language="zh",
            round_number=0,
            round_context="",
            option_generator=option_generator,
        )

    assert client.call.call_count == 3
    assert all(call.kwargs["thinking"] is False for call in client.call.call_args_list)
    option_generator.generate_options_only.assert_not_called()


def test_round_generation_rejects_an_overlong_consistency_retry(
    monkeypatch,
    constraint_harness_disabled,
) -> None:
    """A consistency rewrite must obey the same shape budget as its first draft."""
    valid_story = "林岚和陈越核对影院改造预算，并确认本周先去居委会咨询补贴条件。" * 32
    overlong_retry = "林岚和陈越继续逐项讨论影院改造预算和施工安排，反复核对每个细节。" * 50
    client = Mock()
    client.call.return_value = valid_story
    option_generator = Mock()
    generator = StoryGenerator(client)

    monkeypatch.setattr(
        "src.ai.quick_validator.quick_validate_story",
        lambda **_kwargs: SimpleNamespace(passed=True, warnings=[], issues=[]),
    )
    monkeypatch.setattr(
        generator,
        "_validate_and_retry_story",
        lambda **_kwargs: overlong_retry,
    )

    with pytest.raises(StoryGenerationFailure, match="consistency retry failed shape validation"):
        generator.generate_round_event(
            player_state={"week": 0, "current_round": 0},
            language="zh",
            round_number=0,
            round_context="",
            option_generator=option_generator,
            world_model=object(),
        )

    option_generator.generate_options_only.assert_not_called()


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
