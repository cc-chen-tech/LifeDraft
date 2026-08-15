from typing import Optional

import pytest

from src.ai.models import EventOption, GameEvent
from src.game.daily_timeline import build_daily_timeline
from src.game.game_loop import GameLoop
from src.game.round.daily_choice_processor import DailyChoiceProcessor
from src.game.state import PlayerState


def _state(day_index: int = 0) -> PlayerState:
    return PlayerState(
        energy=50,
        mood=50,
        knowledge=50,
        age=20,
        timeline=build_daily_timeline(start_date="2026-08-13", day_index=day_index),
        timeline_version=2,
        next_age_day=365,
    )


def _event(revision: int = 1) -> GameEvent:
    return GameEvent(
        event_id="day-0-event",
        revision=revision,
        story_date="2026-08-13",
        event_description="这是当天完整故事，结尾留下了唯一的抉择。",
        options=[
            EventOption(
                text="接受邀请",
                effects={"energy": -5, "mood": 4},
                transition_text="话音落下，未散的余韵正悄然走向明日。",
            ),
            EventOption(text="礼貌拒绝", effects={"knowledge": 2}),
        ],
    )


def _processor(state: PlayerState, event: Optional[GameEvent]):
    holder = {"event": event}
    processor = DailyChoiceProcessor(
        player_state_getter=lambda: state,
        current_event_getter=lambda: holder["event"],
        current_event_setter=lambda value: holder.__setitem__("event", value),
    )
    return processor, holder


def test_daily_choice_settles_without_story_model_and_advances_one_day() -> None:
    state = _state()
    processor, holder = _processor(state, _event())

    result = processor.make_choice(event_id="day-0-event", revision=1, option_index=0)

    assert result["story_continuation"] == ""
    assert result["need_weekly_summary"] is False
    assert result["effects_applied"] == {"energy": -5, "mood": 4}
    assert result["next_timeline"]["current_date"] == "2026-08-14"
    assert state.energy == 45
    assert state.mood == 54
    assert len(state.day_history) == 1
    assert state.day_history[0]["options"][0]["text"] == "接受邀请"
    assert result["transition_text"] == "话音落下，未散的余韵正悄然走向明日。"
    assert state.day_history[0]["transition_text"] == result["transition_text"]
    assert (
        state.day_history[0]["choice_result"]["transition_text"]
        == result["transition_text"]
    )
    assert state.day_history[0]["postprocessing_status"] == "pending"
    assert state.current_event_data is None
    assert holder["event"] is None
    assert state.continuity_ledger["timeline"][-1]["event_id"] == "day-0-event"
    assert (
        state.continuity_ledger["timeline"][-1]["date_info"]["story_date"]
        == "2026-08-13"
    )


def test_daily_choice_rejects_stale_revision_before_mutation() -> None:
    state = _state()
    processor, _ = _processor(state, _event(revision=2))

    with pytest.raises(ValueError, match="stale_event_revision"):
        processor.make_choice(event_id="day-0-event", revision=1, option_index=0)

    assert state.timeline["day_index"] == 0
    assert state.energy == 50
    assert state.day_history == []


@pytest.mark.parametrize(("event_id", "revision"), [("", 1), ("day-0-event", 0)])
def test_daily_choice_requires_explicit_event_version(
    event_id: str, revision: int
) -> None:
    state = _state()
    processor, _ = _processor(state, _event())

    with pytest.raises(ValueError, match="missing_event_version"):
        processor.make_choice(event_id=event_id, revision=revision, option_index=0)

    assert state.day_history == []


def test_duplicate_daily_choice_is_idempotent() -> None:
    state = _state()
    processor, _ = _processor(state, _event())

    first = processor.make_choice(event_id="day-0-event", revision=1, option_index=0)
    second = processor.make_choice(event_id="day-0-event", revision=1, option_index=0)

    assert second == first
    assert state.timeline["day_index"] == 1
    assert state.energy == 45
    assert len(state.day_history) == 1
    assert second["transition_text"] == "话音落下，未散的余韵正悄然走向明日。"


def test_missing_transition_uses_stable_fallback_and_persists_it() -> None:
    state = _state()
    event = _event()
    event.options[1].transition_text = None
    processor, _ = _processor(state, event)

    first = processor.make_choice(event_id="day-0-event", revision=1, option_index=1)
    second = processor.make_choice(event_id="day-0-event", revision=1, option_index=1)

    assert first["transition_text"]
    assert second["transition_text"] == first["transition_text"]
    assert state.day_history[0]["transition_text"] == first["transition_text"]


def test_legacy_duplicate_choice_without_transition_gets_deterministic_fallback() -> (
    None
):
    state = _state(day_index=1)
    state.day_history = [
        {
            "event_id": "legacy-day-0",
            "revision": 1,
            "day_index": 0,
            "story_date": "2026-08-13",
            "event_description": "旧存档故事",
            "options": [
                {"text": "接受邀请", "effects": {"mood": 2}},
                {"text": "礼貌拒绝", "effects": {}},
            ],
            "choice_option_index": 0,
            "choice": "接受邀请",
            "choice_result": {
                "story_continuation": "",
                "summary": "",
                "next_timeline": state.timeline,
            },
        }
    ]
    processor, _ = _processor(state, None)

    first = processor.make_choice(event_id="legacy-day-0", revision=1, option_index=0)
    second = processor.make_choice(event_id="legacy-day-0", revision=1, option_index=0)

    assert first["transition_text"]
    assert second["transition_text"] == first["transition_text"]


def test_choice_failure_does_not_partially_commit() -> None:
    state = _state()
    bad_event = _event()
    bad_event.options[0].effects["relationships"] = {"朋友": "invalid"}
    processor, holder = _processor(state, bad_event)

    with pytest.raises((TypeError, ValueError)):
        processor.make_choice(event_id="day-0-event", revision=1, option_index=0)

    assert state.timeline["day_index"] == 0
    assert state.energy == 50
    assert state.day_history == []
    assert holder["event"] is bad_event


def test_daily_choice_persistence_failure_does_not_commit_live_state() -> None:
    state = _state()
    event = _event()
    processor, holder = _processor(state, event)
    persisted_candidates = []

    with pytest.raises(RuntimeError, match="daily_choice_persistence_failed"):
        processor.make_choice(
            event_id="day-0-event",
            revision=1,
            option_index=0,
            persist_callback=lambda candidate: persisted_candidates.append(candidate)
            or False,
        )

    assert len(persisted_candidates) == 1
    assert persisted_candidates[0].timeline["day_index"] == 1
    assert state.timeline["day_index"] == 0
    assert state.energy == 50
    assert state.day_history == []
    assert holder["event"] is event


def test_seventh_completed_day_applies_deterministic_decay_without_summary() -> None:
    state = _state(day_index=6)
    event = _event()
    event.event_id = "day-6-event"
    event.story_date = "2026-08-19"
    processor, _ = _processor(state, event)

    result = processor.make_choice(event_id="day-6-event", revision=1, option_index=1)

    assert result["need_weekly_summary"] is False
    assert result["weekly_decay_applied"] is True
    assert state.mood == 48


@pytest.mark.parametrize(
    ("day_index", "expected_kind"), [(27, "long_term"), (364, "yearly")]
)
def test_summary_milestones_are_queued_without_blocking_choice(
    day_index: int, expected_kind: str
) -> None:
    state = _state(day_index=day_index)
    event = _event()
    event.event_id = f"day-{day_index}-event"
    event.story_date = state.timeline["current_date"]
    processor, _ = _processor(state, event)

    result = processor.make_choice(event_id=event.event_id, revision=1, option_index=1)

    assert result["summary_milestones"] == [expected_kind]
    assert state.day_history[-1]["summary_milestones"] == [expected_kind]


def test_daily_background_worker_generates_long_term_summary() -> None:
    class SummaryGenerator:
        def generate_four_week_summary(self, *args, **kwargs):
            return "28 天长期摘要"

    loop = object.__new__(GameLoop)
    loop.player_state = _state(day_index=28)
    loop.player_state.day_history = [
        {
            "event_id": "day-27",
            "day_index": 27,
            "story_date": "2026-09-09",
            "event_description": "第 28 天故事",
            "choice": "继续",
            "effects_applied": {},
            "summary_milestones": ["long_term"],
        }
    ]
    loop.ai_generator = SummaryGenerator()
    loop.language = "zh"

    loop._generate_daily_milestone_summaries(loop.player_state.day_history[-1])

    assert loop.player_state.four_week_summaries[-1]["summary"] == "28 天长期摘要"
    assert loop.player_state.four_week_summaries[-1]["timeline_version"] == 2


def test_daily_background_worker_applies_updates_entities_and_persists() -> None:
    class StoryService:
        def compress_narrative(self, *args, **kwargs):
            return {
                "summary": "雨夜书铺的摘要",
                "storyline_updates": [
                    {"action": "new", "description": "追查旧钥匙", "importance": "high"}
                ],
            }

        def extract_world_updates(self, *args, **kwargs):
            return {
                "fact_updates": [
                    {"action": "new", "subject": "旧钥匙", "fact": "来自河边仓库"}
                ],
                "foreshadowing_seeds": [],
                "habit_updates": [],
                "location_updates": [],
                "career_updates": [],
                "commitment_updates": [],
                "causal_updates": [],
            }

    loop = object.__new__(GameLoop)
    loop.player_state = _state(day_index=1)
    loop.player_state.day_history = [
        {
            "event_id": "day-0-event",
            "revision": 1,
            "day_index": 0,
            "story_date": "2026-08-13",
            "event_description": "林舟在雨夜书铺发现旧钥匙。",
            "choice": "追查钥匙",
            "postprocessing_status": "pending",
            "summary_milestones": [],
        }
    ]
    loop.story_service = StoryService()
    loop._recognize_daily_entities = lambda _record: {
        "items": [{"name": "旧钥匙"}],
        "characters": [],
        "landmarks": [{"name": "河边仓库"}],
    }
    persisted = []
    loop._daily_postprocess_persist_callback = lambda: persisted.append(True) or True

    loop._process_daily_record("day-0-event")

    record = loop.player_state.day_history[0]
    assert record["postprocessing_status"] == "complete"
    assert record["summary"] == "雨夜书铺的摘要"
    assert record["postprocessing"]["entities"]["items"][0]["name"] == "旧钥匙"
    assert loop.player_state.established_facts[-1]["subject"] == "旧钥匙"
    assert loop.player_state.pending_storylines[-1]["description"] == "追查旧钥匙"
    assert persisted == [True]
