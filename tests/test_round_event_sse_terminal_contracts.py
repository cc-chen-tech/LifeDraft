"""Provider-free wire contracts for durable round-event SSE subscribers."""

from __future__ import annotations

import json
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any

import pytest

from src.api.routers.gameplay import sse_helpers
from src.api.services.event_generation_operation import (
    EventGenerationConflict,
    EventGenerationCoordinator,
    EventGenerationKey,
    EventGenerationOperation,
)
from src.game.daily_timeline import build_daily_timeline


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
async def test_failed_worker_emits_structured_retry_reason(monkeypatch) -> None:
    operation = _operation()
    operation.fail(
        "故事角色一致性检查连续未通过",
        failure={
            "code": "HIGH_CONFIDENCE_UNKNOWN_PERSON",
            "summary": "故事角色一致性检查连续未通过",
            "detail": "失败稿没有保存，也没有改动人物关系。",
            "retryable": True,
            "attempts_used": 3,
            "quality_level": "expert",
            "operation_id": operation.operation_id,
        },
    )
    monkeypatch.setattr(
        sse_helpers,
        "get_or_start_round_event_generation",
        lambda *args, **kwargs: (operation, False),
    )

    events = await _frames(sse_helpers.stream_round_event(object(), 880_001, session=object()))

    payload = events[-1][2]
    assert payload["error"] == "故事角色一致性检查连续未通过"
    assert payload["code"] == "HIGH_CONFIDENCE_UNKNOWN_PERSON"
    assert payload["retryable"] is True
    assert payload["operation_id"] == operation.operation_id


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


@pytest.mark.asyncio
async def test_retry_status_includes_attempt_budget_metadata(monkeypatch) -> None:
    operation = _operation()
    operation.publish_phase(
        {
            "phase": "retry",
            "attempt": 2,
            "max_attempts": 3,
            "quality_level": "expert",
        }
    )
    monkeypatch.setattr(
        sse_helpers,
        "get_or_start_round_event_generation",
        lambda *args, **kwargs: (operation, False),
    )

    stream = sse_helpers.stream_round_event(object(), 880_001, session=object())
    first = _parse_frame(await stream.__anext__())
    second = _parse_frame(await stream.__anext__())
    await stream.aclose()

    assert first == ("status", None, {"phase": "resuming"})
    assert second == (
        "status",
        None,
        {
            "phase": "retry",
            "attempt": 2,
            "max_attempts": 3,
            "quality_level": "expert",
        },
    )


@pytest.mark.asyncio
async def test_reconnect_inside_repaired_candidate_keeps_received_prefix(monkeypatch) -> None:
    """重连游标已属于当前候选时，不得再次发 retry 清空已收到的前缀。"""
    operation = _operation()
    operation.publish_story("REJECTED")
    operation.publish_phase({"phase": "retry", "attempt": 2, "max_attempts": 3})
    fixed_a_id = operation.publish_story("FIXED-A")
    fixed_b_id = operation.publish_story("FIXED-B")
    monkeypatch.setattr(
        sse_helpers,
        "get_or_start_round_event_generation",
        lambda *args, **kwargs: (operation, False),
    )

    stream = sse_helpers.stream_round_event(
        object(), 880_001, session=object(), last_event_id=fixed_a_id
    )
    first = _parse_frame(await stream.__anext__())
    second = _parse_frame(await stream.__anext__())
    await stream.aclose()

    assert first == ("status", None, {"phase": "resuming"})
    assert second == ("story", fixed_b_id, "FIXED-B")


@pytest.mark.asyncio
async def test_daily_reconnect_inside_repaired_candidate_keeps_received_prefix(
    monkeypatch,
) -> None:
    operation = _operation()
    operation.publish_story("REJECTED")
    operation.publish_phase({"phase": "retry", "attempt": 2, "max_attempts": 3})
    fixed_a_id = operation.publish_story("FIXED-A")
    fixed_b_id = operation.publish_story("FIXED-B")
    monkeypatch.setattr(
        sse_helpers,
        "_get_or_start_daily_regeneration",
        lambda *args, **kwargs: (operation, False),
    )

    stream = sse_helpers._stream_daily_regeneration_operation(
        object(), 880_001, object(), last_event_id=fixed_a_id
    )
    first = _parse_frame(await stream.__anext__())
    second = _parse_frame(await stream.__anext__())
    await stream.aclose()

    assert first == ("status", None, {"phase": "resuming"})
    assert second == ("story", fixed_b_id, "FIXED-B")


def test_retry_discards_rejected_candidate_chunks_before_replay() -> None:
    operation = _operation()
    operation.publish_story("REJECTED")
    operation.publish_phase(
        {
            "phase": "retry",
            "attempt": 2,
            "max_attempts": 3,
            "quality_level": "expert",
        }
    )
    repaired_id = operation.publish_story("REPAIRED")

    snapshot = operation.snapshot_after(-1)

    assert snapshot.chunks == ((repaired_id, "REPAIRED"),)
    assert snapshot.retry_version == 1
    assert snapshot.retry_payload["phase"] == "retry"


def test_daily_regeneration_reconnect_does_not_start_a_second_transaction(
    monkeypatch,
) -> None:
    submitted = []

    class _Pool:
        def submit(self, fn, *args):
            submitted.append((fn, args))

    game_loop = SimpleNamespace(
        player_state=SimpleNamespace(
            timeline=build_daily_timeline(start_date="2026-08-08", day_index=7)
        ),
        current_event=SimpleNamespace(event_id="day-7-old", revision=4),
    )
    session = SimpleNamespace(event_generation=EventGenerationCoordinator())
    monkeypatch.setattr(sse_helpers, "_get_sse_thread_pool", lambda: _Pool())
    monkeypatch.setattr(
        sse_helpers,
        "_set_generation_resume_view",
        lambda *args, **kwargs: None,
    )

    first, should_start = sse_helpers._get_or_start_daily_regeneration(
        game_loop, 91, session, None
    )
    reconnected, reconnect_should_start = sse_helpers._get_or_start_daily_regeneration(
        game_loop, 91, session, 0
    )

    assert should_start is True
    assert reconnect_should_start is False
    assert reconnected is first
    assert len(submitted) == 1
