import json
from datetime import datetime, timedelta, timezone
import threading
from types import SimpleNamespace
from typing import Any, Mapping, Optional

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker

from src.database.models import (
    Base,
    DailyWorldProjection,
    DailyWorldProjectionAttempt,
    Game,
    GameState,
)
from src.game.world_projection_schema import (
    WorldProjectionExtractionError,
    WorldPatch,
    WorldProjectionPayload,
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

    def commit(self) -> None:
        self.state.commits += 1

    def rollback(self) -> None:
        self.state.rollbacks += 1


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

    def release_lease(self, *args: Any, **kwargs: Any) -> bool:
        self.state.release_calls.append((args, kwargs))
        if self.state.release_results:
            result = self.state.release_results.pop(0)
            if isinstance(result, Exception):
                raise result
            return bool(result)
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
        self.release_calls: list[Any] = []
        self.ready_calls: list[Any] = []
        self.retry_calls: list[Any] = []
        self.ensured: list[Any] = []
        self.renew_results: list[bool] = []
        self.release_results: list[Any] = []
        self.ready_result = True
        self.retry_result = True
        self.closed_sessions = 0
        self.commits = 0
        self.rollbacks = 0


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
    state.renew_results = [False]

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


def test_file_sqlite_ensure_commits_before_the_service_session_closes(tmp_path) -> None:
    """A durable enqueue must survive the short-lived writer session."""
    from src.services.daily_world_projection import DailyWorldProjectionService
    from src.services.daily_world_projection_repository import ProjectionIdentity

    engine = create_engine(f"sqlite:///{tmp_path / 'projection.sqlite'}")
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)
    with sessions() as session:
        session.add(Game(game_id=9, initial_state={}))
        session.commit()

    service = DailyWorldProjectionService(session_factory=sessions)
    service.ensure_world_projection(
        ProjectionIdentity(game_id=9, event_id="event-1", revision=1, day_index=0),
        "故事",
        ["选项"],
    )

    with sessions() as session:
        assert session.query(DailyWorldProjection).count() == 1


def test_claiming_a_projection_does_not_consume_a_provider_attempt(tmp_path) -> None:
    """Only a successful provider-slot reservation increments attempt_count."""
    from src.services.daily_world_projection_repository import (
        DailyWorldProjectionRepository,
        ProjectionIdentity,
    )

    engine = create_engine(f"sqlite:///{tmp_path / 'claim-only.sqlite'}")
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)
    now = datetime(2026, 8, 17, 10, 0, 0)
    with sessions() as session:
        session.add(Game(game_id=9, initial_state={}))
        repo = DailyWorldProjectionRepository(session)
        row = repo.ensure_projection(
            ProjectionIdentity(game_id=9, event_id="event-1", revision=1, day_index=0),
            compute_projection_source_hash("故事", ["选项"]),
        )
        row.next_attempt_at = now - timedelta(seconds=1)
        session.commit()

    with sessions() as session:
        repo = DailyWorldProjectionRepository(session)
        [claimed] = repo.claim_due(now, "worker-a", 1)
        session.commit()
        assert claimed.attempt_count == 0
        assert (
            session.get(DailyWorldProjection, claimed.projection_id).attempt_count == 0
        )


def test_file_sqlite_claim_attempt_and_ready_are_committed_without_provider_session(
    tmp_path,
) -> None:
    """The provider callback observes no open service DB session and all writes persist."""
    from src.services.daily_world_projection import DailyWorldProjectionService
    from src.services.daily_world_projection_repository import (
        DailyWorldProjectionRepository,
        ProjectionIdentity,
    )

    engine = create_engine(f"sqlite:///{tmp_path / 'worker.sqlite'}")
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)
    now = datetime(2026, 8, 17, 10, 0, 0)
    with sessions() as session:
        session.add(Game(game_id=9, initial_state={}))
        repo = DailyWorldProjectionRepository(session)
        row = repo.ensure_projection(
            ProjectionIdentity(game_id=9, event_id="event-1", revision=1, day_index=0),
            compute_projection_source_hash("故事", ["选项"]),
        )
        row.next_attempt_at = now - timedelta(seconds=1)
        session.commit()

    extractor_calls: list[str] = []
    service = DailyWorldProjectionService(
        session_factory=sessions,
        extractor=lambda *_args: (
            extractor_calls.append("called")
            or WorldProjectionPayload(
                story_patch=WorldPatch(),
                option_patches={0: WorldPatch()},
                no_change=True,
            )
        ),
        canonical_loader=lambda *_args: {
            "revision": 1,
            "story": "故事",
            "options": ["选项"],
            "tracked_state": {},
        },
        now_fn=lambda: now,
        worker_id="worker-a",
    )

    assert service.run_once(now) == 1
    with sessions() as session:
        stored = session.query(DailyWorldProjection).one()
        assert extractor_calls == ["called"]
        assert stored.status == "ready_no_change"


def test_coverage_is_persisted_as_a_json_mapping_not_a_signal_dataclass(
    tmp_path,
) -> None:
    from src.services.daily_world_projection import DailyWorldProjectionService
    from src.services.daily_world_projection_repository import (
        DailyWorldProjectionRepository,
        ProjectionIdentity,
    )

    engine = create_engine(f"sqlite:///{tmp_path / 'coverage.sqlite'}")
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)
    now = datetime(2026, 8, 17, 10, 0, 0)
    with sessions() as session:
        session.add(Game(game_id=9, initial_state={}))
        row = DailyWorldProjectionRepository(session).ensure_projection(
            ProjectionIdentity(game_id=9, event_id="event-1", revision=1, day_index=0),
            compute_projection_source_hash("黑袍人抵达东海。", ["等待"]),
        )
        row.next_attempt_at = now - timedelta(seconds=1)
        session.commit()

    service = DailyWorldProjectionService(
        session_factory=sessions,
        extractor=lambda *_args: WorldProjectionPayload(
            story_patch=WorldPatch(location_updates=[{"location": "东海"}]),
            option_patches={0: WorldPatch()},
        ),
        canonical_loader=lambda *_args: {
            "revision": 1,
            "story": "黑袍人抵达东海。",
            "options": ["等待"],
            "tracked_state": {"character_locations": {"黑袍人": "长安"}},
        },
        now_fn=lambda: now,
        worker_id="worker-a",
    )

    service.run_once(now)
    with sessions() as session:
        coverage = session.query(DailyWorldProjection).one().coverage_json
        assert isinstance(coverage, dict)
        assert coverage["requires_nonempty_patch"] is True


def test_atomic_file_sqlite_slot_reservation_allows_only_one_eighth_call(
    tmp_path,
) -> None:
    """Concurrent projections share one durable game/day provider-call budget."""
    from src.services.daily_world_projection import DailyWorldProjectionService
    from src.services.daily_world_projection_repository import (
        DailyWorldProjectionRepository,
        ProjectionIdentity,
    )

    engine = create_engine(
        f"sqlite:///{tmp_path / 'slots.sqlite'}",
        connect_args={"check_same_thread": False, "timeout": 1},
    )
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)
    now = datetime(2026, 8, 17, 10, 0, 0)
    source_hash = compute_projection_source_hash("故事", ["选项"])
    with sessions() as session:
        session.add(Game(game_id=9, initial_state={}))
        repo = DailyWorldProjectionRepository(session)
        first = repo.ensure_projection(
            ProjectionIdentity(game_id=9, event_id="event-1", revision=1, day_index=0),
            source_hash,
        )
        second = repo.ensure_projection(
            ProjectionIdentity(game_id=9, event_id="event-2", revision=1, day_index=1),
            source_hash,
        )
        for projection in (first, second):
            projection.status = "running"
            projection.lease_owner = "worker-a"
            projection.lease_expires_at = now + timedelta(minutes=5)
        for _ in range(7):
            repo.start_attempt(first.projection_id, 9, now)
        first_id, second_id = first.projection_id, second.projection_id
        session.commit()

    service = DailyWorldProjectionService(
        session_factory=sessions, worker_id="worker-a"
    )
    rows = [
        SimpleNamespace(
            projection_id=first_id,
            game_id=9,
            attempt_count=1,
            source_hash=source_hash,
        ),
        SimpleNamespace(
            projection_id=second_id,
            game_id=9,
            attempt_count=1,
            source_hash=source_hash,
        ),
    ]
    barrier = threading.Barrier(2)
    results: list[Optional[int]] = []

    def reserve(row: Any) -> None:
        barrier.wait()
        results.append(service._reserve_attempt(row, now))

    threads = [threading.Thread(target=reserve, args=(row,)) for row in rows]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    from src.services.daily_world_projection_repository import AttemptReservationStatus

    assert (
        sum(result.status == AttemptReservationStatus.RESERVED for result in results)
        == 1
    )
    with sessions() as session:
        assert (
            session.query(DailyWorldProjectionAttempt).filter_by(game_id=9).count() == 8
        )


@pytest.mark.parametrize(
    ("zone", "now", "expected_bounds", "expected_next"),
    [
        (
            "Asia/Shanghai",
            datetime(2026, 8, 17, 16, 30, tzinfo=timezone.utc),
            (datetime(2026, 8, 17, 16), datetime(2026, 8, 18, 16)),
            datetime(2026, 8, 18, 16),
        ),
        (
            "America/New_York",
            datetime(2026, 3, 8, 7, 30, tzinfo=timezone.utc),
            (datetime(2026, 3, 8, 5), datetime(2026, 3, 9, 4)),
            datetime(2026, 3, 9, 4),
        ),
    ],
)
def test_local_day_boundaries_use_iana_zone_and_utc_database_times(
    zone: str,
    now: datetime,
    expected_bounds: tuple[datetime, datetime],
    expected_next: datetime,
) -> None:
    from src.services.daily_world_projection import DailyWorldProjectionService

    service = DailyWorldProjectionService(
        session_factory=lambda: pytest.fail("no database"), time_zone=zone
    )

    assert service.local_day_bounds_utc(now) == expected_bounds
    assert service.next_local_day(now) == expected_next


def test_stop_then_immediate_start_fences_the_old_scanner_generation() -> None:
    """A released old scanner must not claim again after a new generation starts."""
    from src.services.daily_world_projection import DailyWorldProjectionService

    first_entered = threading.Event()
    first_released = threading.Event()
    second_entered = threading.Event()
    calls: list[int] = []
    service = DailyWorldProjectionService(
        session_factory=lambda: pytest.fail("scanner fake should not open a session")
    )

    def run_once(_now: datetime, *, _generation: int, _cancel: Any) -> int:
        calls.append(_generation)
        if _generation == 1:
            first_entered.set()
            first_released.wait()
        else:
            second_entered.set()
        return 0

    service.run_once = run_once  # type: ignore[method-assign]
    service.start()
    assert first_entered.wait(1)
    service.stop(wait=False)
    service.start()
    assert second_entered.wait(1)
    first_released.set()
    assert first_released.wait(1)
    service.stop(wait=False)

    assert calls.count(1) == 1
    assert 2 in calls


def test_scanner_uses_fresh_post_claim_clock_for_health_interval() -> None:
    """A claim pass crossing 60 seconds must emit in that same scan iteration."""

    from src.services.daily_world_projection import DailyWorldProjectionService

    start = datetime(2026, 8, 17, 10, 0, 0)
    after_claim = start + timedelta(seconds=61)
    clock = iter((start, after_claim))
    cancel = threading.Event()
    claim_times: list[datetime] = []
    health_times: list[datetime] = []

    class ReadSession:
        def close(self) -> None:
            pass

    class OnePassWake:
        def wait(self, _timeout: float) -> bool:
            cancel.set()
            return True

        def clear(self) -> None:
            pass

    service = DailyWorldProjectionService(
        session_factory=ReadSession,
        now_fn=lambda: next(clock),
        wake_event=OnePassWake(),
        health_summary_fn=lambda _db, now: now,
        health_emitter=health_times.append,
    )
    service.run_once = (  # type: ignore[method-assign]
        lambda now, **_kwargs: claim_times.append(now) or 0
    )
    with service._lock:
        service._started = True
        service._generation = 1
        service._cancel_event = cancel
        service._last_health_emitted_at = start

    service._scan_loop(1, cancel)

    assert claim_times == [start]
    assert health_times == [after_claim]


def test_old_scanner_cannot_reserve_health_timestamp_after_restart() -> None:
    """The lifecycle lock must fence a stale generation at timestamp reservation."""

    from src.services.daily_world_projection import DailyWorldProjectionService

    start = datetime(2026, 8, 17, 10, 0, 0)
    old_cancel = threading.Event()
    new_cancel = threading.Event()
    attempted = threading.Event()
    emitted: list[object] = []
    errors: list[BaseException] = []
    service = DailyWorldProjectionService(
        session_factory=lambda: pytest.fail("stale scanner opened a health session"),
        health_summary_fn=lambda _db, _now: pytest.fail("stale scanner summarized"),
        health_emitter=emitted.append,
    )
    service._started = True
    service._generation = 1
    service._cancel_event = old_cancel
    service._last_health_emitted_at = start

    def old_scanner_health() -> None:
        attempted.set()
        try:
            service._emit_health_if_due(
                start + timedelta(seconds=61),
                generation=1,
                cancel=old_cancel,
            )
        except BaseException as exc:
            errors.append(exc)

    with service._lock:
        worker = threading.Thread(target=old_scanner_health)
        worker.start()
        assert attempted.wait(1)
        old_cancel.set()
        service._generation = 2
        service._cancel_event = new_cancel
    worker.join(1)

    assert not worker.is_alive()
    assert errors == []
    assert emitted == []
    assert service._last_health_emitted_at == start


@pytest.mark.parametrize(
    ("clock_values", "expected_claims", "expected_health", "expected_log"),
    [
        (
            (
                RuntimeError("claim clock unavailable"),
                datetime(2026, 8, 17, 10, 1, 1),
                datetime(2026, 8, 17, 10, 1, 2),
                datetime(2026, 8, 17, 10, 1, 2),
            ),
            [datetime(2026, 8, 17, 10, 1, 2)],
            [datetime(2026, 8, 17, 10, 1, 1)],
            "daily world projection scan failed",
        ),
        (
            (
                datetime(2026, 8, 17, 10, 0, 0),
                RuntimeError("health clock unavailable"),
                datetime(2026, 8, 17, 10, 1, 1),
                datetime(2026, 8, 17, 10, 1, 1),
            ),
            [
                datetime(2026, 8, 17, 10, 0, 0),
                datetime(2026, 8, 17, 10, 1, 1),
            ],
            [datetime(2026, 8, 17, 10, 1, 1)],
            "daily world projection health query failed",
        ),
    ],
)
def test_scanner_survives_clock_failures_and_stops_without_leaking_thread(
    clock_values: tuple[object, ...],
    expected_claims: list[datetime],
    expected_health: list[datetime],
    expected_log: str,
    caplog,
) -> None:
    """Transient clocks are contained without spinning or killing the scanner."""

    from src.services.daily_world_projection import DailyWorldProjectionService

    class TwoIterationWake:
        def __init__(self) -> None:
            self.wait_calls = 0
            self.second_wait = threading.Event()
            self.released = threading.Event()

        def wait(self, _timeout: float) -> bool:
            self.wait_calls += 1
            if self.wait_calls == 1:
                return False
            self.second_wait.set()
            return self.released.wait(1)

        def clear(self) -> None:
            pass

        def set(self) -> None:
            self.released.set()

    class ReadSession:
        def close(self) -> None:
            pass

    values = iter(clock_values)

    def now_fn() -> datetime:
        value = next(values)
        if isinstance(value, BaseException):
            raise value
        assert isinstance(value, datetime)
        return value

    wake = TwoIterationWake()
    claims: list[datetime] = []
    health: list[datetime] = []
    service = DailyWorldProjectionService(
        session_factory=ReadSession,
        now_fn=now_fn,
        wake_event=wake,
        health_summary_fn=lambda _db, now: now,
        health_emitter=health.append,
    )
    service.run_once = (  # type: ignore[method-assign]
        lambda now, **_kwargs: claims.append(now) or 0
    )
    service._last_health_emitted_at = datetime(2026, 8, 17, 10, 0, 0)

    service.start()
    scanner = service._scanner
    progressed = wake.second_wait.wait(1)
    service.stop(wait=True)

    assert progressed is True
    assert scanner is not None and not scanner.is_alive()
    assert wake.wait_calls == 2
    assert claims == expected_claims
    assert health == expected_health
    assert expected_log in caplog.text


def test_transaction_helper_commits_success_and_rolls_back_failure() -> None:
    now = datetime(2026, 8, 17, 10, 0, 0)
    state = WorkerState(_row(now))
    service = _service(state, now, pytest.fail)

    assert service._transaction(lambda _session, _repo: "committed") == "committed"
    with pytest.raises(RuntimeError, match="boom"):
        service._transaction(
            lambda _session, _repo: (_ for _ in ()).throw(RuntimeError("boom"))
        )

    assert state.commits == 1
    assert state.rollbacks == 1


def test_transaction_helper_retries_sqlite_lock_with_injected_wait() -> None:
    from src.services.daily_world_projection import DailyWorldProjectionService

    now = datetime(2026, 8, 17, 10, 0, 0)
    state = WorkerState(_row(now))
    waits: list[int] = []
    calls = 0
    service = DailyWorldProjectionService(
        session_factory=lambda: FakeSession(state),
        repository_factory=lambda _session: FakeRepository(state),
        lock_retry_wait=waits.append,
    )

    def write(_session: Any, _repo: Any) -> str:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise OperationalError("UPDATE", {}, RuntimeError("database is locked"))
        return "ok"

    assert service._transaction(write) == "ok"
    assert waits == [0]
    assert (state.commits, state.rollbacks) == (1, 1)


def test_file_sqlite_heartbeat_renewal_commits_and_releases_its_lock(tmp_path) -> None:
    from src.services.daily_world_projection import DailyWorldProjectionService
    from src.services.daily_world_projection_repository import (
        DailyWorldProjectionRepository,
        ProjectionIdentity,
    )

    engine = create_engine(f"sqlite:///{tmp_path / 'heartbeat.sqlite'}")
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)
    now = datetime(2026, 8, 17, 10, 0, 0)
    with sessions() as session:
        session.add(Game(game_id=9, initial_state={}))
        row = DailyWorldProjectionRepository(session).ensure_projection(
            ProjectionIdentity(game_id=9, event_id="event-1", revision=1, day_index=0),
            compute_projection_source_hash("故事", ["选项"]),
        )
        row.status = "running"
        row.lease_owner = "worker-a"
        row.lease_expires_at = now + timedelta(minutes=1)
        row_id, source_hash = row.projection_id, row.source_hash
        session.commit()

    service = DailyWorldProjectionService(
        session_factory=sessions, worker_id="worker-a", now_fn=lambda: now
    )

    class Done:
        calls = 0

        def wait(self, _timeout: float) -> bool:
            self.calls += 1
            return self.calls > 1

    service._lease_heartbeat(row_id, source_hash, Done())
    with sessions() as session:
        stored = session.get(DailyWorldProjection, row_id)
        assert stored.lease_expires_at == now + timedelta(minutes=5)


def test_file_sqlite_typed_failure_commits_retry_and_finished_attempt(tmp_path) -> None:
    from src.services.daily_world_projection import DailyWorldProjectionService
    from src.services.daily_world_projection_repository import (
        DailyWorldProjectionRepository,
        ProjectionIdentity,
    )

    engine = create_engine(f"sqlite:///{tmp_path / 'retry.sqlite'}")
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)
    now = datetime(2026, 8, 17, 10, 0, 0)
    with sessions() as session:
        session.add(Game(game_id=9, initial_state={}))
        row = DailyWorldProjectionRepository(session).ensure_projection(
            ProjectionIdentity(game_id=9, event_id="event-1", revision=1, day_index=0),
            compute_projection_source_hash("故事", ["选项"]),
        )
        row.next_attempt_at = now - timedelta(seconds=1)
        session.commit()

    service = DailyWorldProjectionService(
        session_factory=sessions,
        extractor=lambda *_args: (_ for _ in ()).throw(
            WorldProjectionExtractionError("bad response", code="invalid_schema")
        ),
        canonical_loader=lambda *_args: {
            "revision": 1,
            "story": "故事",
            "options": ["选项"],
            "tracked_state": {},
        },
        now_fn=lambda: now,
        worker_id="worker-a",
    )

    service.run_once(now)
    with sessions() as session:
        stored = session.query(DailyWorldProjection).one()
        attempt = session.query(DailyWorldProjectionAttempt).one()
        assert (stored.status, stored.error_code, stored.next_attempt_at) == (
            "failed_retryable",
            "invalid_schema",
            now + timedelta(seconds=5),
        )
        assert stored.attempt_count == 1
        assert (attempt.outcome, attempt.error_code) == (
            "extraction_error",
            "invalid_schema",
        )


def test_replace_after_canonical_validation_is_fenced_without_provider_or_attempt(
    tmp_path,
) -> None:
    from src.services.daily_world_projection import DailyWorldProjectionService
    from src.services.daily_world_projection_repository import (
        DailyWorldProjectionRepository,
        ProjectionIdentity,
    )

    engine = create_engine(f"sqlite:///{tmp_path / 'fenced.sqlite'}")
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)
    now = datetime(2026, 8, 17, 10, 0, 0)
    old_hash = compute_projection_source_hash("故事", ["选项"])
    new_hash = compute_projection_source_hash("新故事", ["新选项"])
    identity = ProjectionIdentity(
        game_id=9, event_id="event-1", revision=1, day_index=0
    )
    with sessions() as session:
        session.add(Game(game_id=9, initial_state={}))
        row = DailyWorldProjectionRepository(session).ensure_projection(
            identity, old_hash
        )
        row.next_attempt_at = now - timedelta(seconds=1)
        row_id = row.projection_id
        session.commit()

    provider_calls: list[str] = []
    replaced = False

    def canonical_loader(*_args: Any) -> Mapping[str, Any]:
        nonlocal replaced
        if not replaced:
            replaced = True
            with sessions() as session:
                DailyWorldProjectionRepository(session).replace_projection_source(
                    identity, expected_old_hash=old_hash, new_hash=new_hash
                )
                session.commit()
        return {
            "revision": 1,
            "story": "故事",
            "options": ["选项"],
            "tracked_state": {},
        }

    service = DailyWorldProjectionService(
        session_factory=sessions,
        extractor=lambda *_args: provider_calls.append("called"),
        canonical_loader=canonical_loader,
        now_fn=lambda: now,
        worker_id="worker-a",
    )

    service.run_once(now)
    with sessions() as session:
        stored = session.get(DailyWorldProjection, row_id)
        assert provider_calls == []
        assert session.query(DailyWorldProjectionAttempt).count() == 0
        assert (stored.source_hash, stored.attempt_count, stored.status) == (
            new_hash,
            0,
            "pending",
        )


def test_stop_restart_cancels_old_generation_after_blocked_provider_returns(
    tmp_path,
) -> None:
    from src.services.daily_world_projection import DailyWorldProjectionService
    from src.services.daily_world_projection_repository import (
        DailyWorldProjectionRepository,
        ProjectionIdentity,
    )

    engine = create_engine(
        f"sqlite:///{tmp_path / 'cancel.sqlite'}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)
    now = datetime(2026, 8, 17, 10, 0, 0)
    with sessions() as session:
        session.add(Game(game_id=9, initial_state={}))
        row = DailyWorldProjectionRepository(session).ensure_projection(
            ProjectionIdentity(game_id=9, event_id="event-1", revision=1, day_index=0),
            compute_projection_source_hash("故事", ["选项"]),
        )
        row.next_attempt_at = now - timedelta(seconds=1)
        row_id = row.projection_id
        session.commit()
    with sessions() as session:
        [claimed] = DailyWorldProjectionRepository(session).claim_due(
            now, "worker-a", 1
        )
        session.commit()
        assert claimed.lease_owner == "worker-a"

    entered, release = threading.Event(), threading.Event()

    def blocked_extractor(*_args: Any) -> WorldProjectionPayload:
        entered.set()
        release.wait()
        return WorldProjectionPayload(
            story_patch=WorldPatch(), option_patches={0: WorldPatch()}, no_change=True
        )

    service = DailyWorldProjectionService(
        session_factory=sessions,
        extractor=blocked_extractor,
        canonical_loader=lambda *_args: {
            "revision": 1,
            "story": "故事",
            "options": ["选项"],
            "tracked_state": {},
        },
        now_fn=lambda: now,
        worker_id="worker-a",
        claim_limit=0,
    )
    service.start()
    old_cancel = service._cancel_event
    assert old_cancel is not None
    service._generation_owners[id(old_cancel)] = "worker-a"
    worker = threading.Thread(
        target=service._process_claim, args=(row_id, now, old_cancel)
    )
    worker.start()
    assert entered.wait(1)
    service.stop(wait=False)
    service.start()
    release.set()
    worker.join()
    service.stop(wait=False)

    with sessions() as session:
        stored = session.get(DailyWorldProjection, row_id)
        attempt = session.query(DailyWorldProjectionAttempt).one()
        assert stored.status == "running"
        assert (attempt.outcome, attempt.error_code) == ("cancelled", "cancelled")


def test_cancelled_claim_without_provider_keeps_attempt_count_and_ledger_empty(
    tmp_path,
) -> None:
    from src.services.daily_world_projection import DailyWorldProjectionService
    from src.services.daily_world_projection_repository import (
        DailyWorldProjectionRepository,
        ProjectionIdentity,
    )

    engine = create_engine(f"sqlite:///{tmp_path / 'cancel-before-provider.sqlite'}")
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)
    now = datetime(2026, 8, 17, 10, 0, 0)
    with sessions() as session:
        session.add(Game(game_id=9, initial_state={}))
        row = DailyWorldProjectionRepository(session).ensure_projection(
            ProjectionIdentity(game_id=9, event_id="event-1", revision=1, day_index=0),
            compute_projection_source_hash("故事", ["选项"]),
        )
        row.next_attempt_at = now - timedelta(seconds=1)
        row_id = row.projection_id
        session.commit()
    with sessions() as session:
        DailyWorldProjectionRepository(session).claim_due(now, "worker-a", 1)
        session.commit()

    cancel = threading.Event()
    cancel.set()
    service = DailyWorldProjectionService(
        session_factory=sessions,
        extractor=pytest.fail,
        canonical_loader=lambda *_args: pytest.fail("source should not load"),
        now_fn=lambda: now,
        worker_id="worker-a",
    )
    service._process_claim(row_id, now, cancel)

    with sessions() as session:
        stored = session.get(DailyWorldProjection, row_id)
        assert stored.attempt_count == 0
        assert session.query(DailyWorldProjectionAttempt).count() == 0


def test_stop_before_final_publish_commit_rolls_back_ready_and_cancels_attempt(
    tmp_path,
) -> None:
    from src.services.daily_world_projection import DailyWorldProjectionService
    from src.services.daily_world_projection_repository import (
        DailyWorldProjectionRepository,
        ProjectionIdentity,
    )

    engine = create_engine(
        f"sqlite:///{tmp_path / 'publish-rollback.sqlite'}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)
    now = datetime(2026, 8, 17, 10, 0, 0)
    with sessions() as session:
        session.add(Game(game_id=9, initial_state={}))
        row = DailyWorldProjectionRepository(session).ensure_projection(
            ProjectionIdentity(game_id=9, event_id="event-1", revision=1, day_index=0),
            compute_projection_source_hash("故事", ["选项"]),
        )
        row.next_attempt_at = now - timedelta(seconds=1)
        row_id = row.projection_id
        session.commit()
    with sessions() as session:
        DailyWorldProjectionRepository(session).claim_due(now, "worker-a", 1)
        session.commit()

    flushed, release = threading.Event(), threading.Event()

    class BarrierRepository(DailyWorldProjectionRepository):
        def mark_ready(self, *args: Any, **kwargs: Any) -> bool:
            result = super().mark_ready(*args, **kwargs)
            flushed.set()
            release.wait()
            return result

    service = DailyWorldProjectionService(
        session_factory=sessions,
        repository_factory=BarrierRepository,
        extractor=lambda *_args: WorldProjectionPayload(
            story_patch=WorldPatch(), option_patches={0: WorldPatch()}, no_change=True
        ),
        canonical_loader=lambda *_args: {
            "revision": 1,
            "story": "故事",
            "options": ["选项"],
            "tracked_state": {},
        },
        now_fn=lambda: now,
        worker_id="worker-a",
        claim_limit=0,
    )
    service.start()
    cancel = service._cancel_event
    assert cancel is not None
    service._generation_owners[id(cancel)] = "worker-a"
    worker = threading.Thread(target=service._process_claim, args=(row_id, now, cancel))
    worker.start()
    assert flushed.wait(1)
    service.stop(wait=False)
    release.set()
    worker.join()

    with sessions() as session:
        stored = session.get(DailyWorldProjection, row_id)
        attempt = session.query(DailyWorldProjectionAttempt).one()
        assert stored.status == "running"
        assert (attempt.outcome, attempt.error_code) == ("cancelled", "cancelled")


def test_final_publish_commit_before_stop_keeps_ready_and_success(tmp_path) -> None:
    from src.services.daily_world_projection import DailyWorldProjectionService
    from src.services.daily_world_projection_repository import (
        DailyWorldProjectionRepository,
        ProjectionIdentity,
    )

    engine = create_engine(
        f"sqlite:///{tmp_path / 'publish-commit.sqlite'}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)
    now = datetime(2026, 8, 17, 10, 0, 0)
    with sessions() as session:
        session.add(Game(game_id=9, initial_state={}))
        row = DailyWorldProjectionRepository(session).ensure_projection(
            ProjectionIdentity(game_id=9, event_id="event-1", revision=1, day_index=0),
            compute_projection_source_hash("故事", ["选项"]),
        )
        row.next_attempt_at = now - timedelta(seconds=1)
        row_id = row.projection_id
        session.commit()
    with sessions() as session:
        DailyWorldProjectionRepository(session).claim_due(now, "worker-a", 1)
        session.commit()

    committed, release = threading.Event(), threading.Event()
    service = DailyWorldProjectionService(
        session_factory=sessions,
        extractor=lambda *_args: WorldProjectionPayload(
            story_patch=WorldPatch(), option_patches={0: WorldPatch()}, no_change=True
        ),
        canonical_loader=lambda *_args: {
            "revision": 1,
            "story": "故事",
            "options": ["选项"],
            "tracked_state": {},
        },
        now_fn=lambda: now,
        worker_id="worker-a",
        claim_limit=0,
        after_final_publish_commit=lambda: (committed.set(), release.wait()),
    )
    service.start()
    cancel = service._cancel_event
    assert cancel is not None
    service._generation_owners[id(cancel)] = "worker-a"
    worker = threading.Thread(target=service._process_claim, args=(row_id, now, cancel))
    worker.start()
    assert committed.wait(1)
    service.stop(wait=False)
    release.set()
    worker.join()

    with sessions() as session:
        stored = session.get(DailyWorldProjection, row_id)
        attempt = session.query(DailyWorldProjectionAttempt).one()
        assert stored.status == "ready_no_change"
        assert (attempt.outcome, attempt.error_code) == ("success", None)


def test_stop_during_heartbeat_commit_is_nonblocking_and_releases_old_lease(
    tmp_path,
) -> None:
    """A stopped generation cannot leave a post-stop heartbeat lease extension."""
    from src.services.daily_world_projection import DailyWorldProjectionService
    from src.services.daily_world_projection_repository import (
        DailyWorldProjectionRepository,
        ProjectionIdentity,
    )

    engine = create_engine(
        f"sqlite:///{tmp_path / 'heartbeat-stop.sqlite'}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)
    now = datetime(2026, 8, 17, 10, 0, 0)
    with sessions() as session:
        session.add(Game(game_id=9, initial_state={}))
        row = DailyWorldProjectionRepository(session).ensure_projection(
            ProjectionIdentity(game_id=9, event_id="event-1", revision=1, day_index=0),
            compute_projection_source_hash("故事", ["选项"]),
        )
        row.status = "running"
        row.lease_expires_at = now + timedelta(minutes=5)
        row_id, source_hash = row.projection_id, row.source_hash
        session.commit()

    commit_started, release_commit = threading.Event(), threading.Event()
    service = DailyWorldProjectionService(
        session_factory=sessions,
        worker_id="worker-a",
        claim_limit=0,
        now_fn=lambda: now + timedelta(minutes=4),
        before_lease_commit=lambda: (commit_started.set(), release_commit.wait()),
    )
    service.start()
    cancel = service._cancel_event
    assert cancel is not None
    owner = service._owner_for(cancel)
    with sessions() as session:
        stored = session.get(DailyWorldProjection, row_id)
        stored.lease_owner = owner
        session.commit()

    class Done:
        calls = 0

        def wait(self, _timeout: float) -> bool:
            self.calls += 1
            return self.calls > 1

    heartbeat = threading.Thread(
        target=service._lease_heartbeat,
        args=(row_id, source_hash, Done(), owner, cancel),
    )
    heartbeat.start()
    assert commit_started.wait(1)
    import time

    started = time.monotonic()
    service.stop(wait=False)
    assert time.monotonic() - started < 0.2
    release_commit.set()
    heartbeat.join()

    with sessions() as session:
        stored = session.get(DailyWorldProjection, row_id)
        assert stored.lease_expires_at == now + timedelta(minutes=4)
        assert (
            DailyWorldProjectionRepository(session)
            .claim_due(now + timedelta(minutes=4), "new-worker", 1)[0]
            .lease_owner
            == "new-worker"
        )


@pytest.mark.parametrize(
    "worker_id",
    [None, "诊断-worker-" + "用户" * 80],
)
def test_generation_owner_fits_persisted_lease_owner_and_is_unique(
    worker_id: Optional[str],
) -> None:
    """Generation owners remain diagnosable without exceeding String(96)."""
    from src.services.daily_world_projection import DailyWorldProjectionService

    now = datetime(2026, 8, 17, 10, 0, 0)
    state = WorkerState(_row(now))
    service = DailyWorldProjectionService(
        session_factory=lambda: FakeSession(state),
        repository_factory=lambda _session: FakeRepository(state),
        worker_id=worker_id,
        claim_limit=0,
    )

    service.start()
    first_cancel = service._cancel_event
    assert first_cancel is not None
    first_owner = service._owner_for(first_cancel)
    service.stop(wait=False)
    service.start()
    second_cancel = service._cancel_event
    assert second_cancel is not None
    second_owner = service._owner_for(second_cancel)
    service.stop(wait=False)

    for owner in (first_owner, second_owner):
        assert len(owner) <= 96
        assert len(owner.encode("utf-8")) <= 96
        assert owner.startswith(service.worker_id[:8])
    assert first_owner != second_owner


@pytest.mark.parametrize(
    ("worker_id", "expected_owner"),
    [
        ("worker-a", "worker-a"),
        ("诊断-worker-" + "用户" * 160, None),
    ],
)
def test_direct_run_once_claims_with_a_stable_bounded_base_owner(
    worker_id: str, expected_owner: Optional[str]
) -> None:
    """Direct callers persist the same bounded owner they later fence/renew."""
    from src.services.daily_world_projection import DailyWorldProjectionService

    now = datetime(2026, 8, 17, 10, 0, 0)
    state = WorkerState(_row(now))
    service = DailyWorldProjectionService(
        session_factory=lambda: FakeSession(state),
        repository_factory=lambda _session: FakeRepository(state),
        worker_id=worker_id,
    )

    assert service.run_once(now) == 0
    [(claim_now, claimed_owner, _limit)] = state.claim_calls
    assert claim_now == now
    assert claimed_owner == service._owner_for()
    assert service._owner_for() == claimed_owner
    assert len(claimed_owner) <= 96
    assert len(claimed_owner.encode("utf-8")) <= 96
    if expected_owner is not None:
        assert claimed_owner == expected_owner
    else:
        assert claimed_owner.startswith(worker_id[:8])

    state.rows[7].lease_owner = claimed_owner
    assert service._claimed_snapshot(7, claimed_owner) is not None
    assert service._renew_lease(7, state.rows[7].source_hash, now, claimed_owner)
    assert state.renewals[-1][0][1] == claimed_owner


def test_heartbeat_contains_exhausted_release_lock_failures() -> None:
    """A stopped heartbeat must not leak a daemon exception after lock retries."""
    from src.services.daily_world_projection import DailyWorldProjectionService

    now = datetime(2026, 8, 17, 10, 0, 0)
    state = WorkerState(_row(now))
    locked = OperationalError("UPDATE projection", {}, Exception("database is locked"))
    state.release_results = [locked, locked, locked]
    waits: list[int] = []
    service = DailyWorldProjectionService(
        session_factory=lambda: FakeSession(state),
        repository_factory=lambda _session: FakeRepository(state),
        now_fn=lambda: now,
        worker_id="worker-a",
        lock_retry_wait=waits.append,
    )
    cancel = threading.Event()
    cancel.set()
    done = threading.Event()
    done.set()
    errors: list[Exception] = []

    def run_heartbeat() -> None:
        try:
            service._lease_heartbeat(
                7, state.rows[7].source_hash, done, "worker-a", cancel
            )
        except Exception as exc:  # pragma: no cover - assertion below is the contract
            errors.append(exc)

    heartbeat = threading.Thread(target=run_heartbeat)
    heartbeat.start()
    heartbeat.join(1)

    assert not heartbeat.is_alive()
    assert errors == []
    assert len(state.release_calls) == 3
    assert waits == [0, 1]
    assert state.finished_attempts == []


def test_stop_heartbeat_retries_locked_release_then_allows_reclaim(tmp_path) -> None:
    """One bounded release retry compensates a stopped old-generation lease."""
    from src.services.daily_world_projection import DailyWorldProjectionService
    from src.services.daily_world_projection_repository import (
        DailyWorldProjectionRepository,
        ProjectionIdentity,
    )

    engine = create_engine(
        f"sqlite:///{tmp_path / 'heartbeat-release-retry.sqlite'}",
        connect_args={"check_same_thread": False, "timeout": 1},
    )
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)
    now = datetime(2026, 8, 17, 10, 0, 0)
    with sessions() as session:
        session.add(Game(game_id=9, initial_state={}))
        row = DailyWorldProjectionRepository(session).ensure_projection(
            ProjectionIdentity(game_id=9, event_id="event-1", revision=1, day_index=0),
            compute_projection_source_hash("故事", ["选项"]),
        )
        row.status = "running"
        row.lease_expires_at = now + timedelta(minutes=5)
        row_id, source_hash = row.projection_id, row.source_hash
        session.commit()

    class FlakyReleaseRepository:
        release_attempts = 0

        def __init__(self, session: Any) -> None:
            self.delegate = DailyWorldProjectionRepository(session)

        def __getattr__(self, name: str) -> Any:
            return getattr(self.delegate, name)

        def release_lease(self, *args: Any, **kwargs: Any) -> bool:
            type(self).release_attempts += 1
            if type(self).release_attempts == 1:
                raise OperationalError(
                    "UPDATE daily_world_projections",
                    {},
                    Exception("database is locked"),
                )
            return self.delegate.release_lease(*args, **kwargs)

    retry_attempts: list[int] = []
    service = DailyWorldProjectionService(
        session_factory=sessions,
        repository_factory=FlakyReleaseRepository,
        now_fn=lambda: now,
        worker_id="worker-a",
        claim_limit=0,
        lock_retry_wait=retry_attempts.append,
    )
    service.start()
    cancel = service._cancel_event
    assert cancel is not None
    owner = service._owner_for(cancel)
    with sessions() as session:
        session.get(DailyWorldProjection, row_id).lease_owner = owner
        session.commit()

    done = threading.Event()
    with service._lock:
        service._heartbeat_done.add(done)
    heartbeat = threading.Thread(
        target=service._lease_heartbeat,
        args=(row_id, source_hash, done, owner, cancel),
    )
    heartbeat.start()
    import time

    started = time.monotonic()
    service.stop(wait=False)
    assert time.monotonic() - started < 0.2
    heartbeat.join(1)
    assert not heartbeat.is_alive()
    assert FlakyReleaseRepository.release_attempts == 2
    assert retry_attempts == [0]

    with sessions() as session:
        [claimed] = DailyWorldProjectionRepository(session).claim_due(
            now, "new-worker", 1
        )
        assert claimed.lease_owner == "new-worker"


def test_stop_before_claim_permit_rolls_back_old_generation_claim(tmp_path) -> None:
    """A stop before the claim commit permit leaves no old-generation lease."""
    from src.services.daily_world_projection import DailyWorldProjectionService
    from src.services.daily_world_projection_repository import (
        DailyWorldProjectionRepository,
        ProjectionIdentity,
    )

    engine = create_engine(
        f"sqlite:///{tmp_path / 'claim-stop-before-permit.sqlite'}",
        connect_args={"check_same_thread": False, "timeout": 1},
    )
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)
    now = datetime(2026, 8, 17, 10, 0, 0)
    with sessions() as session:
        session.add(Game(game_id=9, initial_state={}))
        row = DailyWorldProjectionRepository(session).ensure_projection(
            ProjectionIdentity(game_id=9, event_id="event-1", revision=1, day_index=0),
            compute_projection_source_hash("故事", ["选项"]),
        )
        row.next_attempt_at = now
        row_id = row.projection_id
        session.commit()

    flushed, release_commit = threading.Event(), threading.Event()
    service = DailyWorldProjectionService(
        session_factory=sessions,
        worker_id="worker-a",
        claim_limit=0,
        now_fn=lambda: now,
        before_claim_guard=lambda: (flushed.set(), release_commit.wait()),
    )
    service.start()
    old_cancel, old_generation = service._cancel_event, service._generation
    assert old_cancel is not None
    service.claim_limit = 1
    worker = threading.Thread(
        target=service.run_once,
        args=(now,),
        kwargs={"_generation": old_generation, "_cancel": old_cancel},
    )
    worker.start()
    assert flushed.wait(1)
    import time

    started = time.monotonic()
    service.stop(wait=False)
    assert time.monotonic() - started < 0.2
    service.claim_limit = 0
    service.start()
    release_commit.set()
    worker.join(1)
    assert not worker.is_alive()

    with sessions() as session:
        stored = session.get(DailyWorldProjection, row_id)
        assert stored.status == "pending"
        assert stored.lease_owner is None
        [claimed] = DailyWorldProjectionRepository(session).claim_due(
            now, "new-worker", 1
        )
        assert claimed.lease_owner == "new-worker"
    service.stop(wait=False)


def test_stop_after_claim_permit_releases_old_generation_lease(tmp_path) -> None:
    """A claim permitted before stop compensates its committed old lease."""
    from src.services.daily_world_projection import DailyWorldProjectionService
    from src.services.daily_world_projection_repository import (
        DailyWorldProjectionRepository,
        ProjectionIdentity,
    )

    engine = create_engine(
        f"sqlite:///{tmp_path / 'claim-stop-after-permit.sqlite'}",
        connect_args={"check_same_thread": False, "timeout": 1},
    )
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)
    now = datetime(2026, 8, 17, 10, 0, 0)
    with sessions() as session:
        session.add(Game(game_id=9, initial_state={}))
        row = DailyWorldProjectionRepository(session).ensure_projection(
            ProjectionIdentity(game_id=9, event_id="event-1", revision=1, day_index=0),
            compute_projection_source_hash("故事", ["选项"]),
        )
        row.next_attempt_at = now
        row_id = row.projection_id
        session.commit()

    permitted, release_commit = threading.Event(), threading.Event()
    service = DailyWorldProjectionService(
        session_factory=sessions,
        worker_id="worker-a",
        claim_limit=0,
        now_fn=lambda: now,
        before_claim_commit=lambda: (permitted.set(), release_commit.wait()),
    )
    service.start()
    old_cancel, old_generation = service._cancel_event, service._generation
    assert old_cancel is not None
    service.claim_limit = 1
    worker = threading.Thread(
        target=service.run_once,
        args=(now,),
        kwargs={"_generation": old_generation, "_cancel": old_cancel},
    )
    worker.start()
    assert permitted.wait(1)
    import time

    started = time.monotonic()
    service.stop(wait=False)
    assert time.monotonic() - started < 0.2
    service.claim_limit = 0
    service.start()
    release_commit.set()
    worker.join(1)
    assert not worker.is_alive()

    with sessions() as session:
        [claimed] = DailyWorldProjectionRepository(session).claim_due(
            now, "new-worker", 1
        )
        assert claimed.lease_owner == "new-worker"
        assert claimed.status == "running"
        assert claimed.projection_id == row_id
    service.stop(wait=False)


def test_cancelled_queued_claim_future_releases_its_old_lease(tmp_path) -> None:
    """cancel_futures compensation does not leave a queued claim fenced for 5m."""
    from src.services.daily_world_projection import DailyWorldProjectionService
    from src.services.daily_world_projection_repository import (
        DailyWorldProjectionRepository,
        ProjectionIdentity,
    )

    engine = create_engine(
        f"sqlite:///{tmp_path / 'queued-claim-stop.sqlite'}",
        connect_args={"check_same_thread": False, "timeout": 1},
    )
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)
    now = datetime(2026, 8, 17, 10, 0, 0)
    with sessions() as session:
        session.add(Game(game_id=9, initial_state={}))
        row = DailyWorldProjectionRepository(session).ensure_projection(
            ProjectionIdentity(game_id=9, event_id="event-1", revision=1, day_index=0),
            compute_projection_source_hash("故事", ["选项"]),
        )
        row.next_attempt_at = now
        row_id = row.projection_id
        session.commit()

    blocker_started, unblock, released = (
        threading.Event(),
        threading.Event(),
        threading.Event(),
    )
    service = DailyWorldProjectionService(
        session_factory=sessions,
        worker_id="worker-a",
        claim_limit=0,
        extraction_workers=1,
        now_fn=lambda: now,
    )
    service.start()
    old_cancel, old_generation = service._cancel_event, service._generation
    assert old_cancel is not None and service._pool is not None
    service._pool.submit(lambda: (blocker_started.set(), unblock.wait()))
    assert blocker_started.wait(1)
    original_release = service._release_lease

    def observed_release(*args: Any, **kwargs: Any) -> bool:
        result = original_release(*args, **kwargs)
        released.set()
        return result

    service._release_lease = observed_release  # type: ignore[method-assign]
    service.claim_limit = 1
    assert service.run_once(now, _generation=old_generation, _cancel=old_cancel) == 1
    import time

    started = time.monotonic()
    service.stop(wait=False)
    assert time.monotonic() - started < 0.2
    assert released.wait(1)
    unblock.set()

    with sessions() as session:
        [claimed] = DailyWorldProjectionRepository(session).claim_due(
            now, "new-worker", 1
        )
        assert claimed.projection_id == row_id
        assert claimed.lease_owner == "new-worker"


def test_old_claim_compensation_does_not_release_replacement_owner(tmp_path) -> None:
    """Claim cleanup is fenced by both the old generation owner and source."""
    from src.services.daily_world_projection import DailyWorldProjectionService
    from src.services.daily_world_projection_repository import (
        DailyWorldProjectionRepository,
        ProjectionIdentity,
    )

    engine = create_engine(f"sqlite:///{tmp_path / 'claim-replacement.sqlite'}")
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)
    now = datetime(2026, 8, 17, 10, 0, 0)
    old_hash = compute_projection_source_hash("旧故事", ["旧选项"])
    with sessions() as session:
        session.add(Game(game_id=9, initial_state={}))
        row = DailyWorldProjectionRepository(session).ensure_projection(
            ProjectionIdentity(game_id=9, event_id="event-1", revision=1, day_index=0),
            old_hash,
        )
        row.status = "running"
        row.lease_owner = "new-owner"
        row.lease_expires_at = now + timedelta(minutes=5)
        row.source_hash = compute_projection_source_hash("新故事", ["新选项"])
        row_id, new_hash = row.projection_id, row.source_hash
        session.commit()

    service = DailyWorldProjectionService(session_factory=sessions, now_fn=lambda: now)
    service._release_claims([(row_id, old_hash)], "old-owner", now)

    with sessions() as session:
        stored = session.get(DailyWorldProjection, row_id)
        assert stored.lease_owner == "new-owner"
        assert stored.lease_expires_at == now + timedelta(minutes=5)
        assert stored.source_hash == new_hash


def test_stop_before_provider_slot_permit_rolls_back_zero_call_reservation(
    tmp_path,
) -> None:
    """Stop-first must not persist a zero-provider slot, count, or lease."""
    from src.services.daily_world_projection import DailyWorldProjectionService
    from src.services.daily_world_projection_repository import (
        DailyWorldProjectionRepository,
        ProjectionIdentity,
    )

    engine = create_engine(
        f"sqlite:///{tmp_path / 'reservation-stop-before-permit.sqlite'}",
        connect_args={"check_same_thread": False, "timeout": 1},
    )
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)
    now = datetime(2026, 8, 17, 10, 0, 0)
    with sessions() as session:
        session.add(Game(game_id=9, initial_state={}))
        row = DailyWorldProjectionRepository(session).ensure_projection(
            ProjectionIdentity(game_id=9, event_id="event-1", revision=1, day_index=0),
            compute_projection_source_hash("故事", ["选项"]),
        )
        row.status = "running"
        row.lease_expires_at = now + timedelta(minutes=5)
        row_id = row.projection_id
        session.commit()

    reserved, release_permit, provider_called = (
        threading.Event(),
        threading.Event(),
        threading.Event(),
    )
    service = DailyWorldProjectionService(
        session_factory=sessions,
        extractor=lambda *_args: provider_called.set(),
        canonical_loader=lambda *_args: {
            "revision": 1,
            "story": "故事",
            "options": ["选项"],
            "tracked_state": {},
        },
        now_fn=lambda: now,
        worker_id="worker-a",
        claim_limit=0,
        before_reservation_guard=lambda: (reserved.set(), release_permit.wait()),
    )
    service.start()
    cancel = service._cancel_event
    assert cancel is not None
    owner = service._owner_for(cancel)
    with sessions() as session:
        session.get(DailyWorldProjection, row_id).lease_owner = owner
        session.commit()

    worker = threading.Thread(target=service._process_claim, args=(row_id, now, cancel))
    worker.start()
    assert reserved.wait(1)
    service.stop(wait=False)
    release_permit.set()
    worker.join(1)
    assert not worker.is_alive()
    assert not provider_called.is_set()

    with sessions() as session:
        stored = session.get(DailyWorldProjection, row_id)
        assert stored.attempt_count == 0
        assert session.query(DailyWorldProjectionAttempt).count() == 0
        [claimed] = DailyWorldProjectionRepository(session).claim_due(
            now, "new-worker", 1
        )
        assert claimed.lease_owner == "new-worker"


def test_ready_and_attempt_finish_are_atomic_when_legacy_finish_locks(tmp_path) -> None:
    """A successful ready transition cannot commit with a running ledger row."""
    from src.services.daily_world_projection import DailyWorldProjectionService
    from src.services.daily_world_projection_repository import (
        DailyWorldProjectionRepository,
        ProjectionIdentity,
    )

    engine = create_engine(f"sqlite:///{tmp_path / 'ready-attempt-atomic.sqlite'}")
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)
    now = datetime(2026, 8, 17, 10, 0, 0)
    with sessions() as session:
        session.add(Game(game_id=9, initial_state={}))
        row = DailyWorldProjectionRepository(session).ensure_projection(
            ProjectionIdentity(game_id=9, event_id="event-1", revision=1, day_index=0),
            compute_projection_source_hash("故事", ["选项"]),
        )
        row.status = "running"
        row.lease_owner = "worker-a"
        row.lease_expires_at = now + timedelta(minutes=5)
        row_id = row.projection_id
        session.commit()

    class LockedLegacyFinishRepository(DailyWorldProjectionRepository):
        def finish_attempt(self, *args: Any, **kwargs: Any) -> None:
            raise OperationalError(
                "UPDATE daily_world_projection_attempts",
                {},
                Exception("database is locked"),
            )

    service = DailyWorldProjectionService(
        session_factory=sessions,
        repository_factory=LockedLegacyFinishRepository,
        extractor=lambda *_args: WorldProjectionPayload(
            story_patch=WorldPatch(), option_patches={0: WorldPatch()}, no_change=True
        ),
        canonical_loader=lambda *_args: {
            "revision": 1,
            "story": "故事",
            "options": ["选项"],
            "tracked_state": {},
        },
        now_fn=lambda: now,
        worker_id="worker-a",
        lock_retry_wait=lambda _attempt: None,
    )
    service._process_claim(row_id, now)

    with sessions() as session:
        projection = session.get(DailyWorldProjection, row_id)
        attempt = session.query(DailyWorldProjectionAttempt).one()
        assert not (
            projection.status == "ready_no_change" and attempt.outcome == "running"
        )


def test_provider_failure_retry_and_attempt_finish_are_atomic(tmp_path) -> None:
    """A retryable provider failure cannot commit while its ledger stays running."""
    from src.services.daily_world_projection import DailyWorldProjectionService
    from src.services.daily_world_projection_repository import (
        DailyWorldProjectionRepository,
        ProjectionIdentity,
    )

    engine = create_engine(f"sqlite:///{tmp_path / 'retry-attempt-atomic.sqlite'}")
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)
    now = datetime(2026, 8, 17, 10, 0, 0)
    with sessions() as session:
        session.add(Game(game_id=9, initial_state={}))
        row = DailyWorldProjectionRepository(session).ensure_projection(
            ProjectionIdentity(game_id=9, event_id="event-1", revision=1, day_index=0),
            compute_projection_source_hash("故事", ["选项"]),
        )
        row.status, row.lease_owner = "running", "worker-a"
        row.lease_expires_at = now + timedelta(minutes=5)
        row_id = row.projection_id
        session.commit()

    class LockedLegacyFinishRepository(DailyWorldProjectionRepository):
        def finish_attempt(self, *args: Any, **kwargs: Any) -> None:
            raise OperationalError(
                "UPDATE daily_world_projection_attempts",
                {},
                Exception("database is locked"),
            )

    service = DailyWorldProjectionService(
        session_factory=sessions,
        repository_factory=LockedLegacyFinishRepository,
        extractor=lambda *_args: (_ for _ in ()).throw(RuntimeError("provider failed")),
        canonical_loader=lambda *_args: {
            "revision": 1,
            "story": "故事",
            "options": ["选项"],
            "tracked_state": {},
        },
        now_fn=lambda: now,
        worker_id="worker-a",
        lock_retry_wait=lambda _attempt: None,
    )
    service._process_claim(row_id, now)

    with sessions() as session:
        projection = session.get(DailyWorldProjection, row_id)
        attempt = session.query(DailyWorldProjectionAttempt).one()
        assert not (
            projection.status == "failed_retryable" and attempt.outcome == "running"
        )


def test_provider_cancel_finalizes_ledger_and_releases_lease_atomically(
    tmp_path,
) -> None:
    """A post-provider stop cannot strand a running ledger or five-minute lease."""
    from src.services.daily_world_projection import DailyWorldProjectionService
    from src.services.daily_world_projection_repository import (
        DailyWorldProjectionRepository,
        ProjectionIdentity,
    )

    engine = create_engine(f"sqlite:///{tmp_path / 'cancel-attempt-atomic.sqlite'}")
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)
    now = datetime(2026, 8, 17, 10, 0, 0)
    with sessions() as session:
        session.add(Game(game_id=9, initial_state={}))
        row = DailyWorldProjectionRepository(session).ensure_projection(
            ProjectionIdentity(game_id=9, event_id="event-1", revision=1, day_index=0),
            compute_projection_source_hash("故事", ["选项"]),
        )
        row.status, row.lease_owner = "running", "worker-a"
        row.lease_expires_at = now + timedelta(minutes=5)
        row_id = row.projection_id
        session.commit()

    class LockedLegacyFinishRepository(DailyWorldProjectionRepository):
        def finish_attempt(self, *args: Any, **kwargs: Any) -> None:
            raise OperationalError(
                "UPDATE daily_world_projection_attempts",
                {},
                Exception("database is locked"),
            )

    cancel = threading.Event()
    service = DailyWorldProjectionService(
        session_factory=sessions,
        repository_factory=LockedLegacyFinishRepository,
        extractor=lambda *_args: (
            cancel.set()
            or WorldProjectionPayload(
                story_patch=WorldPatch(),
                option_patches={0: WorldPatch()},
                no_change=True,
            )
        ),
        canonical_loader=lambda *_args: {
            "revision": 1,
            "story": "故事",
            "options": ["选项"],
            "tracked_state": {},
        },
        now_fn=lambda: now,
        worker_id="worker-a",
        lock_retry_wait=lambda _attempt: None,
    )
    service._process_claim(row_id, now, cancel)

    with sessions() as session:
        projection = session.get(DailyWorldProjection, row_id)
        [attempt] = session.query(DailyWorldProjectionAttempt).all()
        assert projection.status == "running"
        assert (attempt.outcome, attempt.error_code) == ("cancelled", "cancelled")
        [claimed] = DailyWorldProjectionRepository(session).claim_due(
            now, "new-worker", 1
        )
        assert claimed.lease_owner == "new-worker"


def test_submit_failure_releases_all_unsubmitted_claims_in_a_batch(tmp_path) -> None:
    """A later submit failure cannot strand already committed batch leases."""
    from concurrent.futures import Future

    from src.services.daily_world_projection import DailyWorldProjectionService
    from src.services.daily_world_projection_repository import (
        DailyWorldProjectionRepository,
        ProjectionIdentity,
    )

    engine = create_engine(f"sqlite:///{tmp_path / 'claim-batch-submit.sqlite'}")
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)
    now = datetime(2026, 8, 17, 10, 0, 0)
    with sessions() as session:
        session.add(Game(game_id=9, initial_state={}))
        repo = DailyWorldProjectionRepository(session)
        rows = [
            repo.ensure_projection(
                ProjectionIdentity(
                    game_id=9, event_id=f"event-{index}", revision=1, day_index=index
                ),
                compute_projection_source_hash("故事", ["选项"]),
            )
            for index in range(3)
        ]
        for row in rows:
            row.next_attempt_at = now
        row_ids = [row.projection_id for row in rows]
        session.commit()

    class FirstThenFailPool:
        calls = 0

        def submit(self, *_args: Any, **_kwargs: Any) -> Future[Any]:
            self.calls += 1
            if self.calls == 1:
                return Future()
            raise RuntimeError("pool stopped")

    service = DailyWorldProjectionService(
        session_factory=sessions,
        worker_id="worker-a",
        claim_limit=3,
        now_fn=lambda: now,
    )
    cancel = threading.Event()
    service._started = True
    service._generation = 1
    service._cancel_event = cancel
    service._generation_owners[id(cancel)] = "old-owner"
    service._pool = FirstThenFailPool()  # type: ignore[assignment]

    assert service.run_once(now, _generation=1, _cancel=cancel) == 3
    with sessions() as session:
        reclaimed = DailyWorldProjectionRepository(session).claim_due(
            now, "new-worker", 3
        )
        assert {row.projection_id for row in reclaimed} == set(row_ids[1:])


def test_stop_before_heartbeat_releases_pre_provider_reservation_lease(
    tmp_path,
) -> None:
    """A stop after the slot permit records one real provider call, then releases."""
    from src.services.daily_world_projection import DailyWorldProjectionService
    from src.services.daily_world_projection_repository import (
        DailyWorldProjectionRepository,
        ProjectionIdentity,
    )

    engine = create_engine(
        f"sqlite:///{tmp_path / 'reservation-stop.sqlite'}",
        connect_args={"check_same_thread": False, "timeout": 1},
    )
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)
    now = datetime(2026, 8, 17, 10, 0, 0)
    with sessions() as session:
        session.add(Game(game_id=9, initial_state={}))
        row = DailyWorldProjectionRepository(session).ensure_projection(
            ProjectionIdentity(game_id=9, event_id="event-1", revision=1, day_index=0),
            compute_projection_source_hash("故事", ["选项"]),
        )
        row.status = "running"
        row.lease_expires_at = now + timedelta(minutes=5)
        row_id, source_hash = row.projection_id, row.source_hash
        session.commit()

    reserved, release_worker, provider_calls = threading.Event(), threading.Event(), []
    service = DailyWorldProjectionService(
        session_factory=sessions,
        extractor=lambda *_args: (
            provider_calls.append("called")
            or WorldProjectionPayload(
                story_patch=WorldPatch(),
                option_patches={0: WorldPatch()},
                no_change=True,
            )
        ),
        canonical_loader=lambda *_args: {
            "revision": 1,
            "story": "故事",
            "options": ["选项"],
            "tracked_state": {},
        },
        now_fn=lambda: now,
        worker_id="worker-a",
        claim_limit=0,
    )
    service.start()
    cancel = service._cancel_event
    assert cancel is not None
    owner = service._owner_for(cancel)
    with sessions() as session:
        stored = session.get(DailyWorldProjection, row_id)
        stored.lease_owner = owner
        session.commit()

    reserve_attempt = service._reserve_attempt

    def pause_after_reservation(*args: Any, **kwargs: Any) -> Any:
        result = reserve_attempt(*args, **kwargs)
        reserved.set()
        assert release_worker.wait(1)
        return result

    service._reserve_attempt = pause_after_reservation  # type: ignore[method-assign]
    worker = threading.Thread(target=service._process_claim, args=(row_id, now, cancel))
    worker.start()
    assert reserved.wait(1)
    service.stop(wait=False)
    release_worker.set()
    worker.join(1)
    assert not worker.is_alive()

    with sessions() as session:
        stored = session.get(DailyWorldProjection, row_id)
        assert provider_calls == ["called"]
        assert stored.attempt_count == 1
        [attempt] = session.query(DailyWorldProjectionAttempt).all()
        assert (attempt.outcome, attempt.error_code) == ("cancelled", "cancelled")
        [claimed] = DailyWorldProjectionRepository(session).claim_due(
            now, "new-worker", 1
        )
        assert claimed.lease_owner == "new-worker"
        assert claimed.source_hash == source_hash


def test_canonical_source_uses_highest_state_id_when_timestamps_run_backwards(
    temp_db_file,
) -> None:
    from src.services.daily_world_projection import DailyWorldProjectionService

    engine, _ = temp_db_file
    sessions = sessionmaker(bind=engine)
    old_event = {
        "event_id": "old",
        "revision": 1,
        "event_description": "旧故事",
        "options": [{"text": "旧选项", "effects": {}}],
    }
    current_event = {
        "event_id": "current",
        "revision": 1,
        "event_description": "孙悟空已返回花果山。",
        "options": [{"text": "休息", "effects": {}}],
    }
    with sessions.begin() as session:
        game = Game(language="zh", initial_state={})
        session.add(game)
        session.flush()
        session.add(
            GameState(
                game_id=game.game_id,
                week=1,
                age=18,
                state_json={"current_event_data": old_event},
                created_at=datetime(2026, 8, 17, 12, 0, 0),
            )
        )
        session.add(
            GameState(
                game_id=game.game_id,
                week=1,
                age=18,
                state_json={
                    "current_event_data": current_event,
                    "day_history": [{"event_description": "很长的历史正文"}],
                    "world_model_data": {
                        "character_locations": {"孙悟空": {"location": "东海"}},
                        "active_commitments": [
                            {"description": "守护花果山", "parties": ["孙悟空"]}
                        ],
                        "causal_chains": [
                            {
                                "cause": "大闹天宫",
                                "expected_consequence": "天兵追捕",
                                "characters": ["孙悟空"],
                            }
                        ],
                    },
                    "landmarks": {"花果山": {"name": "花果山"}},
                    "world_projection_state": {
                        "world": {
                            "location_updates": [
                                {"character": "孙悟空", "location": "花果山"}
                            ],
                            "commitment_updates": [
                                {"description": "守护花果山", "parties": ["孙悟空"]}
                            ],
                            "causal_updates": [
                                {
                                    "cause": "大闹天宫",
                                    "expected_consequence": "天兵追捕",
                                    "characters": ["孙悟空"],
                                }
                            ],
                        }
                    },
                },
                created_at=datetime(2026, 8, 17, 11, 0, 0),
            )
        )
        game_id = int(game.game_id)

    source = DailyWorldProjectionService(
        session_factory=sessions
    )._load_canonical_source(game_id, "current", 1)

    assert source is not None
    assert source["story"] == "孙悟空已返回花果山。"
    tracked = source["tracked_state"]
    assert "day_history" not in tracked
    assert "current_event_data" not in tracked
    assert tracked["character_locations"]["孙悟空"]["location"] == "花果山"
    assert tracked["active_commitments"][0]["description"] == "守护花果山"
    assert tracked["causal_chains"][0]["cause"] == "大闹天宫"


def test_compact_tracked_state_has_a_hard_total_budget() -> None:
    from src.services.daily_world_projection import DailyWorldProjectionService

    huge = "\x00\n" * 125_000
    tracked = DailyWorldProjectionService._compact_tracked_state(
        {
            "world_model_data": {
                "character_locations": {
                    f"角色{index}": {"location": huge} for index in range(200)
                },
                "active_commitments": [
                    {"description": huge, "parties": [f"角色{index}"]}
                    for index in range(200)
                ],
                "causal_chains": [
                    {"cause": huge, "expected_consequence": huge}
                    for _index in range(200)
                ],
            },
            "landmarks": {
                f"地点{index}": {"description": huge} for index in range(200)
            },
            "world_projection_state": {
                "world": {
                    "location_updates": [{"character": "孙悟空", "location": "花果山"}]
                }
            },
        }
    )

    encoded = json.dumps(tracked, ensure_ascii=False, separators=(",", ":"))
    assert len(encoded) <= 32_000
    assert "孙悟空" in tracked["character_locations"]


def test_compact_tracked_state_prefers_all_projection_world_categories() -> None:
    from src.game.world_projection_coverage import detect_world_change_signals
    from src.services.daily_world_projection import DailyWorldProjectionService

    tracked = DailyWorldProjectionService._compact_tracked_state(
        {
            "world_model_data": {
                "causal_chains": [
                    {
                        "cause": "旧日误会",
                        "expected_consequence": "仍然争吵",
                    }
                ]
            },
            "world_projection_state": {
                "world": {
                    "fact_updates": [{"subject": "孙悟空", "fact": "持有金箍棒"}],
                    "foreshadowing_seeds": [{"description": "天庭来使"}],
                    "habit_updates": [{"character": "孙悟空", "habit": "每日练棍"}],
                    "location_updates": [{"character": "孙悟空", "location": "花果山"}],
                    "career_updates": [
                        {"character": "孙悟空", "current_job": "美猴王"}
                    ],
                    "commitment_updates": [
                        {"description": "守护花果山", "parties": ["孙悟空"]}
                    ],
                    "causal_updates": [
                        {
                            "cause": "偷取金箍棒",
                            "expected_consequence": "龙宫追责",
                            "characters": ["孙悟空"],
                        }
                    ],
                }
            },
        }
    )

    signals = detect_world_change_signals("偷取金箍棒引发的后果终于解决。", [], tracked)

    assert signals.requires_nonempty_patch is True
    assert "causal_updates" in signals.categories
    assert tracked["active_commitments"][0]["description"] == "守护花果山"
    assert tracked["fact_updates"][0]["fact"] == "持有金箍棒"
    assert tracked["habit_updates"][0]["habit"] == "每日练棍"
    assert tracked["career_updates"][0]["current_job"] == "美猴王"
    assert tracked["foreshadowing_seeds"][0]["description"] == "天庭来使"


def test_compact_tracked_state_reserves_budget_for_each_projection_category() -> None:
    from src.game.world_projection_coverage import detect_world_change_signals
    from src.services.daily_world_projection import DailyWorldProjectionService

    tracked = DailyWorldProjectionService._compact_tracked_state(
        {
            "world_projection_state": {
                "world": {
                    "location_updates": [
                        {
                            "character": f"角色{index}",
                            "location": "花果山" * 128,
                            "region": "东胜神洲" * 128,
                        }
                        for index in range(32)
                    ],
                    "causal_updates": [
                        {
                            "cause": "偷取金箍棒",
                            "expected_consequence": "龙宫追责",
                            "characters": ["孙悟空"],
                        }
                    ],
                }
            }
        }
    )

    signals = detect_world_change_signals("偷取金箍棒引发的后果终于解决。", [], tracked)

    assert signals.requires_nonempty_patch is True
    assert "causal_updates" in signals.categories
