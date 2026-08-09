"""Provider-free terminal-state contracts for gameplay SSE helpers."""

import asyncio
import json

import pytest

from src.ai.models import EventOption, GameEvent
from src.api.routers.gameplay.sse_helpers import (
    replay_cached_then_complete,
    return_existing_event,
    wait_for_event_generation,
)
from src.api.services.event_generation_operation import (
    EventGenerationKey,
    EventGenerationOperation,
)


def _event() -> GameEvent:
    return GameEvent(
        event_description="The saved story remains visible.",
        options=[
            EventOption(text="Continue", effects={}),
            EventOption(text="Wait", effects={}),
        ],
    )


@pytest.mark.asyncio
async def test_wait_returns_completed_terminal_snapshot() -> None:
    operation = EventGenerationOperation(EventGenerationKey(1, 2, 0))
    event = _event()
    operation.complete(event)

    snapshot = await wait_for_event_generation(operation, timeout=0)

    assert snapshot.status == "completed"
    assert snapshot.result is event


@pytest.mark.asyncio
async def test_wait_returns_failed_terminal_snapshot() -> None:
    operation = EventGenerationOperation(EventGenerationKey(1, 2, 0))
    operation.fail("upstream unavailable")

    snapshot = await wait_for_event_generation(operation, timeout=0)

    assert snapshot.status == "failed"
    assert snapshot.error == "upstream unavailable"


@pytest.mark.asyncio
async def test_wait_times_out_without_mutating_running_operation() -> None:
    operation = EventGenerationOperation(EventGenerationKey(1, 2, 0))

    with pytest.raises(asyncio.TimeoutError):
        await wait_for_event_generation(operation, timeout=0)

    assert operation.status == "running"


@pytest.mark.asyncio
async def test_replay_and_existing_event_emit_stable_complete_payloads() -> None:
    event = _event()
    replay_frames = [frame async for frame in replay_cached_then_complete(None, 8, event)]
    existing_frames = [frame async for frame in return_existing_event(event)]

    assert "event: status" in replay_frames[0]
    assert json.loads(replay_frames[1].split("data: ", 1)[1]) == event.model_dump()
    assert json.loads(existing_frames[0].split("data: ", 1)[1]) == event.model_dump()
