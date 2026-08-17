import json
from types import SimpleNamespace

import pytest

from src.api.routers.gameplay.sse_helpers import (
    _set_generation_resume_view,
    build_event_generation_key,
    stream_round_event,
    wait_for_event_generation,
)
from src.api.services.event_generation_operation import (
    EventGenerationCoordinator,
    EventGenerationKey,
)

pytestmark = [pytest.mark.unit]



class _Event:
    def __init__(self, payload):
        self.payload = payload

    def model_dump(self):
        return self.payload


class _Loop:
    def __init__(self, week=4, round_number=1):
        self.player_state = SimpleNamespace(
            week=week,
            current_round=round_number,
            resume_view=None,
        )

    def get_state(self):
        return None


class _Session:
    def __init__(self):
        self.event_generation = EventGenerationCoordinator()


def _payload(chunk: str):
    return json.loads(chunk.split("data: ", 1)[1])


@pytest.mark.asyncio
async def test_completed_operation_replays_terminal_phase_chunks_and_result():
    loop = _Loop()
    session = _Session()
    operation, should_start = session.event_generation.get_or_create(
        build_event_generation_key(71, loop)
    )
    assert should_start is True
    operation.publish_story("林见微发现旧信")
    operation.complete(_Event({"event_id": 71, "options": ["继续"]}))

    chunks = [chunk async for chunk in stream_round_event(loop, 71, session=session)]

    assert [_payload(chunk) for chunk in chunks] == [
        {"phase": "resuming"},
        {"phase": "completed"},
        "林见微发现旧信",
        {"event_id": 71, "options": ["继续"]},
    ]


@pytest.mark.asyncio
async def test_conflicting_active_operation_returns_an_sse_error():
    conflict_loop = _Loop(week=9, round_number=2)
    conflict_session = _Session()
    conflict_session.event_generation.get_or_create(EventGenerationKey(73, 9, 1))
    conflict_chunks = [
        chunk async for chunk in stream_round_event(conflict_loop, 73, session=conflict_session)
    ]
    assert "generation already running" in _payload(conflict_chunks[0])["error"]


@pytest.mark.asyncio
async def test_terminal_wait_and_resume_view_are_deterministic():
    loop = _Loop(week=8, round_number=3)
    session = _Session()
    operation, _ = session.event_generation.get_or_create(build_event_generation_key(74, loop))
    operation.complete(_Event({"event_id": 74}))

    snapshot = await wait_for_event_generation(operation)
    assert snapshot.status == "completed"
    assert snapshot.result.model_dump() == {"event_id": 74}

    _set_generation_resume_view(loop, 74, "generating")
    assert loop.player_state.resume_view == {
        "phase": "generating",
        "story_text": "",
        "round_summary": "",
        "summary_text": "",
        "error": "",
        "completed_week": 8,
        "completed_round": 3,
    }
    _set_generation_resume_view(loop, 74, "options")
    assert loop.player_state.resume_view is None
