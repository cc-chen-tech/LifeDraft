"""Durable event-generation ownership contracts (Layer 3)."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace

import pytest

from src.api.services.event_generation_operation import (
    EventGenerationConflict,
    EventGenerationCoordinator,
    EventGenerationKey,
)

pytestmark = [pytest.mark.unit]



class TestEventGenerationCoordinator:
    """One operation key has one producer and any number of subscribers."""

    def test_same_operation_key_has_exactly_one_starter(self):
        coordinator = EventGenerationCoordinator()
        key = EventGenerationKey(7, 3, 1, "event")

        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(lambda _: coordinator.get_or_create(key), range(8)))

        assert sum(1 for _, should_start in results if should_start) == 1
        assert len({id(operation) for operation, _ in results}) == 1

    def test_different_key_cannot_replace_running_operation(self):
        coordinator = EventGenerationCoordinator()
        coordinator.get_or_create(EventGenerationKey(7, 3, 1, "event"))

        with pytest.raises(EventGenerationConflict):
            coordinator.get_or_create(EventGenerationKey(7, 3, 2, "event"))

    def test_failed_operation_can_start_a_new_attempt_for_same_key(self):
        coordinator = EventGenerationCoordinator()
        key = EventGenerationKey(7, 3, 1, "event")
        first, first_should_start = coordinator.get_or_create(key)
        first.fail("provider unavailable")

        second, second_should_start = coordinator.get_or_create(key)

        assert first_should_start is True
        assert second_should_start is True
        assert second is not first

    def test_completed_operation_is_reused_for_same_key(self):
        coordinator = EventGenerationCoordinator()
        key = EventGenerationKey(7, 3, 1, "event")
        first, _ = coordinator.get_or_create(key)
        first.complete({"event_description": "done"})

        second, should_start = coordinator.get_or_create(key)

        assert second is first
        assert should_start is False

    def test_daily_requests_for_same_slot_join_running_operation(self):
        coordinator = EventGenerationCoordinator()
        first_key = EventGenerationKey(
            game_id=156,
            week=31,
            round_number=5,
            stage="daily",
            resolved_mode="generate_missing",
        )
        second_key = replace(
            first_key,
            stage="daily-reconnect",
            resolved_mode="replace_current",
            base_event_id="evt-current",
            base_revision=3,
        )

        first, first_should_start = coordinator.get_or_create_for_slot(first_key)
        second, second_should_start = coordinator.get_or_create_for_slot(second_key)

        assert first is second
        assert (first_should_start, second_should_start) == (True, False)


def test_daily_event_generation_key_changes_after_timeline_advance() -> None:
    from types import SimpleNamespace

    from src.api.routers.gameplay.sse_helpers import build_event_generation_key
    from src.game.daily_timeline import build_daily_timeline

    state = SimpleNamespace(
        week=0,
        current_round=0,
        timeline_version=2,
        timeline=build_daily_timeline(start_date="2026-08-13", day_index=0),
    )
    loop = SimpleNamespace(player_state=state)
    day_zero = build_event_generation_key(7, loop)

    state.timeline = build_daily_timeline(start_date="2026-08-13", day_index=1)
    day_one = build_event_generation_key(7, loop)

    assert day_zero != day_one
    assert day_zero.round_number == 0
    assert day_one.round_number == 1


class TestEventGenerationOperation:
    """Subscribers can replay exactly the chunks they have not seen."""

    def test_snapshot_replays_only_chunks_after_last_event_id(self):
        coordinator = EventGenerationCoordinator()
        operation, _ = coordinator.get_or_create(
            EventGenerationKey(7, 3, 1, "event")
        )
        assert operation.publish_story("A") == 0
        assert operation.publish_story("B") == 1

        snapshot = operation.snapshot_after(0)

        assert snapshot.chunks == ((1, "B"),)

    def test_snapshot_reports_phase_result_and_error(self):
        coordinator = EventGenerationCoordinator()
        operation, _ = coordinator.get_or_create(
            EventGenerationKey(7, 3, 1, "event")
        )
        operation.publish_phase("generating_story")

        assert operation.snapshot_after(-1).phase == "generating_story"

        operation.fail("upstream failed")
        failed = operation.snapshot_after(-1)
        assert failed.status == "failed"
        assert failed.error == "upstream failed"


class TestSSEErrorFormatContract:
    """Existing SSE error framing remains stable."""

    @pytest.mark.asyncio
    async def test_return_sse_error_format(self):
        from src.api.routers.gameplay.sse_helpers import return_sse_error

        chunks = []
        async for chunk in return_sse_error("Event generation failed"):
            chunks.append(chunk)
        assert len(chunks) == 1
        assert "event: error" in chunks[0]
        assert "Event generation failed" in chunks[0]
