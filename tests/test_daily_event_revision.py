import pytest

from src.ai.models import EventOption, GameEvent
from src.game.daily_event_revision import (
    regenerate_daily_event_atomically,
    rewrite_daily_event_atomically,
)
from src.game.daily_timeline import build_daily_timeline
from src.game.state import PlayerState
from src.game.round.event_generator import apply_daily_event_metadata


def _event(text: str = "原故事", revision: int = 1) -> GameEvent:
    return GameEvent(
        event_id="stable-event",
        revision=revision,
        story_date="2026-08-13",
        event_description=text,
        options=[
            EventOption(text="旧选项一", effects={"mood": 1}),
            EventOption(text="旧选项二", effects={"energy": -1}),
        ],
    )


class FakeLoop:
    def __init__(self) -> None:
        self.current_event = _event()
        self.player_state = PlayerState(
            timeline=build_daily_timeline(start_date="2026-08-13", day_index=0),
            timeline_version=2,
            current_event_data=self.current_event.model_dump(),
        )
        self.fail_regenerate = False
        self.fail_options = False
        self.ai_generator = self

    def generate_round_event(self, **_kwargs):
        self.player_state.pending_storylines.append({"description": "candidate side effect"})
        if self.fail_regenerate:
            raise RuntimeError("generation failed")
        event = _event("重新生成的故事")
        event.options[0].text = "新选项一"
        self.current_event = event
        self.player_state.current_event_data = event.model_dump()
        return event

    def rewrite_story_segment(self, **_kwargs):
        return "改写后的完整故事"

    def generate_options_only(self, **_kwargs):
        if self.fail_options:
            raise RuntimeError("option generation failed")
        return GameEvent(
            event_description="改写后的完整故事",
            options=[
                EventOption(text="改写选项一", effects={"mood": 2}),
                EventOption(text="改写选项二", effects={"knowledge": 2}),
            ],
        )


def test_regenerate_replaces_story_options_and_revision_but_keeps_day() -> None:
    loop = FakeLoop()

    event = regenerate_daily_event_atomically(loop)

    assert event.event_id == "stable-event"
    assert event.revision == 2
    assert event.story_date == "2026-08-13"
    assert event.event_description == "重新生成的故事"
    assert event.options[0].text == "新选项一"
    assert loop.player_state.timeline["day_index"] == 0
    assert loop.player_state.day_history == []
    assert loop.player_state.pending_storylines == [
        {"description": "candidate side effect"}
    ]


def test_regenerate_passes_operation_id_into_candidate_pipeline() -> None:
    loop = FakeLoop()
    captured = {}
    original_generate = loop.generate_round_event

    def capture(**kwargs):
        captured.update(kwargs)
        return original_generate(**kwargs)

    loop.generate_round_event = capture

    regenerate_daily_event_atomically(loop, operation_id="sse-operation-456")

    assert captured["operation_id"] == "sse-operation-456"


def test_failed_regenerate_preserves_old_event() -> None:
    loop = FakeLoop()
    original = loop.current_event.model_dump()
    loop.fail_regenerate = True

    with pytest.raises(RuntimeError, match="generation failed"):
        regenerate_daily_event_atomically(loop)

    assert loop.current_event.model_dump() == original
    assert loop.player_state.current_event_data == original
    assert loop.player_state.pending_storylines == []


def test_regenerate_rejects_a_stale_operation_id_and_restores_old_event() -> None:
    loop = FakeLoop()
    original = loop.current_event.model_dump()
    generate = loop.generate_round_event

    def tampered_generation(**kwargs):
        candidate = generate(**kwargs)
        loop._active_daily_replacement_operation_id = "another-operation"
        return candidate

    loop.generate_round_event = tampered_generation

    with pytest.raises(ValueError, match="replacement_operation"):
        regenerate_daily_event_atomically(loop, operation_id="expected-operation")

    assert loop.current_event.model_dump() == original
    assert loop.player_state.current_event_data == original


def test_rewrite_regenerates_options_and_commits_atomically() -> None:
    loop = FakeLoop()

    event = rewrite_daily_event_atomically(
        loop,
        full_story="原故事",
        segment_to_replace="原故事",
        user_instruction="更紧凑",
        language="zh",
    )

    assert event.event_description == "改写后的完整故事"
    assert event.options[0].text == "改写选项一"
    assert event.revision == 2


def test_failed_rewrite_option_generation_preserves_story_and_options() -> None:
    loop = FakeLoop()
    original = loop.current_event.model_dump()
    loop.fail_options = True

    with pytest.raises(RuntimeError, match="option generation failed"):
        rewrite_daily_event_atomically(
            loop,
            full_story="原故事",
            segment_to_replace="原故事",
            user_instruction="更紧凑",
            language="zh",
        )

    assert loop.current_event.model_dump() == original
    assert loop.player_state.current_event_data == original


def test_scheduled_daily_event_receives_version_and_story_date() -> None:
    loop = FakeLoop()
    event = _event("预定事件")
    event.event_id = "legacy-scheduled"
    event.revision = 7
    event.story_date = ""

    stamped = apply_daily_event_metadata(event, loop.player_state)

    assert stamped.event_id.startswith("day-0-")
    assert stamped.revision == 1
    assert stamped.story_date == "2026-08-13"
