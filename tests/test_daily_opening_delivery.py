"""First-day formatting must not exhaust the prose budget for a playable story."""

from unittest.mock import MagicMock

import pytest

from src.ai.daily_opening import validate_daily_first_opening
from src.ai.generator import EventGenerator
from src.ai.harness.quality_level import QualityLevel
from src.ai.models import EventOption, GameEvent
from src.ai.system_prompts import STORY_NOVELIST_ZH
from src.ai.story_exceptions import StoryGenerationFailure
from src.ai.story_generator import StoryGenerator
from src.ai.text_quality import normalize_generated_story
from src.game.daily_timeline import build_daily_timeline
from src.game.round.character_introduction import CharacterIntroductionService
from src.game.round.event_generator import RoundEventGenerator
from src.game.state import PlayerState

pytestmark = [pytest.mark.unit]

STYLE_VARIANT_STORY = (
    "林岚想开一间社区书店，却还凑不齐租金。她决定先把账目理清。\n\n"
    "父亲的承诺与积蓄都悬在心头，她反复盘算手中能用的筹码。\n\n"
    "清晨她来到旧街的店面，翻看租约上的期限和押金条款。"
    "房东催她当场答复，她必须决定先争取宽限，还是放弃这间合适的店面。"
)


def _first_day_state() -> dict:
    return {
        "game_id": 1,
        "week": 0,
        "current_round": 0,
        "player_name": "林岚",
        "life_vision": "开一间社区书店",
        "timeline": {"version": 2, "day_index": 0, "day_number": 1},
    }


def _generate_first_day(story: str) -> tuple[GameEvent, MagicMock, MagicMock]:
    client = MagicMock()
    client.call.return_value = story
    generator = StoryGenerator(client, quality_level=QualityLevel.EXPERT)
    generator._harness_enabled = False
    generator._soft_narrative_lengths = True
    options = MagicMock()
    options.generate_options_only.return_value = GameEvent(
        event_description=story,
        options=[EventOption(text="继续", effects={}) for _ in range(3)],
    )
    options.validate_options_consistency.return_value = []

    event = generator.generate_round_event(
        player_state=_first_day_state(),
        character_settings={"name": "林岚"},
        language="zh",
        round_number=0,
        round_context="",
        option_generator=options,
    )
    return event, client, options


def test_chinese_punctuation_cleanup_preserves_story_paragraphs() -> None:
    story = "林岚还要筹措租金。\n\n清晨，她走进旧街的店面。"

    assert normalize_generated_story(story, language="zh") == story


def test_first_day_style_variance_keeps_playable_story_after_one_prose_call() -> None:
    assert validate_daily_first_opening(
        STYLE_VARIANT_STORY, _first_day_state(), {"name": "林岚"}, "zh"
    ) == [
        "daily_opening_not_single_sentence",
        "daily_opening_second_paragraph_not_scene",
    ]
    event, client, options = _generate_first_day(STYLE_VARIANT_STORY)

    assert event.event_description == STYLE_VARIANT_STORY
    assert client.call.call_count == 1
    options.generate_options_only.assert_called_once()


def test_first_day_style_variance_is_safe_to_resume() -> None:
    generator = RoundEventGenerator(
        lambda: None,
        MagicMock(),
        lambda: "zh",
        MagicMock(),
        MagicMock(),
        MagicMock(),
    )
    assert generator._existing_story_satisfies_quick_constraints(
        existing_story=STYLE_VARIANT_STORY,
        player_state=_first_day_state(),
        character_settings={"name": "林岚"},
        language="zh",
        resume_source="test",
    )


def test_failed_first_day_master_retry_accepts_style_variance_with_harness(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ENABLE_CONSTRAINT_HARNESS", "true")
    monkeypatch.setenv("ENABLE_SOFT_NARRATIVE_LENGTHS", "true")
    monkeypatch.setenv("ENABLE_UNIFIED_NARRATIVE_BUDGETS", "false")
    state = _first_day_state()
    state["resume_view"] = {
        "phase": "failed",
        "failure": {"code": "RETRY_EXHAUSTED", "summary": "故事生成未能完成"},
    }
    client = MagicMock()
    client.call.return_value = STYLE_VARIANT_STORY
    generator = StoryGenerator(client, quality_level=QualityLevel.MASTER)
    assert generator._harness_enabled
    assert generator._soft_narrative_lengths
    options = MagicMock()
    options.generate_options_only.return_value = GameEvent(
        event_description=STYLE_VARIANT_STORY,
        options=[EventOption(text="继续", effects={}) for _ in range(3)],
    )
    options.validate_options_consistency.return_value = []

    event = generator.generate_round_event(
        player_state=state,
        character_settings={"name": "林岚"},
        language="zh",
        round_number=0,
        round_context="",
        option_generator=options,
    )

    assert event.event_description == STYLE_VARIANT_STORY
    assert client.call.call_count == 1
    assert generator._validation_pipeline is not None
    options.generate_options_only.assert_called_once()


def test_failed_first_day_retry_commits_playable_event_with_real_validators(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ENABLE_CONSTRAINT_HARNESS", "true")
    monkeypatch.setenv("ENABLE_SOFT_NARRATIVE_LENGTHS", "true")
    monkeypatch.setenv("ENABLE_UNIFIED_NARRATIVE_BUDGETS", "false")
    state = PlayerState(
        player_name="林岚",
        life_vision="开一间社区书店",
        character_settings={
            "name": "林岚",
            "life_vision": "开一间社区书店",
            "relationships": {"key_people": []},
        },
        timeline=build_daily_timeline(start_date="2026-08-13", day_index=0),
        timeline_version=2,
        resume_view={
            "phase": "failed",
            "failure": {"code": "RETRY_EXHAUSTED", "retryable": True},
        },
    )
    ai = EventGenerator(
        api_key="test-key", use_cache=False, quality_level=QualityLevel.MASTER
    )
    prose_requests: list[str] = []

    def provider_response(**kwargs: object) -> str:
        system_prompt = str(kwargs["system_prompt"])
        if system_prompt.startswith(STORY_NOVELIST_ZH):
            prose_requests.append(system_prompt)
            return STYLE_VARIANT_STORY
        return '{"issues":[],"should_retry":false}'

    ai.ai_client.call = MagicMock(side_effect=provider_response)
    ai.option_gen.generate_options_only = MagicMock(
        return_value=GameEvent(
            event_description=STYLE_VARIANT_STORY,
            options=[EventOption(text="继续", effects={}) for _ in range(3)],
        )
    )
    ai.option_gen.validate_options_consistency = MagicMock(return_value=[])
    introductions = CharacterIntroductionService(
        player_state_getter=lambda: state, character_creator=MagicMock()
    )
    relationships = MagicMock()
    relationships.get_triggered_events.return_value = []
    committed: list[GameEvent] = []
    generator = RoundEventGenerator(
        player_state_getter=lambda: state,
        ai_generator=ai,
        language_getter=lambda: "zh",
        character_introduction_service=introductions,
        summary_selector=MagicMock(),
        relationship_service=relationships,
        event_callback=lambda event, _state: committed.append(event),
    )
    streamed: list[str] = []

    event = generator.generate_round_event(
        force_regenerate=True, stream_callback=streamed.append
    )

    assert event is not None
    assert event.event_description == STYLE_VARIANT_STORY
    assert len(event.options) == 3
    assert event.story_date == "2026-08-13"
    assert event.event_id.startswith("day-0-")
    assert state.current_event_data == event.model_dump()
    assert committed == [event]
    assert streamed == [STYLE_VARIANT_STORY]
    assert len(prose_requests) == 1
    assert ai.ai_client.call.call_count == 2  # prose plus the real consistency judge


def test_first_day_missing_protagonist_still_blocks_story_delivery() -> None:
    story = (
        "她想开一间社区书店，却还凑不齐租金。她决定先把账目理清。\n\n"
        "父亲的承诺与积蓄都悬在心头，她反复盘算手中能用的筹码。\n\n"
        "清晨她来到旧街的店面，翻看租约上的期限和押金条款。"
    )

    with pytest.raises(StoryGenerationFailure):
        _generate_first_day(story)
