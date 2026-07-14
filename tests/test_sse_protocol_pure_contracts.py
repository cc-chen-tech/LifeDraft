"""Deterministic contracts for the pure SSE protocol surface."""

import json
from types import SimpleNamespace

import pytest

from src.api.routers.gameplay.sse_helpers import (
    build_event_generation_key,
    clear_sse_cache_if_retry,
    make_sse_event,
    replay_cached_then_complete,
    return_sse_error,
)


class RecordingSession:
    def __init__(self):
        self.clear_calls = 0

    def clear_sse_cache(self):
        self.clear_calls += 1


def test_make_sse_event_preserves_unicode_payload_and_event_id():
    event = make_sse_event("story", {"text": "林见微继续前行"}, event_id=7)

    assert event.startswith("id: 7\nevent: story\ndata: ")
    assert event.endswith("\n\n")
    assert json.loads(event.split("data: ", 1)[1]) == {"text": "林见微继续前行"}


def test_retry_phase_clears_cache_but_other_phases_do_not():
    session = RecordingSession()

    clear_sse_cache_if_retry({"phase": "generating"}, session)
    clear_sse_cache_if_retry({"phase": "retry"}, session)
    clear_sse_cache_if_retry({}, session)

    assert session.clear_calls == 1


def test_generation_key_uses_game_week_round_and_event_stage():
    game_loop = SimpleNamespace(player_state=SimpleNamespace(week="12", current_round="2"))

    key = build_event_generation_key(41, game_loop)

    assert (key.game_id, key.week, key.round_number, key.stage) == (41, 12, 2, "event")


@pytest.mark.asyncio
async def test_return_sse_error_has_machine_and_display_messages():
    chunks = [chunk async for chunk in return_sse_error("generation stopped")]

    assert len(chunks) == 1
    assert json.loads(chunks[0].split("data: ", 1)[1]) == {
        "error": "generation stopped",
        "message": "generation stopped",
    }


@pytest.mark.asyncio
async def test_completed_replay_emits_resuming_then_complete_payload():
    event = SimpleNamespace(model_dump=lambda: {"event_id": 9, "story": "已完成"})
    chunks = [chunk async for chunk in replay_cached_then_complete(RecordingSession(), 4, event)]

    assert [chunk.split("\n", 1)[0] for chunk in chunks] == [
        "event: status",
        "event: complete",
    ]
    assert json.loads(chunks[1].split("data: ", 1)[1]) == {"event_id": 9, "story": "已完成"}
