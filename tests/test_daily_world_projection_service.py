from datetime import datetime, timedelta
from types import SimpleNamespace
from typing import Any, Optional

import pytest

from src.game.world_projection_schema import (
    WorldProjectionExtractionError,
    compute_projection_source_hash,
)


class FakeSession:
    def __init__(self, state: "WorkerState") -> None:
        self.state = state
        self.closed = False

    def get(self, _model: Any, projection_id: int) -> Any:
        return self.state.rows.get(projection_id)

    def close(self) -> None:
        self.closed = True
        self.state.closed_sessions += 1


class FakeRepository:
    def __init__(self, state: "WorkerState") -> None:
        self.state = state

    def claim_due(self, *, now: datetime, worker_id: str, limit: int) -> list[Any]:
        self.state.claim_calls.append((now, worker_id, limit))
        return self.state.claimed[:limit]

    def ensure_projection(self, identity: Any, source_hash: str) -> tuple[Any, str]:
        self.state.ensured.append((identity, source_hash))
        return identity, source_hash

    def count_game_attempts_between(
        self, game_id: int, start: datetime, end: datetime
    ) -> int:
        self.state.count_windows.append((game_id, start, end))
        return self.state.daily_attempts

    def start_attempt(self, projection_id: int, game_id: int, now: datetime) -> int:
        self.state.started_attempts.append((projection_id, game_id, now))
        return len(self.state.started_attempts)

    def finish_attempt(
        self,
        attempt_id: int,
        outcome: Optional[str],
        error_code: Optional[str],
        now: datetime,
    ) -> None:
        self.state.finished_attempts.append((attempt_id, outcome, error_code, now))

    def renew_lease(self, *args: Any, **kwargs: Any) -> bool:
        self.state.renewals.append((args, kwargs))
        if self.state.renew_results:
            return self.state.renew_results.pop(0)
        return True

    def mark_ready(self, *args: Any, **kwargs: Any) -> bool:
        self.state.ready_calls.append((args, kwargs))
        return self.state.ready_result

    def mark_retryable(self, *args: Any, **kwargs: Any) -> bool:
        self.state.retry_calls.append((args, kwargs))
        return self.state.retry_result


class WorkerState:
    def __init__(self, row: Any, *, daily_attempts: int = 0) -> None:
        self.rows = {row.projection_id: row}
        self.claimed: list[Any] = []
        self.daily_attempts = daily_attempts
        self.claim_calls: list[Any] = []
        self.count_windows: list[Any] = []
        self.started_attempts: list[Any] = []
        self.finished_attempts: list[Any] = []
        self.renewals: list[Any] = []
        self.ready_calls: list[Any] = []
        self.retry_calls: list[Any] = []
        self.ensured: list[Any] = []
        self.renew_results: list[bool] = []
        self.ready_result = True
        self.retry_result = True
        self.closed_sessions = 0


def _row(now: datetime, *, source_hash: Optional[str] = None) -> Any:
    source_hash = source_hash or compute_projection_source_hash("故事", ["选项"])
    return SimpleNamespace(
        projection_id=7,
        game_id=9,
        event_id="event-1",
        revision=3,
        source_hash=source_hash,
        attempt_count=1,
        lease_owner="worker-a",
        status="running",
        lease_expires_at=now + timedelta(minutes=5),
    )


def _service(state: WorkerState, now: datetime, extractor: Any) -> Any:
    from src.services.daily_world_projection import DailyWorldProjectionService

    return DailyWorldProjectionService(
        session_factory=lambda: FakeSession(state),
        repository_factory=lambda _session: FakeRepository(state),
        extractor=extractor,
        canonical_loader=lambda _game, _event, revision: {
            "revision": revision,
            "story": "故事",
            "options": ["选项"],
            "tracked_state": {},
        },
        now_fn=lambda: now,
        worker_id="worker-a",
    )


def test_retry_schedule_covers_all_persisted_boundaries() -> None:
    from src.services.daily_world_projection import DailyWorldProjectionService

    now = datetime(2026, 8, 17, 10, 0, 0)
    assert [
        DailyWorldProjectionService.next_retry_at(attempt, now)
        for attempt in range(1, 7)
    ] == [
        now + timedelta(seconds=5),
        now + timedelta(seconds=30),
        now + timedelta(seconds=120),
        now + timedelta(seconds=300),
        now + timedelta(seconds=1800),
        now + timedelta(seconds=7200),
    ]
    assert DailyWorldProjectionService.next_retry_at(7, now) == datetime(2026, 8, 18)


def test_import_has_no_worker_side_effects() -> None:
    from src.services.daily_world_projection import get_daily_world_projection_service

    service = get_daily_world_projection_service()

    assert service.is_running is False


def test_start_wake_stop_are_idempotent_with_injected_wake_event() -> None:
    from src.services.daily_world_projection import DailyWorldProjectionService

    class WakeEvent:
        def __init__(self) -> None:
            self.set_calls = 0

        def set(self) -> None:
            self.set_calls += 1

        def clear(self) -> None:
            pass

        def wait(self, _timeout: float) -> bool:
            return True

    wake = WakeEvent()
    now = datetime(2026, 8, 17, 10, 0, 0)
    state = WorkerState(_row(now))
    service = DailyWorldProjectionService(
        session_factory=lambda: FakeSession(state),
        repository_factory=lambda _session: FakeRepository(state),
        wake_event=wake,
    )

    service.start()
    service.start()
    service.wake()
    service.stop(wait=False)
    service.stop(wait=False)

    assert wake.set_calls >= 2
    assert service.is_running is False


def test_daily_cap_defers_without_provider_call_until_next_local_day() -> None:
    now = datetime(2026, 8, 17, 23, 30, 0)
    state = WorkerState(_row(now), daily_attempts=8)
    extractor = pytest.fail

    _service(state, now, extractor)._process_claim(7, now)

    assert state.started_attempts == []
    assert state.retry_calls[0][0][3] == datetime(2026, 8, 18)


@pytest.mark.parametrize(
    ("extractor", "expected_outcome", "expected_code", "ready_calls", "retry_calls"),
    [
        (
            lambda *_args: SimpleNamespace(no_change=True),
            "success",
            None,
            1,
            0,
        ),
        (
            lambda *_args: (_ for _ in ()).throw(
                WorldProjectionExtractionError("bad schema", code="invalid_schema")
            ),
            "extraction_error",
            "invalid_schema",
            0,
            1,
        ),
        (
            lambda *_args: (_ for _ in ()).throw(RuntimeError("provider exploded")),
            "unexpected_error",
            "unexpected_error",
            0,
            1,
        ),
    ],
)
def test_provider_attempts_are_finished_for_success_and_failures(
    extractor: Any,
    expected_outcome: str,
    expected_code: Optional[str],
    ready_calls: int,
    retry_calls: int,
) -> None:
    now = datetime(2026, 8, 17, 10, 0, 0)
    state = WorkerState(_row(now))

    _service(state, now, extractor)._process_claim(7, now)

    assert len(state.started_attempts) == 1
    assert [(outcome, code) for _, outcome, code, _ in state.finished_attempts] == [
        (expected_outcome, expected_code)
    ]
    assert len(state.ready_calls) == ready_calls
    assert len(state.retry_calls) == retry_calls


def test_missing_or_hash_mismatched_canonical_source_never_calls_provider() -> None:
    now = datetime(2026, 8, 17, 10, 0, 0)
    state = WorkerState(_row(now))
    service = _service(state, now, pytest.fail)
    service.canonical_loader = lambda *_args: {
        "revision": 3,
        "story": "changed after claim",
        "options": ["选项"],
        "tracked_state": {},
    }

    service._process_claim(7, now)

    assert state.started_attempts == []
    assert state.ready_calls == []
    assert state.retry_calls[0][0][2] == "source_hash_mismatch"


def test_lost_lease_after_extraction_cannot_publish_and_attempt_is_finished() -> None:
    now = datetime(2026, 8, 17, 10, 0, 0)
    state = WorkerState(_row(now))
    state.renew_results = [True, False]

    _service(
        state, now, lambda *_args: SimpleNamespace(no_change=False)
    )._process_claim(7, now)

    assert state.ready_calls == []
    assert state.finished_attempts[0][1:3] == ("lease_lost", "lease_lost")


def test_source_superseded_during_extraction_cannot_publish() -> None:
    now = datetime(2026, 8, 17, 10, 0, 0)
    state = WorkerState(_row(now))
    service = _service(state, now, lambda *_args: SimpleNamespace(no_change=False))
    sources = [
        {"revision": 3, "story": "故事", "options": ["选项"], "tracked_state": {}},
        {
            "revision": 4,
            "story": "new accepted story",
            "options": ["new option"],
            "tracked_state": {},
        },
    ]
    service.canonical_loader = lambda *_args: sources.pop(0)

    service._process_claim(7, now)

    assert state.ready_calls == []
    assert state.finished_attempts[0][1:3] == ("source_superseded", "source_superseded")


def test_expired_reclaims_are_processed_while_fresh_claims_are_repository_excluded() -> (
    None
):
    now = datetime(2026, 8, 17, 10, 0, 0)
    state = WorkerState(_row(now))
    state.claimed = [state.rows[7]]
    service = _service(state, now, lambda *_args: SimpleNamespace(no_change=True))

    assert service.run_once(now) == 1
    assert state.claim_calls == [(now, "worker-a", 4)]
    assert len(state.ready_calls) == 1


def test_heartbeat_uses_an_independent_short_lived_session() -> None:
    now = datetime(2026, 8, 17, 10, 0, 0)
    state = WorkerState(_row(now))
    service = _service(state, now, lambda *_args: SimpleNamespace(no_change=True))

    class Done:
        def __init__(self) -> None:
            self.calls = 0

        def wait(self, _timeout: float) -> bool:
            self.calls += 1
            return self.calls > 1

    service._lease_heartbeat(7, state.rows[7].source_hash, Done())

    assert len(state.renewals) == 1
    assert state.closed_sessions == 1


def test_enqueue_public_contract_accepts_game_event_and_player_state() -> None:
    now = datetime(2026, 8, 17, 10, 0, 0)
    state = WorkerState(_row(now))
    service = _service(state, now, pytest.fail)
    event = SimpleNamespace(
        event_id="event-1",
        revision=3,
        event_description="故事",
        options=["选项"],
        story_date="2026-08-17",
    )
    player_state = SimpleNamespace(timeline={"day_index": 12})

    service.ensure_world_projection(9, event, player_state)

    identity, source_hash = state.ensured[0]
    assert (
        identity.game_id,
        identity.event_id,
        identity.revision,
        identity.day_index,
    ) == (
        9,
        "event-1",
        3,
        12,
    )
    assert source_hash == compute_projection_source_hash("故事", ["选项"])
