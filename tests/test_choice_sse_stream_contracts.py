"""Provider-free contracts for choice SSE streaming state transitions."""

import json
from typing import Optional, Tuple

import pytest

from src.api.routers.gameplay.sse_helpers import stream_choice
from src.api.session_store import GameLoopSession


class _ChoiceLoop:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail

    def get_state(self):
        return None

    def make_round_choice(self, option_index, stream_callback, status_callback):
        if self.fail:
            raise ValueError("invalid option payload")
        status_callback("writing")
        stream_callback(f"choice-{option_index}-story")
        return {"summary": "choice committed", "option_index": option_index}

    def make_custom_choice(self, custom_text, stream_callback, status_callback):
        del custom_text
        return self.make_round_choice(0, stream_callback, status_callback)


def _event_type_and_payload(frame: str) -> Tuple[str, Optional[int], object]:
    lines = frame.strip().splitlines()
    event_type = next(
        line.removeprefix("event: ") for line in lines if line.startswith("event: ")
    )
    event_id = next(
        (int(line.removeprefix("id: ")) for line in lines if line.startswith("id: ")),
        None,
    )
    payload = json.loads(
        next(line.removeprefix("data: ") for line in lines if line.startswith("data: "))
    )
    return event_type, event_id, payload


@pytest.mark.asyncio
async def test_choice_stream_emits_status_story_and_complete_with_real_cache() -> None:
    game_id = 783_001
    session = GameLoopSession(game_loop=_ChoiceLoop(), game_id=game_id)

    frames = [frame async for frame in stream_choice(session.game_loop, 2, game_id, session=session)]
    events = [_event_type_and_payload(frame) for frame in frames]

    assert events == [
        ("status", None, {"phase": "preparing"}),
        ("status", None, {"phase": "writing"}),
        ("story", 0, "choice-2-story"),
        ("complete", None, {"summary": "choice committed", "option_index": 2}),
    ]
    assert session.get_cached_chunks_after(-1) == [(0, "choice-2-story")]


@pytest.mark.asyncio
async def test_choice_stream_replays_cached_story_before_new_output() -> None:
    game_id = 783_002
    session = GameLoopSession(game_loop=_ChoiceLoop(), game_id=game_id)
    session.cache_sse_chunk("before-reconnect")

    frames = [
        frame
        async for frame in stream_choice(
            session.game_loop, 1, game_id, session=session, last_event_id=-1
        )
    ]
    events = [_event_type_and_payload(frame) for frame in frames]

    assert events[:3] == [
        ("status", None, {"phase": "replaying", "cached_count": 1}),
        ("story", 0, "before-reconnect"),
        ("status", None, {"phase": "preparing"}),
    ]
    assert events[-1][0] == "complete"


@pytest.mark.asyncio
async def test_choice_stream_data_error_emits_error_and_clears_cache() -> None:
    game_id = 783_003
    session = GameLoopSession(game_loop=_ChoiceLoop(fail=True), game_id=game_id)
    session.cache_sse_chunk("stale-story")

    frames = [frame async for frame in stream_choice(session.game_loop, 0, game_id, session=session)]
    events = [_event_type_and_payload(frame) for frame in frames]

    assert events[-1] == ("error", None, {"error": "invalid option payload"})
    assert session.get_cached_chunks_after(-1) == []
