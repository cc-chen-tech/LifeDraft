from unittest.mock import Mock

import pytest

from config.feature_flags import reset_features, set_feature
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
    monkeypatch.setattr(
        "src.game.round.character_introduction.random.random", lambda: 1.0
    )

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
    monkeypatch.setattr(
        "src.game.round.character_introduction.random.random", lambda: 1.0
    )

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
    monkeypatch.setattr(
        "src.game.round.character_introduction.random.random", lambda: 1.0
    )

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
    monkeypatch.setattr(
        "src.game.round.character_introduction.random.random", lambda: 1.0
    )

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
    monkeypatch.setattr(
        "src.game.round.character_introduction.random.random", lambda: 1.0
    )

    generator.generate_round_event(operation_id="sse-operation-123")

    assert (
        ai_generator.generate_round_event.call_args.kwargs["operation_id"]
        == "sse-operation-123"
    )


def test_daily_generation_uses_soft_history_when_world_projection_is_stale(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = _daily_state()
    state.pending_character_introductions = []
    state.day_history = [
        {
            "day_index": 0,
            "event_description": "孙悟空已经离开花果山，抵达东海。",
            "choice": "进入龙宫",
            "postprocessing_status": "pending",
        }
    ]
    state.world_model_data = {
        "character_locations": {"孙悟空": {"location": "花果山", "region": "傲来国"}},
        "active_commitments": [{"description": "留在花果山", "parties": ["孙悟空"]}],
        "causal_chains": [
            {
                "cause": "留守花果山",
                "expected_consequence": "不能前往东海",
            }
        ],
    }
    state.established_facts = [
        {
            "subject": "孙悟空",
            "category": "location",
            "fact": "仍在花果山",
            "established_week": 0,
        }
    ]
    ai_generator = Mock()
    ai_generator.generate_round_event.return_value = GameEvent(
        event_description="孙悟空在东海岸边观察潮汐，思考如何进入龙宫。",
        options=[
            EventOption(text="潜入海中", effects={}),
            EventOption(text="寻找向导", effects={}),
        ],
    )
    generator = _round_generator(state, ai_generator)
    monkeypatch.setattr(
        "src.game.round.character_introduction.random.random", lambda: 1.0
    )

    generator.generate_round_event()

    kwargs = ai_generator.generate_round_event.call_args.kwargs
    assert kwargs["world_model"].character_locations == {}
    assert kwargs["world_model"].active_commitments == []
    assert kwargs["world_model"].causal_chains == []
    assert list(kwargs["established_facts"]) == []
    assert "孙悟空已经离开花果山，抵达东海。" in kwargs["round_context"]
    assert "进入龙宫" in kwargs["round_context"]


def test_daily_generation_uses_projection_hard_world_and_canonical_gap_tail(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    set_feature("daily_world_projection_v1", True)
    try:
        state = _daily_state()
        state.pending_character_introductions = []
        state.day_history = [
            {
                "day_index": 1,
                "event_id": "event-1",
                "revision": 2,
                "story_date": "2026-08-14",
                "event_description": "孙悟空离开东海，回到花果山。",
                "options": [
                    {"text": "留在东海", "effects": {}},
                    {"text": "进入水帘洞", "effects": {}},
                ],
                "choice_option_index": 1,
                "choice": "进入水帘洞",
                "world_projection_status": "failed_retryable",
            }
        ]
        state.world_model_data = {
            "character_locations": {"孙悟空": {"location": "东海", "region": "东海"}},
            "career_records": {
                "孙悟空": {"current_job": "旧任弼马温", "since_week": 0}
            },
            "active_commitments": [
                {"description": "继续留在东海", "parties": ["孙悟空"]}
            ],
            "causal_chains": [
                {"cause": "滞留东海", "expected_consequence": "不能回山"}
            ],
        }
        state.character_habits = [{"character": "孙悟空", "habit": "每天清晨巡海"}]
        state.world_projection_state["applied_through_day_index"] = 0
        state.world_projection_state["projected_through_day_index"] = 0
        state.world_projection_state["pending_from_day_index"] = 1
        state.world_projection_state["world"]["location_updates"] = [
            {
                "character": "孙悟空",
                "location": "花果山",
                "region": "傲来国",
                "source": {"event_id": "event-0", "revision": 1, "day_index": 0},
            }
        ]
        ai_generator = Mock()
        ai_generator.generate_round_event.return_value = GameEvent(
            event_description="孙悟空在花果山查看水帘洞里的陈设。",
            options=[
                EventOption(text="召集群猴", effects={}),
                EventOption(text="独自休息", effects={}),
            ],
        )
        generator = _round_generator(state, ai_generator)
        monkeypatch.setattr(
            "src.game.round.character_introduction.random.random", lambda: 1.0
        )

        generator.generate_round_event()

        kwargs = ai_generator.generate_round_event.call_args.kwargs
        assert kwargs["world_model"].character_locations["孙悟空"].location == "花果山"
        assert kwargs["world_model"].career_records == {}
        assert kwargs["world_model"].active_commitments == []
        assert kwargs["world_model"].causal_chains == []
        assert kwargs["character_habits"] == []
        assert "孙悟空离开东海，回到花果山。" in kwargs["round_context"]
        assert "进入水帘洞" in kwargs["round_context"]
        assert "event-1" in kwargs["round_context"]
        assert "继续留在东海" in kwargs["round_context"]
        assert "每天清晨巡海" in kwargs["round_context"]
    finally:
        reset_features()
