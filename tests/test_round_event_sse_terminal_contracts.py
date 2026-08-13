"""Provider-free wire contracts for durable round-event SSE subscribers."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import pytest

from src.api.routers.gameplay import sse_helpers
from src.api.services.event_generation_operation import (
    EventGenerationConflict,
    EventGenerationKey,
    EventGenerationOperation,
)


@dataclass
class _EventResult:
    description: str

    def model_dump(self) -> dict[str, Any]:
        return {"event_description": self.description, "options": [{"text": "继续"}]}


def _parse_frame(frame: str) -> tuple[str, int | None, object]:
    lines = frame.strip().splitlines()
    event_type = next(line.removeprefix("event: ") for line in lines if line.startswith("event: "))
    event_id = next(
        (int(line.removeprefix("id: ")) for line in lines if line.startswith("id: ")),
        None,
    )
    payload = json.loads(
        next(line.removeprefix("data: ") for line in lines if line.startswith("data: "))
    )
    return event_type, event_id, payload


async def _frames(stream) -> list[tuple[str, int | None, object]]:
    return [_parse_frame(frame) async for frame in stream]


def _operation() -> EventGenerationOperation:
    return EventGenerationOperation(
        EventGenerationKey(game_id=880_001, week=3, round_number=2)
    )


@pytest.mark.asyncio
async def test_reconnect_replays_only_story_frames_after_cursor_then_completes(monkeypatch) -> None:
    operation = _operation()
    first_id = operation.publish_story("已收到的片段")
    second_id = operation.publish_story("断线后补发的片段")
    operation.complete(_EventResult("完整事件"))

    monkeypatch.setattr(
        sse_helpers,
        "get_or_start_round_event_generation",
        lambda *args, **kwargs: (operation, False),
    )

    events = await _frames(
        sse_helpers.stream_round_event(object(), 880_001, session=object(), last_event_id=first_id)
    )

    assert events == [
        ("status", None, {"phase": "resuming"}),
        ("status", None, {"phase": "completed"}),
        ("story", second_id, "断线后补发的片段"),
        ("complete", None, {"event_description": "完整事件", "options": [{"text": "继续"}]}),
    ]


@pytest.mark.asyncio
async def test_failed_worker_emits_error_without_complete(monkeypatch) -> None:
    operation = _operation()
    operation.publish_story("在失败前生成的片段")
    operation.fail("provider timed out")

    monkeypatch.setattr(
        sse_helpers,
        "get_or_start_round_event_generation",
        lambda *args, **kwargs: (operation, False),
    )

    events = await _frames(sse_helpers.stream_round_event(object(), 880_001, session=object()))

    assert events[-1] == ("error", None, {"error": "provider timed out"})
    assert all(event_type != "complete" for event_type, _, _ in events)
    assert ("story", 0, "在失败前生成的片段") in events


@pytest.mark.asyncio
async def test_generation_conflict_emits_one_terminal_error(monkeypatch) -> None:
    monkeypatch.setattr(
        sse_helpers,
        "get_or_start_round_event_generation",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            EventGenerationConflict("generation already running for another round")
        ),
    )

    events = await _frames(sse_helpers.stream_round_event(object(), 880_001, session=object()))

    assert events == [
        ("error", None, {"error": "generation already running for another round"})
    ]
