from unittest.mock import Mock

import pytest

from src.ai.models import EventOption, GameEvent
from src.ai.story_exceptions import StoryGenerationFailure
from src.game.daily_timeline import build_daily_timeline
from src.game.round.character_introduction import CharacterIntroductionService
from src.game.round.event_generator import RoundEventGenerator
from src.game.state import PlayerState


def _pending_character(name: str = "玄奘") -> dict:
    return {
        "character_data": {"name": name, "role": "导师", "affinity": 60},
        "created_week": 0,
        "introduction_context": "random",
        "priority": 9,
        "attempts": 0,
    }


def _daily_state() -> PlayerState:
    return PlayerState(
        player_name="孙悟空",
        character_settings={"relationships": {"key_people": []}},
        timeline=build_daily_timeline(start_date="2026-08-13", day_index=1),
        timeline_version=2,
        pending_character_introductions=[_pending_character()],
    )


def _round_generator(state: PlayerState, ai_generator: Mock) -> RoundEventGenerator:
    introductions = CharacterIntroductionService(
        player_state_getter=lambda: state,
        character_creator=Mock(),
    )
    relationships = Mock()
    relationships.get_triggered_events.return_value = []
    return RoundEventGenerator(
        player_state_getter=lambda: state,
        ai_generator=ai_generator,
        language_getter=lambda: "zh",
        character_introduction_service=introductions,
        summary_selector=Mock(),
        relationship_service=relationships,
    )


def test_failed_daily_generation_discards_character_introduction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Removing the transaction would leak the introduced person into saved state."""
    state = _daily_state()
    before = state.model_dump()
    ai_generator = Mock()
    ai_generator.generate_round_event.side_effect = StoryGenerationFailure(
        "provider unavailable"
    )
    generator = _round_generator(state, ai_generator)
    monkeypatch.setattr("src.game.round.character_introduction.random.random", lambda: 1.0)

    with pytest.raises(StoryGenerationFailure, match="provider unavailable"):
        generator.generate_round_event()

    assert state.model_dump() == before


def test_daily_generation_rejects_an_introduced_character_missing_from_final_story(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A staged person must not be committed unless the accepted prose introduces them."""
    state = _daily_state()
    before = state.model_dump()
    ai_generator = Mock()
    ai_generator.generate_round_event.return_value = GameEvent(
        event_description="孙悟空独自在山路上整理行囊，没有遇到其他人。",
        options=[
            EventOption(text="继续赶路", effects={}),
            EventOption(text="原地休息", effects={}),
        ],
    )
    generator = _round_generator(state, ai_generator)
    monkeypatch.setattr("src.game.round.character_introduction.random.random", lambda: 1.0)

    with pytest.raises(StoryGenerationFailure, match="introduced character"):
        generator.generate_round_event()

    assert state.model_dump() == before


def test_successful_daily_generation_commits_staged_character_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Skipping commit would lose the one character that appears in accepted prose."""
    state = _daily_state()
    ai_generator = Mock()
    ai_generator.generate_round_event.return_value = GameEvent(
        event_description="玄奘在山门前叫住孙悟空，两人约定次日一同赶路。",
        options=[
            EventOption(text="答应同行", effects={}),
            EventOption(text="先问清路线", effects={}),
        ],
    )
    generator = _round_generator(state, ai_generator)
    monkeypatch.setattr("src.game.round.character_introduction.random.random", lambda: 1.0)

    event = generator.generate_round_event()

    people = state.character_settings["relationships"]["key_people"]
    assert [person["name"] for person in people] == ["玄奘"]
    assert state.pending_character_introductions == []
    assert state.relationships["玄奘"] == 60
    assert state.current_event_data == event.model_dump()


def test_commit_callback_failure_restores_live_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = _daily_state()
    before = state.model_dump()
    ai_generator = Mock()
    ai_generator.generate_round_event.return_value = GameEvent(
        event_description="玄奘在山门前叫住孙悟空，两人约定次日一同赶路。",
        options=[
            EventOption(text="答应同行", effects={}),
            EventOption(text="先问清路线", effects={}),
        ],
    )
    generator = _round_generator(state, ai_generator)
    generator.event_callback = Mock(side_effect=RuntimeError("persist failed"))
    monkeypatch.setattr("src.game.round.character_introduction.random.random", lambda: 1.0)

    with pytest.raises(RuntimeError, match="persist failed"):
        generator.generate_round_event()

    assert state.model_dump() == before


def test_sse_operation_id_reaches_story_candidate_generation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = _daily_state()
    ai_generator = Mock()
    ai_generator.generate_round_event.return_value = GameEvent(
        event_description="玄奘在山门前叫住孙悟空，两人约定次日一同赶路。",
        options=[
            EventOption(text="答应同行", effects={}),
            EventOption(text="先问清路线", effects={}),
        ],
    )
    generator = _round_generator(state, ai_generator)
    monkeypatch.setattr("src.game.round.character_introduction.random.random", lambda: 1.0)

    generator.generate_round_event(operation_id="sse-operation-123")

    assert (
        ai_generator.generate_round_event.call_args.kwargs["operation_id"]
        == "sse-operation-123"
    )
