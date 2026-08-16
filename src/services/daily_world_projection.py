"""Durable, lease-fenced worker for daily world projection extraction.

Database work is intentionally short-lived: every state transition runs in a
committed transaction and closes before a provider request begins.  The worker
therefore never keeps a SQLite write lock or SQLAlchemy session while calling a
model provider.
"""

from __future__ import annotations

import logging
import os
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from typing import Any, Callable, Mapping, Optional, Sequence
from zoneinfo import ZoneInfo

from sqlalchemy.exc import OperationalError

from src.database.models import DailyWorldProjection, GameState, SessionLocal
from src.game.world_projection_coverage import detect_world_change_signals
from src.game.world_projection_schema import (
    WorldProjectionExtractionError,
    compute_projection_source_hash,
)
from src.services.daily_world_projection_repository import (
    LEASE_DURATION,
    AttemptReservation,
    AttemptReservationStatus,
    DailyWorldProjectionRepository,
    ProjectionIdentity,
)

logger = logging.getLogger(__name__)

RETRY_DELAYS = (5, 30, 120, 300, 1800, 7200)
MAX_DAILY_MODEL_CALLS = 8
DEFAULT_TIME_ZONE = "Asia/Shanghai"
LOCK_RETRY_ATTEMPTS = 3


class GenerationCancelled(RuntimeError):
    """A guarded post-provider transaction lost the lifecycle race to stop()."""


class DailyWorldProjectionService:
    """Claim due rows and publish extraction results through repository fences."""

    def __init__(
        self,
        *,
        session_factory: Callable[[], Any] = SessionLocal,
        repository_factory: Callable[[Any], Any] = DailyWorldProjectionRepository,
        extractor: Optional[Callable[[str, Sequence[Any], Any], Any]] = None,
        canonical_loader: Optional[
            Callable[[int, str, int], Optional[Mapping[str, Any]]]
        ] = None,
        now_fn: Optional[Callable[[], datetime]] = None,
        wake_event: Optional[Any] = None,
        worker_id: Optional[str] = None,
        scan_seconds: float = 1.0,
        claim_limit: int = 4,
        extraction_workers: int = 2,
        heartbeat_interval: float = 60.0,
        time_zone: Optional[str] = None,
        lock_retry_wait: Optional[Callable[[int], None]] = None,
        after_final_publish_commit: Optional[Callable[[], None]] = None,
    ) -> None:
        self.session_factory = session_factory
        self.repository_factory = repository_factory
        self.extractor = extractor
        self.now_fn = now_fn or (lambda: datetime.now(timezone.utc))
        self.wake_event = wake_event or threading.Event()
        self.worker_id = worker_id or f"daily-world-projection-{uuid.uuid4()}"
        self.scan_seconds = scan_seconds
        self.claim_limit = claim_limit
        self.extraction_workers = extraction_workers
        self.heartbeat_interval = heartbeat_interval
        self.lock_retry_wait = lock_retry_wait or (
            lambda attempt: time.sleep(0.01 * (attempt + 1))
        )
        self.after_final_publish_commit = after_final_publish_commit
        zone_name = time_zone or os.getenv(
            "WORLD_PROJECTION_TIME_ZONE", DEFAULT_TIME_ZONE
        )
        self.time_zone = ZoneInfo(zone_name)
        self._lock = threading.Lock()
        self._scanner: Optional[threading.Thread] = None
        self._pool: Optional[ThreadPoolExecutor] = None
        self._started = False
        self._generation = 0
        self._cancel_event: Optional[threading.Event] = None
        self._heartbeat_done: set[threading.Event] = set()
        self.canonical_loader = canonical_loader or self._load_canonical_source

    @property
    def is_running(self) -> bool:
        with self._lock:
            return self._started

    @staticmethod
    def next_retry_at(attempt_count: int, now: datetime) -> datetime:
        """Legacy-friendly deterministic backoff for a caller-provided clock."""

        if attempt_count <= len(RETRY_DELAYS):
            return now + timedelta(seconds=RETRY_DELAYS[max(0, attempt_count - 1)])
        tomorrow = now.date() + timedelta(days=1)
        return datetime.combine(tomorrow, datetime.min.time(), tzinfo=now.tzinfo)

    def _as_utc_naive(self, value: datetime) -> datetime:
        """Persist DB timestamps as naive UTC, while accepting legacy naive tests."""

        if value.tzinfo is None:
            return value
        return value.astimezone(timezone.utc).replace(tzinfo=None)

    def _as_local(self, value: datetime) -> datetime:
        if value.tzinfo is None:
            # Legacy callers historically supplied local naive values. Production
            # now_fn is aware UTC, so this branch is only compatibility/test input.
            return value.replace(tzinfo=self.time_zone)
        return value.astimezone(self.time_zone)

    def local_day_bounds_utc(self, now: datetime) -> tuple[datetime, datetime]:
        """Return [local midnight, next local midnight) as naive UTC DB bounds."""

        local = self._as_local(now)
        start_local = datetime.combine(
            local.date(), datetime.min.time(), self.time_zone
        )
        end_local = start_local + timedelta(days=1)
        if now.tzinfo is None:
            return start_local.replace(tzinfo=None), end_local.replace(tzinfo=None)
        return self._as_utc_naive(start_local), self._as_utc_naive(end_local)

    def next_local_day(self, now: datetime) -> datetime:
        local = self._as_local(now)
        tomorrow = local.date() + timedelta(days=1)
        target = datetime.combine(tomorrow, datetime.min.time(), self.time_zone)
        return (
            target.replace(tzinfo=None)
            if now.tzinfo is None
            else self._as_utc_naive(target)
        )

    def _next_retry_at(self, attempt_count: int, now: datetime) -> datetime:
        if attempt_count <= len(RETRY_DELAYS):
            return self._as_utc_naive(now) + timedelta(
                seconds=RETRY_DELAYS[max(0, attempt_count - 1)]
            )
        return self.next_local_day(now)

    def _active_generation(
        self, generation: Optional[int], cancel: Optional[Any]
    ) -> bool:
        with self._lock:
            return (
                generation is None or (self._started and generation == self._generation)
            ) and not (cancel is not None and cancel.is_set())

    def start(self) -> None:
        """Start exactly one daemon scanner and a bounded extraction pool."""

        with self._lock:
            if self._started:
                return
            self._generation += 1
            generation = self._generation
            cancel = threading.Event()
            self._cancel_event = cancel
            self._pool = ThreadPoolExecutor(
                max_workers=self.extraction_workers,
                thread_name_prefix="daily-world-projection",
            )
            self._started = True
            self._scanner = threading.Thread(
                target=self._scan_loop,
                args=(generation, cancel),
                name="daily-world-projection-scanner",
                daemon=True,
            )
            self._scanner.start()

    def stop(self, *, wait: bool = False) -> None:
        """Cancel this generation before safely releasing its worker resources."""

        with self._lock:
            if not self._started:
                return
            self._started = False
            cancel, self._cancel_event = self._cancel_event, None
            if cancel is not None:
                cancel.set()
            heartbeat_done = tuple(self._heartbeat_done)
            for done in heartbeat_done:
                done.set()
            self.wake_event.set()
            pool, self._pool = self._pool, None
            scanner, self._scanner = self._scanner, None
        try:
            if pool is not None:
                pool.shutdown(wait=wait, cancel_futures=True)
        except Exception:
            logger.exception("daily world projection pool shutdown failed")
        finally:
            if wait and scanner is not None:
                scanner.join(timeout=1)

    def wake(self) -> None:
        self.wake_event.set()

    def _transaction(
        self,
        callback: Callable[[Any, Any], Any],
        *,
        cancel_guard: Optional[Any] = None,
        after_commit: Optional[Callable[[], None]] = None,
    ) -> Any:
        """Commit one DB transition, optionally linearized against stop()."""

        last_error: Optional[OperationalError] = None
        for attempt in range(LOCK_RETRY_ATTEMPTS):
            session = self.session_factory()
            try:
                result = callback(session, self.repository_factory(session))
                if cancel_guard is None:
                    session.commit()
                else:
                    # stop() sets its generation cancel event under this same
                    # lifecycle lock.  This makes "cancel check + commit" one
                    # linearizable decision rather than a check-then-commit race.
                    with self._lock:
                        if cancel_guard.is_set():
                            raise GenerationCancelled()
                        session.commit()
                if after_commit is not None:
                    after_commit()
                return result
            except GenerationCancelled:
                session.rollback()
                raise
            except OperationalError as exc:
                session.rollback()
                last_error = exc
                if (
                    "locked" not in str(exc).lower()
                    or attempt + 1 == LOCK_RETRY_ATTEMPTS
                ):
                    raise
                self.lock_retry_wait(attempt)
            except Exception:
                session.rollback()
                raise
            finally:
                session.close()
        assert last_error is not None
        raise last_error

    def ensure_world_projection(
        self, identity_or_game_id: Any, story_or_event: Any, options_or_state: Any
    ) -> Any:
        """Persist an idempotent row without starting a model or worker."""

        if isinstance(identity_or_game_id, ProjectionIdentity):
            identity = identity_or_game_id
            story = str(story_or_event)
            options = options_or_state
        else:
            game_id = int(identity_or_game_id)
            event, player_state = story_or_event, options_or_state

            def field(value: Any, name: str, default: Any = None) -> Any:
                if isinstance(value, Mapping):
                    return value.get(name, default)
                return getattr(value, name, default)

            timeline = field(player_state, "timeline", {}) or {}
            event_id = field(event, "event_id")
            revision = field(event, "revision", 1)
            if not event_id or int(revision) < 1:
                raise ValueError("invalid_daily_world_projection_event")
            identity = ProjectionIdentity(
                game_id=game_id,
                event_id=str(event_id),
                revision=int(revision),
                day_index=int(
                    field(timeline, "day_index", field(player_state, "day_index", 0))
                ),
                story_date=field(event, "story_date", field(timeline, "current_date")),
            )
            story = str(field(event, "event_description", field(event, "story", "")))
            options = field(event, "options", [])
        source_hash = compute_projection_source_hash(story, options)
        return self._transaction(
            lambda _session, repo: repo.ensure_projection(identity, source_hash)
        )

    def run_once(
        self,
        now: Optional[datetime] = None,
        *,
        _generation: Optional[int] = None,
        _cancel: Optional[Any] = None,
    ) -> int:
        """Commit claims, then process only the active generation's rows."""

        if not self._active_generation(_generation, _cancel):
            return 0
        clock_now = now or self.now_fn()
        db_now = self._as_utc_naive(clock_now)
        claimed_ids = self._transaction(
            lambda _session, repo: [
                int(row.projection_id)
                for row in repo.claim_due(
                    now=db_now, worker_id=self.worker_id, limit=self.claim_limit
                )
            ]
        )
        pool = self._pool
        for projection_id in claimed_ids:
            if not self._active_generation(_generation, _cancel):
                break
            if pool is None:
                self._process_claim(projection_id, clock_now, _cancel)
            else:
                try:
                    pool.submit(self._process_claim, projection_id, clock_now, _cancel)
                except RuntimeError:
                    break
        return len(claimed_ids)

    def _scan_loop(self, generation: int, cancel: threading.Event) -> None:
        while self._active_generation(generation, cancel):
            try:
                self.run_once(self.now_fn(), _generation=generation, _cancel=cancel)
            except Exception:
                logger.exception("daily world projection scan failed")
            if cancel.is_set():
                return
            self.wake_event.wait(self.scan_seconds)
            self.wake_event.clear()

    def _load_canonical_source(
        self, game_id: int, event_id: str, revision: int
    ) -> Optional[Mapping[str, Any]]:
        """Read one accepted event in a short committed transaction."""

        def load(session: Any, _repo: Any) -> Optional[Mapping[str, Any]]:
            state = (
                session.query(GameState)
                .filter(GameState.game_id == game_id)
                .order_by(GameState.created_at.desc())
                .first()
            )
            data = getattr(state, "state_json", None)
            if not isinstance(data, Mapping):
                return None
            candidates = [data.get("current_event_data")]
            candidates.extend(reversed(data.get("day_history") or []))
            for event in candidates:
                if not isinstance(event, Mapping) or event.get("event_id") != event_id:
                    continue
                if int(event.get("revision") or 1) != revision:
                    continue
                story = event.get("event_description", event.get("story", ""))
                options = event.get("options")
                if isinstance(story, str) and isinstance(options, list):
                    return {
                        "revision": revision,
                        "story": story,
                        "options": options,
                        "tracked_state": dict(data),
                    }
            return None

        return self._transaction(load)

    def _validated_canonical_source(
        self, row: Any
    ) -> tuple[Optional[Mapping[str, Any]], Optional[str]]:
        source = self.canonical_loader(row.game_id, row.event_id, row.revision)
        if not source or int(source.get("revision", row.revision)) != row.revision:
            return None, "source_superseded"
        story, options = str(source.get("story", "")), list(source.get("options", []))
        if compute_projection_source_hash(story, options) != row.source_hash:
            return None, "source_hash_mismatch"
        return source, None

    def _claimed_snapshot(self, projection_id: int) -> Optional[Any]:
        def read(session: Any, _repo: Any) -> Optional[Any]:
            row = session.get(DailyWorldProjection, projection_id)
            if (
                row is None
                or row.lease_owner != self.worker_id
                or row.status != "running"
            ):
                return None
            return SimpleNamespace(
                projection_id=row.projection_id,
                game_id=row.game_id,
                event_id=row.event_id,
                revision=row.revision,
                source_hash=row.source_hash,
                attempt_count=row.attempt_count,
            )

        return self._transaction(read)

    def _renew_lease(
        self,
        projection_id: int,
        source_hash: str,
        now: datetime,
        cancel: Optional[Any] = None,
        guard_commit: bool = False,
    ) -> bool:
        if cancel is not None and cancel.is_set():
            if guard_commit:
                raise GenerationCancelled()
            return False
        db_now = self._as_utc_naive(now)
        return bool(
            self._transaction(
                lambda _session, repo: (
                    False
                    if cancel is not None and cancel.is_set()
                    else repo.renew_lease(
                        projection_id,
                        self.worker_id,
                        db_now,
                        db_now + LEASE_DURATION,
                        source_hash=source_hash,
                    )
                ),
                cancel_guard=cancel if guard_commit else None,
            )
        )

    def _lease_heartbeat(
        self,
        projection_id: int,
        source_hash: str,
        done: threading.Event,
        cancel: Optional[Any] = None,
    ) -> None:
        """Renew with independent committed sessions until extraction completes."""

        try:
            while not done.wait(self.heartbeat_interval):
                if (cancel is not None and cancel.is_set()) or not self._renew_lease(
                    projection_id, source_hash, self.now_fn(), cancel
                ):
                    return
        finally:
            with self._lock:
                self._heartbeat_done.discard(done)

    @staticmethod
    def _coverage_mapping(coverage: Any) -> Mapping[str, Any]:
        return {
            "requires_nonempty_patch": bool(coverage.requires_nonempty_patch),
            "categories": list(coverage.categories),
            "matched_spans": list(coverage.matched_spans),
        }

    def _retry(
        self,
        row: Any,
        now: datetime,
        error_code: str,
        cancel: Optional[Any] = None,
        guard_commit: bool = False,
    ) -> bool:
        if cancel is not None and cancel.is_set():
            if guard_commit:
                raise GenerationCancelled()
            return False
        return bool(
            self._transaction(
                lambda _session, repo: (
                    False
                    if cancel is not None and cancel.is_set()
                    else repo.mark_retryable(
                        row.projection_id,
                        self.worker_id,
                        error_code,
                        self._next_retry_at(row.attempt_count, now),
                        source_hash=row.source_hash,
                    )
                ),
                cancel_guard=cancel if guard_commit else None,
            )
        )

    def _defer_for_daily_cap(
        self, row: Any, now: datetime, cancel: Optional[Any] = None
    ) -> bool:
        if cancel is not None and cancel.is_set():
            return False
        return bool(
            self._transaction(
                lambda _session, repo: (
                    False
                    if cancel is not None and cancel.is_set()
                    else repo.mark_retryable(
                        row.projection_id,
                        self.worker_id,
                        "daily_call_cap",
                        self.next_local_day(now),
                        source_hash=row.source_hash,
                    )
                )
            )
        )

    def _reserve_attempt(self, row: Any, now: datetime) -> AttemptReservation:
        start, end = self.local_day_bounds_utc(now)
        db_now = self._as_utc_naive(now)

        def reserve(_session: Any, repo: Any) -> AttemptReservation:
            method = getattr(repo, "reserve_attempt_slot", None)
            if method is not None:
                return method(
                    row.projection_id,
                    row.game_id,
                    start,
                    end,
                    db_now,
                    max_attempts=MAX_DAILY_MODEL_CALLS,
                    worker_id=self.worker_id,
                    source_hash=row.source_hash,
                    lease_until=db_now + LEASE_DURATION,
                )
            # Compatibility only for injected test repositories predating Task 3.
            if (
                repo.count_game_attempts_between(row.game_id, start, end)
                >= MAX_DAILY_MODEL_CALLS
            ):
                return AttemptReservation(AttemptReservationStatus.DAILY_CAP)
            attempt_id = repo.start_attempt(row.projection_id, row.game_id, db_now)
            return AttemptReservation(
                AttemptReservationStatus.RESERVED,
                attempt_id=attempt_id,
                attempt_count=row.attempt_count,
            )

        return self._transaction(reserve)

    def _release_attempt_reservation(self, row: Any, attempt_id: int) -> bool:
        def release(_session: Any, repo: Any) -> bool:
            method = getattr(repo, "release_attempt_reservation", None)
            if method is None:
                return False
            return bool(
                method(
                    row.projection_id,
                    attempt_id,
                    self.worker_id,
                    row.source_hash,
                )
            )

        return bool(self._transaction(release))

    def _finish_attempt(
        self, attempt_id: int, outcome: str, error_code: Optional[str], now: datetime
    ) -> None:
        self._transaction(
            lambda _session, repo: repo.finish_attempt(
                attempt_id, outcome, error_code, self._as_utc_naive(now)
            )
        )

    def _extract(self, story: str, options: Sequence[Any], tracked_state: Any) -> Any:
        """Construct the model facade only after all DB sessions are closed."""

        if self.extractor is not None:
            return self.extractor(story, options, tracked_state)
        from src.ai.generator import EventGenerator

        return EventGenerator().extract_daily_world_projection(
            story, list(options), tracked_state
        )

    def _process_claim(
        self, projection_id: int, now: datetime, cancel: Optional[Any] = None
    ) -> None:
        """Extract one claim; every provider call's reservation is finished finally."""

        row = self._claimed_snapshot(projection_id)
        if row is None or (cancel is not None and cancel.is_set()):
            return
        attempt_id: Optional[int] = None
        provider_called = False
        outcome, error_code = "unexpected_error", "unexpected_error"
        done = threading.Event()
        heartbeat: Optional[threading.Thread] = None
        try:
            source, source_error = self._validated_canonical_source(row)
            if source is None:
                assert source_error is not None
                self._retry(row, now, source_error, cancel)
                outcome, error_code = source_error, source_error
                return
            if cancel is not None and cancel.is_set():
                return
            story, options = str(source.get("story", "")), list(
                source.get("options", [])
            )
            reservation = self._reserve_attempt(row, now)
            if reservation.status == AttemptReservationStatus.DAILY_CAP:
                self._defer_for_daily_cap(row, now, cancel)
                outcome, error_code = "daily_call_cap", "daily_call_cap"
                return
            if reservation.status == AttemptReservationStatus.FENCED:
                outcome, error_code = "fenced", "fenced"
                return
            assert reservation.attempt_id is not None
            assert reservation.attempt_count is not None
            attempt_id = reservation.attempt_id
            row.attempt_count = reservation.attempt_count
            if cancel is not None and cancel.is_set():
                self._release_attempt_reservation(row, attempt_id)
                attempt_id = None
                return
            with self._lock:
                self._heartbeat_done.add(done)
            heartbeat = threading.Thread(
                target=self._lease_heartbeat,
                args=(projection_id, row.source_hash, done, cancel),
                name="daily-world-projection-heartbeat",
                daemon=True,
            )
            heartbeat.start()
            if cancel is not None and cancel.is_set():
                self._release_attempt_reservation(row, attempt_id)
                attempt_id = None
                return
            provider_called = True
            payload = self._extract(story, options, source.get("tracked_state"))
            done.set()
            if cancel is not None and cancel.is_set():
                outcome, error_code = "cancelled", "cancelled"
                return
            if not self._renew_lease(
                projection_id,
                row.source_hash,
                self.now_fn(),
                cancel,
                guard_commit=True,
            ):
                outcome, error_code = "lease_lost", "lease_lost"
                return
            if cancel is not None and cancel.is_set():
                outcome, error_code = "cancelled", "cancelled"
                return
            latest_source, source_error = self._validated_canonical_source(row)
            if latest_source is None:
                assert source_error is not None
                self._retry(row, now, source_error, cancel, guard_commit=True)
                outcome, error_code = source_error, source_error
                return
            if cancel is not None and cancel.is_set():
                outcome, error_code = "cancelled", "cancelled"
                return
            coverage = self._coverage_mapping(
                detect_world_change_signals(story, options, source.get("tracked_state"))
            )
            published = self._transaction(
                lambda _session, repo: repo.mark_ready(
                    row.projection_id,
                    self.worker_id,
                    row.source_hash,
                    payload,
                    bool(getattr(payload, "no_change", False)),
                    coverage=coverage,
                ),
                cancel_guard=cancel,
                after_commit=self.after_final_publish_commit,
            )
            outcome, error_code = (
                ("success", None) if published else ("lease_lost", "lease_lost")
            )
        except GenerationCancelled:
            if provider_called:
                outcome, error_code = "cancelled", "cancelled"
            else:
                raise
        except WorldProjectionExtractionError as exc:
            error_code = exc.code
            if cancel is not None and cancel.is_set() and provider_called:
                outcome, error_code = "cancelled", "cancelled"
            else:
                self._retry(row, now, error_code, cancel, guard_commit=provider_called)
                outcome = "extraction_error"
        except Exception:
            logger.exception(
                "daily world projection extraction failed projection_id=%s",
                projection_id,
            )
            if cancel is not None and cancel.is_set() and provider_called:
                outcome, error_code = "cancelled", "cancelled"
            else:
                self._retry(
                    row,
                    now,
                    "unexpected_error",
                    cancel,
                    guard_commit=provider_called,
                )
        finally:
            done.set()
            if heartbeat is not None:
                heartbeat.join(timeout=0)
            with self._lock:
                self._heartbeat_done.discard(done)
            if attempt_id is not None:
                self._finish_attempt(
                    attempt_id,
                    outcome,
                    error_code,
                    self.now_fn(),
                )


_service: Optional[DailyWorldProjectionService] = None
_service_lock = threading.Lock()


def get_daily_world_projection_service() -> DailyWorldProjectionService:
    """Lazily construct the process singleton after startup enables the flag."""

    global _service
    with _service_lock:
        if _service is None:
            _service = DailyWorldProjectionService()
        return _service
