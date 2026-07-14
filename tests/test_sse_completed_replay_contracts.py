"""Provider-free contracts for completed SSE operation replay."""

import json

import pytest

from src.api.routers.gameplay.sse_helpers import stream_round_event
from src.api.services.event_generation_operation import (
    EventGenerationKey,
    EventGenerationOperation,
)
from src.game.state import PlayerState


class CompletedEvent:
    def model_dump(self) -> dict[str, object]:
        return {
            "event_description": "林岚收到了导师的回复。",
            "options": [{"text": "约定复盘"}, {"text": "独自整理"}],
        }


class CompletedOperationCoordinator:
    def __init__(self, operation: EventGenerationOperation) -> None:
        self.operation = operation
        self.keys: list[EventGenerationKey] = []

    def get_or_create(
        self, key: EventGenerationKey
    ) -> tuple[EventGenerationOperation, bool]:
        self.keys.append(key)
        return self.operation, False


class ReplaySession:
    def __init__(self, operation: EventGenerationOperation) -> None:
        self.event_generation = CompletedOperationCoordinator(operation)


class ReplayGameLoop:
    def __init__(self) -> None:
        self.player_state = PlayerState(week=6, current_round=1)


def _event_type_and_payload(raw_event: str) -> tuple[str, int | None, object]:
    lines = raw_event.strip().splitlines()
    event_type = next(line.removeprefix("event: ") for line in lines if line.startswith("event: "))
    event_id = next(
        (int(line.removeprefix("id: ")) for line in lines if line.startswith("id: ")),
        None,
    )
    payload = json.loads(
        next(line.removeprefix("data: ") for line in lines if line.startswith("data: "))
    )
    return event_type, event_id, payload


@pytest.mark.asyncio
async def test_completed_round_replay_emits_only_unseen_chunk_then_complete() -> None:
    key = EventGenerationKey(game_id=23, week=6, round_number=1)
    operation = EventGenerationOperation(key)
    operation.publish_story("已经收到的片段")
    operation.publish_story("断线后补发的片段")
    operation.complete(CompletedEvent())
    session = ReplaySession(operation)

    raw_events = [
        event
        async for event in stream_round_event(
            ReplayGameLoop(), game_id=23, session=session, last_event_id=0
        )
    ]
    events = [_event_type_and_payload(event) for event in raw_events]

    assert session.event_generation.keys == [key]
    assert events == [
        ("status", None, {"phase": "resuming"}),
        ("status", None, {"phase": "completed"}),
        ("story", 1, "断线后补发的片段"),
        ("complete", None, CompletedEvent().model_dump()),
    ]
