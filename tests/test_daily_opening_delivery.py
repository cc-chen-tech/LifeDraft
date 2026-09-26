"""First-day formatting must not exhaust the prose budget for a playable story."""

from unittest.mock import MagicMock, patch

import pytest

from src.ai.harness.quality_level import QualityLevel
from src.ai.models import EventOption, GameEvent
from src.ai.quick_validator import QuickValidationResult
from src.ai.story_exceptions import StoryGenerationFailure
from src.ai.story_generator import StoryGenerator
from src.ai.text_quality import normalize_generated_story
from src.game.round.event_generator import RoundEventGenerator

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

    with patch(
        "src.ai.quick_validator.quick_validate_story",
        side_effect=lambda **_kwargs: QuickValidationResult(
            passed=True, issues=[], warnings=[]
        ),
    ):
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
    with patch(
        "src.ai.quick_validator.quick_validate_story",
        return_value=QuickValidationResult(passed=True, issues=[], warnings=[]),
    ):
        assert generator._existing_story_satisfies_quick_constraints(
            existing_story=STYLE_VARIANT_STORY,
            player_state=_first_day_state(),
            character_settings={"name": "林岚"},
            language="zh",
            resume_source="test",
        )


def test_failed_first_day_master_retry_accepts_style_variance_with_harness() -> None:
    state = _first_day_state()
    state["resume_view"] = {
        "phase": "failed",
        "failure": {"code": "RETRY_EXHAUSTED", "summary": "故事生成未能完成"},
    }
    client = MagicMock()
    client.call.return_value = STYLE_VARIANT_STORY
    generator = StoryGenerator(client, quality_level=QualityLevel.MASTER)
    generator._harness_enabled = True
    generator._soft_narrative_lengths = True
    generator._validation_pipeline = MagicMock()
    generator._validation_pipeline.validate.return_value = MagicMock(
        passed=True,
        score=95,
        critical_failures=[],
        high_warnings=[],
        medium_notes=[],
        low_notes=[],
    )
    generator._diagnostics = MagicMock()
    options = MagicMock()
    options.generate_options_only.return_value = GameEvent(
        event_description=STYLE_VARIANT_STORY,
        options=[EventOption(text="继续", effects={}) for _ in range(3)],
    )
    options.validate_options_consistency.return_value = []

    with patch(
        "src.ai.quick_validator.quick_validate_story",
        return_value=QuickValidationResult(passed=True, issues=[], warnings=[]),
    ):
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
    generator._validation_pipeline.validate.assert_called_once()
    options.generate_options_only.assert_called_once()


def test_first_day_missing_protagonist_still_blocks_story_delivery() -> None:
    story = (
        "她想开一间社区书店，却还凑不齐租金。她决定先把账目理清。\n\n"
        "父亲的承诺与积蓄都悬在心头，她反复盘算手中能用的筹码。\n\n"
        "清晨她来到旧街的店面，翻看租约上的期限和押金条款。"
    )

    with pytest.raises(StoryGenerationFailure):
        _generate_first_day(story)
