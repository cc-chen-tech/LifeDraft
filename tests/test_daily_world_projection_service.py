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


def test_transaction_helper_commits_success_and_rolls_back_failure() -> None:
    from src.services.daily_world_projection import DailyWorldProjectionService

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


def test_stop_before_heartbeat_releases_pre_provider_reservation_lease(
    tmp_path,
) -> None:
    """Cancel after a committed slot leaves no ledger, count, or stale lease."""
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

    reserved, release_worker = threading.Event(), threading.Event()
    service = DailyWorldProjectionService(
        session_factory=sessions,
        extractor=lambda *_args: pytest.fail("provider must not be called"),
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
        assert stored.attempt_count == 0
        assert session.query(DailyWorldProjectionAttempt).count() == 0
        [claimed] = DailyWorldProjectionRepository(session).claim_due(
            now, "new-worker", 1
        )
        assert claimed.lease_owner == "new-worker"
        assert claimed.source_hash == source_hash
