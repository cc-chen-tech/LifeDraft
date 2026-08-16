"""Durable, lease-fenced worker for daily world projection extraction.

Database work is intentionally short-lived: every state transition runs in a
committed transaction and closes before a provider request begins.  The worker
therefore never keeps a SQLite write lock or SQLAlchemy session while calling a
model provider.
"""

from __future__ import annotations

import hashlib
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

from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from src.database.models import DailyWorldProjection, Game, GameState, SessionLocal
from src.game.world_projection_coverage import detect_world_change_signals
from src.game.world_projection_schema import (
    WorldProjectionExtractionError,
    compute_projection_source_hash,
)
from src.game.world_projection_state import (
    apply_contiguous_world_projections,
    projection_row_snapshot,
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
MAX_LEASE_OWNER_BYTES = 96
_GENERATION_OWNER_SUFFIX_BYTES = 43
_BASE_OWNER_SUFFIX_BYTES = 18


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
        before_guarded_commit: Optional[Callable[[], None]] = None,
        before_lease_commit: Optional[Callable[[], None]] = None,
        before_claim_guard: Optional[Callable[[], None]] = None,
        before_claim_commit: Optional[Callable[[], None]] = None,
        before_reservation_guard: Optional[Callable[[], None]] = None,
        before_projection_state_save: Optional[Callable[[], None]] = None,
    ) -> None:
        self.session_factory = session_factory
        self.repository_factory = repository_factory
        self.extractor = extractor
        self.now_fn = now_fn or (lambda: datetime.now(timezone.utc))
        self.wake_event = wake_event or threading.Event()
        self.worker_id = self._base_owner(
            worker_id or f"daily-world-projection-{uuid.uuid4()}"
        )
        self.scan_seconds = scan_seconds
        self.claim_limit = claim_limit
        self.extraction_workers = extraction_workers
        self.heartbeat_interval = heartbeat_interval
        self.lock_retry_wait = lock_retry_wait or (
            lambda attempt: time.sleep(0.01 * (attempt + 1))
        )
        self.after_final_publish_commit = after_final_publish_commit
        self.before_guarded_commit = before_guarded_commit
        self.before_lease_commit = before_lease_commit
        self.before_claim_guard = before_claim_guard
        self.before_claim_commit = before_claim_commit
        self.before_reservation_guard = before_reservation_guard
        self.before_projection_state_save = before_projection_state_save
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
        self._generation_owners: dict[int, str] = {}
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

    def _owner_for(self, cancel: Optional[Any] = None) -> str:
        if cancel is None:
            return self.worker_id
        with self._lock:
            return self._generation_owners.get(id(cancel), self.worker_id)

    @staticmethod
    def _utf8_prefix(value: str, byte_limit: int) -> str:
        return value.encode("utf-8")[:byte_limit].decode("utf-8", errors="ignore")

    @classmethod
    def _base_owner(cls, worker_id: str) -> str:
        """Normalize direct-run owners to the persisted lease-owner limit."""

        encoded = worker_id.encode("utf-8")
        if len(encoded) <= MAX_LEASE_OWNER_BYTES:
            return worker_id
        suffix = f":b{hashlib.blake2s(encoded, digest_size=8).hexdigest()}"
        assert len(suffix.encode("utf-8")) == _BASE_OWNER_SUFFIX_BYTES
        return f"{cls._utf8_prefix(worker_id, MAX_LEASE_OWNER_BYTES - len(suffix))}{suffix}"

    def _generation_owner(self, generation: int) -> str:
        """Return a unique, diagnosable owner token that fits lease_owner."""

        generation_digest = hashlib.blake2s(
            str(generation).encode("ascii"), digest_size=4
        ).hexdigest()
        suffix = f":g{generation_digest}:{uuid.uuid4().hex}"
        assert len(suffix.encode("utf-8")) == _GENERATION_OWNER_SUFFIX_BYTES
        prefix_budget = MAX_LEASE_OWNER_BYTES - _GENERATION_OWNER_SUFFIX_BYTES
        prefix = self._utf8_prefix(self.worker_id, prefix_budget)
        return f"{prefix}{suffix}"

    def start(self) -> None:
        """Start exactly one daemon scanner and a bounded extraction pool."""

        with self._lock:
            if self._started:
                return
            self._generation += 1
            generation = self._generation
            cancel = threading.Event()
            self._cancel_event = cancel
            self._generation_owners[id(cancel)] = self._generation_owner(generation)
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

    def lookup_choice_projection(
        self,
        *,
        event_id: str,
        revision: int,
        day_index: int,
        source_hash: str,
    ) -> Optional[Any]:
        """Return one fully fenced row using only a short database read."""

        def lookup(session: Any, _repo: Any) -> Optional[Any]:
            rows = (
                session.query(DailyWorldProjection)
                .filter(
                    DailyWorldProjection.event_id == event_id,
                    DailyWorldProjection.revision == revision,
                    DailyWorldProjection.day_index == day_index,
                    DailyWorldProjection.source_hash == source_hash,
                    DailyWorldProjection.status != "superseded",
                )
                .limit(2)
                .all()
            )
            if len(rows) != 1:
                return None
            return projection_row_snapshot(rows[0])

        return self._transaction(lookup)

    @staticmethod
    def _lock_projection_game(session: Any, game_id: int) -> Optional[Game]:
        bind = session.get_bind()
        if bind.dialect.name == "sqlite":
            updated = session.execute(
                text(
                    "UPDATE games SET updated_at = updated_at WHERE game_id = :game_id"
                ),
                {"game_id": game_id},
            )
            if updated.rowcount != 1:
                return None
            return session.get(Game, game_id)
        return (
            session.query(Game)
            .filter(Game.game_id == game_id)
            .with_for_update()
            .one_or_none()
        )

    def _apply_and_save_contiguous(
        self, session: Any, game_id: int
    ) -> tuple[int, list[tuple[int, str]]]:
        game = self._lock_projection_game(session, game_id)
        if game is None:
            return 0, []
        latest = (
            session.query(GameState)
            .filter(GameState.game_id == game_id)
            .order_by(GameState.state_id.desc())
            .first()
        )
        state_data = latest.state_json if latest is not None else game.initial_state
        if not isinstance(state_data, Mapping):
            return 0, []

        from src.game.state import PlayerState

        state = PlayerState.from_dict(dict(state_data))
        rows = [
            projection_row_snapshot(row)
            for row in (
                session.query(DailyWorldProjection)
                .filter(DailyWorldProjection.game_id == game_id)
                .order_by(
                    DailyWorldProjection.day_index,
                    DailyWorldProjection.revision.desc(),
                    DailyWorldProjection.projection_id,
                )
                .all()
            )
        ]
        batch = apply_contiguous_world_projections(state, rows)
        if not batch.state_changed:
            return batch.applied_count, list(batch.rows_to_mark)

        expected_state_id = int(latest.state_id) if latest is not None else None
        current_state_id = (
            session.query(GameState.state_id)
            .filter(GameState.game_id == game_id)
            .order_by(GameState.state_id.desc())
            .limit(1)
            .scalar()
        )
        if current_state_id != expected_state_id:
            raise OperationalError(
                "daily_world_projection_state_cas_conflict", {}, None
            )
        if self.before_projection_state_save is not None:
            self.before_projection_state_save()
        session.add(
            GameState(
                game_id=game_id,
                week=state.week,
                age=state.age,
                state_json=state.to_dict(),
            )
        )
        game.updated_at = self._as_utc_naive(self.now_fn())
        session.flush()
        return batch.applied_count, list(batch.rows_to_mark)

    def apply_ready_for_game(self, game_id: int) -> int:
        """Apply only the contiguous settled-day prefix, then mark rows applied."""

        from src.api.routers.gameplay.sse_helpers import _get_game_state_lock

        with _get_game_state_lock(game_id):
            applied_count, rows_to_mark = self._transaction(
                lambda session, _repo: self._apply_and_save_contiguous(session, game_id)
            )
            applied_at = self._as_utc_naive(self.now_fn())
            for projection_id, source_hash in rows_to_mark:
                self._transaction(
                    lambda _session, repo, projection_id=projection_id, source_hash=source_hash: repo.mark_applied(
                        projection_id, source_hash, applied_at
                    )
                )
            return applied_count

    def schedule_apply_for_game(self, game_id: int) -> None:
        """Start a model-free best-effort apply after choice durability."""

        def apply() -> None:
            try:
                self.apply_ready_for_game(game_id)
            except Exception:
                logger.exception(
                    "daily world projection post-choice apply failed game_id=%s",
                    game_id,
                )

        threading.Thread(
            target=apply,
            name=f"daily-world-projection-apply-{game_id}",
            daemon=True,
        ).start()

    def _recover_ready_projection_states(self) -> None:
        """Replay durable ready rows left by a crash or failed final marker."""

        def ready_games(session: Any, _repo: Any) -> list[int]:
            # Task 3's injected FakeSession intentionally models only worker
            # lifecycle calls. Production sessions always provide query().
            if not hasattr(session, "query"):
                return []
            return [
                int(row.game_id)
                for row in (
                    session.query(DailyWorldProjection.game_id)
                    .filter(
                        DailyWorldProjection.status.in_(("ready", "ready_no_change"))
                    )
                    .distinct()
                    .all()
                )
            ]

        for game_id in self._transaction(ready_games):
            try:
                self.apply_ready_for_game(game_id)
            except Exception:
                logger.exception(
                    "daily world projection ready replay failed game_id=%s", game_id
                )

    def _transaction(
        self,
        callback: Callable[[Any, Any], Any],
        *,
        cancel_guard: Optional[Any] = None,
        after_commit: Optional[Callable[[], None]] = None,
        before_commit: Optional[Callable[[], None]] = None,
        before_guard: Optional[Callable[[], None]] = None,
    ) -> Any:
        """Commit one DB transition, optionally linearized against stop()."""

        last_error: Optional[OperationalError] = None
        for attempt in range(LOCK_RETRY_ATTEMPTS):
            session = self.session_factory()
            try:

                def commit_boundary() -> None:
                    if cancel_guard is None:
                        if before_commit is not None:
                            before_commit()
                        return
                    # stop() sets its generation cancel event under this same
                    # lifecycle lock.  This makes "cancel check + commit" one
                    # linearizable decision rather than a check-then-commit race.
                    if before_guard is not None:
                        before_guard()
                    with self._lock:
                        if cancel_guard.is_set():
                            raise GenerationCancelled()
                    # Permit is the commit's lifecycle linearization point.
                    # Do not hold the lifecycle lock across a potentially slow
                    # SQLite commit: stop() can cancel a later generation
                    # immediately while this already-permitted commit finishes.
                    if self.before_guarded_commit is not None:
                        self.before_guarded_commit()
                    if before_commit is not None:
                        before_commit()

                begin = getattr(session, "begin", None)
                if callable(begin):
                    # SQLite releases a top-level SAVEPOINT as a commit when no
                    # explicit outer transaction exists. Repositories use
                    # begin_nested() for uniqueness races, so establish the
                    # outer boundary before their callbacks can create one.
                    with begin():
                        connection = session.connection()
                        if connection.dialect.name == "sqlite":
                            connection.exec_driver_sql("BEGIN")
                        result = callback(session, self.repository_factory(session))
                        commit_boundary()
                else:
                    # Task 3's lightweight FakeSession has no begin() API.
                    result = callback(session, self.repository_factory(session))
                    commit_boundary()
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

        identity, source_hash = self._projection_identity_and_source(
            identity_or_game_id, story_or_event, options_or_state
        )
        return self._transaction(
            lambda _session, repo: repo.ensure_projection(identity, source_hash)
        )

    def ensure_replacement_world_projection(
        self, game_id: int, event: Any, player_state: Any
    ) -> Any:
        """Persist a replacement row and fence every older revision atomically."""

        identity, source_hash = self._projection_identity_and_source(
            game_id, event, player_state
        )

        def ensure_and_supersede(_session: Any, repo: Any) -> Any:
            self._lock_replacement_game(_session, identity.game_id)
            projection = repo.ensure_projection(identity, source_hash)
            repo.supersede(
                identity.game_id, identity.event_id, before_revision=identity.revision
            )
            newer_exists = (
                _session.query(DailyWorldProjection)
                .filter(
                    DailyWorldProjection.game_id == identity.game_id,
                    DailyWorldProjection.event_id == identity.event_id,
                    DailyWorldProjection.revision > identity.revision,
                )
                .first()
                is not None
            )
            if newer_exists:
                repo.supersede(
                    identity.game_id,
                    identity.event_id,
                    before_revision=identity.revision + 1,
                )
            return projection

        return self._transaction(ensure_and_supersede)

    @staticmethod
    def _lock_replacement_game(session: Any, game_id: int) -> None:
        """Serialize replacement callbacks for one game before inspecting revisions."""

        bind = session.get_bind()
        if bind.dialect.name == "sqlite":
            # SQLite has no FOR UPDATE. A no-op row update acquires its writer
            # lock before the nested projection savepoint can be released.
            session.execute(
                text(
                    "UPDATE games SET updated_at = updated_at WHERE game_id = :game_id"
                ),
                {"game_id": game_id},
            )
            return
        session.query(Game).filter(Game.game_id == game_id).with_for_update().one()

    @staticmethod
    def _projection_identity_and_source(
        identity_or_game_id: Any, story_or_event: Any, options_or_state: Any
    ) -> tuple[ProjectionIdentity, str]:
        """Normalize the frozen enqueue arguments without starting a worker."""

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
                    field(
                        event,
                        "day_index",
                        field(
                            timeline, "day_index", field(player_state, "day_index", 0)
                        ),
                    )
                ),
                story_date=field(event, "story_date", field(timeline, "current_date")),
            )
            story = str(field(event, "event_description", field(event, "story", "")))
            options = field(event, "options", [])
        source_hash = compute_projection_source_hash(story, options)
        return identity, source_hash

    def _release_claims(
        self, claims: Sequence[tuple[int, str]], owner: str, now: datetime
    ) -> None:
        """Release only leases still owned by this stale generation/source."""

        for projection_id, source_hash in claims:
            try:
                self._release_lease(projection_id, source_hash, owner, now)
            except Exception:
                logger.exception(
                    "daily_world_projection_claim_release_failed "
                    "projection_id=%s source_hash=%s",
                    projection_id,
                    source_hash,
                )

    def _release_claim_async(
        self, claim: tuple[int, str], owner: str, now: datetime
    ) -> None:
        threading.Thread(
            target=self._release_claims,
            args=([claim], owner, now),
            name="daily-world-projection-claim-release",
            daemon=True,
        ).start()

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
        owner = self._owner_for(_cancel)
        try:
            claims = self._transaction(
                lambda _session, repo: [
                    (int(row.projection_id), str(row.source_hash))
                    for row in repo.claim_due(
                        now=db_now, worker_id=owner, limit=self.claim_limit
                    )
                ],
                cancel_guard=_cancel,
                before_guard=(self.before_claim_guard if _cancel is not None else None),
                before_commit=(
                    self.before_claim_commit if _cancel is not None else None
                ),
            )
        except GenerationCancelled:
            return 0
        if not self._active_generation(_generation, _cancel):
            self._release_claims(claims, owner, db_now)
            return 0
        pool = self._pool
        for index, (projection_id, source_hash) in enumerate(claims):
            if not self._active_generation(_generation, _cancel):
                self._release_claims(claims[index:], owner, db_now)
                break
            if pool is None:
                self._process_claim(projection_id, clock_now, _cancel)
            else:
                try:
                    future = pool.submit(
                        self._process_claim, projection_id, clock_now, _cancel
                    )
                    future.add_done_callback(
                        lambda completed, claim=(projection_id, source_hash): (
                            self._release_claim_async(claim, owner, db_now)
                            if completed.cancelled()
                            else None
                        )
                    )
                except RuntimeError:
                    self._release_claims(claims[index:], owner, db_now)
                    break
        self._recover_ready_projection_states()
        return len(claims)

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

    def _claimed_snapshot(self, projection_id: int, owner: str) -> Optional[Any]:
        def read(session: Any, _repo: Any) -> Optional[Any]:
            row = session.get(DailyWorldProjection, projection_id)
            if row is None or row.lease_owner != owner or row.status != "running":
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
        owner: str,
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
                        owner,
                        db_now,
                        db_now + LEASE_DURATION,
                        source_hash=source_hash,
                    )
                ),
                cancel_guard=cancel if guard_commit else None,
                before_commit=self.before_lease_commit,
            )
        )

    def _lease_heartbeat(
        self,
        projection_id: int,
        source_hash: str,
        done: threading.Event,
        owner: Optional[str] = None,
        cancel: Optional[Any] = None,
    ) -> None:
        """Renew with independent committed sessions until extraction completes."""

        try:
            while not done.wait(self.heartbeat_interval):
                if (cancel is not None and cancel.is_set()) or not self._renew_lease(
                    projection_id,
                    source_hash,
                    self.now_fn(),
                    owner or self._owner_for(cancel),
                    cancel,
                ):
                    return
        finally:
            if cancel is not None and cancel.is_set():
                try:
                    self._release_lease(
                        projection_id,
                        source_hash,
                        owner or self._owner_for(cancel),
                        self.now_fn(),
                    )
                except Exception:
                    # _transaction already gives lock errors a bounded retry;
                    # a final failure must not leak out of this daemon thread.
                    logger.exception(
                        "daily_world_projection_lease_release_failed "
                        "projection_id=%s source_hash=%s; lease will expire naturally",
                        projection_id,
                        source_hash,
                    )
            with self._lock:
                self._heartbeat_done.discard(done)

    def _release_lease(
        self, projection_id: int, source_hash: str, owner: str, now: datetime
    ) -> bool:
        """Compensate a stopped generation without touching a newer owner."""

        db_now = self._as_utc_naive(now)
        return bool(
            self._transaction(
                lambda _session, repo: repo.release_lease(
                    projection_id,
                    owner,
                    db_now,
                    source_hash=source_hash,
                )
            )
        )

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
        owner: str,
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
                        owner,
                        error_code,
                        self._next_retry_at(row.attempt_count, now),
                        source_hash=row.source_hash,
                    )
                ),
                cancel_guard=cancel if guard_commit else None,
            )
        )

    def _defer_for_daily_cap(
        self, row: Any, now: datetime, owner: str, cancel: Optional[Any] = None
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
                        owner,
                        "daily_call_cap",
                        self.next_local_day(now),
                        source_hash=row.source_hash,
                    )
                )
            )
        )

    def _reserve_attempt(
        self,
        row: Any,
        now: datetime,
        owner: Optional[str] = None,
        cancel: Optional[Any] = None,
    ) -> AttemptReservation:
        owner = owner or self.worker_id
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
                    worker_id=owner,
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

        return self._transaction(
            reserve,
            cancel_guard=cancel,
            before_guard=(
                self.before_reservation_guard if cancel is not None else None
            ),
        )

    def _release_attempt_reservation(
        self, row: Any, attempt_id: int, owner: str, now: datetime
    ) -> bool:
        def release(_session: Any, repo: Any) -> bool:
            method = getattr(repo, "release_attempt_reservation", None)
            if method is None:
                return False
            return bool(
                method(
                    row.projection_id,
                    attempt_id,
                    owner,
                    row.source_hash,
                    self._as_utc_naive(now),
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

    def _publish_and_finish_attempt(
        self,
        repo: Any,
        row: Any,
        owner: str,
        payload: Any,
        coverage: Mapping[str, Any],
        attempt_id: Optional[int],
    ) -> tuple[bool, bool]:
        """Use the atomic repository transition when the provider slot exists."""

        method = getattr(repo, "mark_ready_and_finish_attempt", None)
        if method is not None and attempt_id is not None:
            return (
                bool(
                    method(
                        row.projection_id,
                        owner,
                        row.source_hash,
                        payload,
                        bool(getattr(payload, "no_change", False)),
                        coverage=coverage,
                        attempt_id=attempt_id,
                        now=self._as_utc_naive(self.now_fn()),
                    )
                ),
                True,
            )
        return (
            bool(
                repo.mark_ready(
                    row.projection_id,
                    owner,
                    row.source_hash,
                    payload,
                    bool(getattr(payload, "no_change", False)),
                    coverage=coverage,
                )
            ),
            False,
        )

    def _retry_and_finish_attempt(
        self,
        row: Any,
        now: datetime,
        error_code: str,
        outcome: str,
        owner: str,
        attempt_id: Optional[int],
        cancel: Optional[Any],
    ) -> bool:
        """Atomically schedule a provider failure retry and close its ledger."""

        if attempt_id is None:
            return False

        def retry(session: Any, repo: Any) -> tuple[bool, bool]:
            method = getattr(repo, "mark_retryable_and_finish_attempt", None)
            if method is not None:
                return (
                    bool(
                        method(
                            row.projection_id,
                            owner,
                            error_code,
                            self._next_retry_at(row.attempt_count, now),
                            source_hash=row.source_hash,
                            attempt_id=attempt_id,
                            outcome=outcome,
                            now=self._as_utc_naive(self.now_fn()),
                        )
                    ),
                    True,
                )
            return (
                bool(
                    repo.mark_retryable(
                        row.projection_id,
                        owner,
                        error_code,
                        self._next_retry_at(row.attempt_count, now),
                        source_hash=row.source_hash,
                    )
                ),
                False,
            )

        _retried, finalized = self._transaction(
            retry, cancel_guard=cancel if cancel is not None else None
        )
        return finalized

    def _cancel_and_finish_attempt(
        self, row: Any, owner: str, attempt_id: int, now: datetime
    ) -> bool:
        """Atomically close a cancelled provider call and release its lease."""

        def cancel_attempt(_session: Any, repo: Any) -> bool:
            method = getattr(repo, "release_lease_and_finish_attempt", None)
            if method is None:
                return False
            return bool(
                method(
                    row.projection_id,
                    owner,
                    row.source_hash,
                    self._as_utc_naive(now),
                    attempt_id=attempt_id,
                    outcome="cancelled",
                    error_code="cancelled",
                )
            )

        return bool(self._transaction(cancel_attempt))

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

        owner = self._owner_for(cancel)
        row = self._claimed_snapshot(projection_id, owner)
        if row is None:
            return
        if cancel is not None and cancel.is_set():
            self._release_claims(
                [(projection_id, row.source_hash)], owner, self._as_utc_naive(now)
            )
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
                self._retry(row, now, source_error, owner, cancel)
                outcome, error_code = source_error, source_error
                return
            if cancel is not None and cancel.is_set():
                self._release_claims(
                    [(projection_id, row.source_hash)], owner, self._as_utc_naive(now)
                )
                return
            story, options = str(source.get("story", "")), list(
                source.get("options", [])
            )
            reservation = self._reserve_attempt(row, now, owner, cancel)
            if reservation.status == AttemptReservationStatus.DAILY_CAP:
                self._defer_for_daily_cap(row, now, owner, cancel)
                outcome, error_code = "daily_call_cap", "daily_call_cap"
                return
            if reservation.status == AttemptReservationStatus.FENCED:
                outcome, error_code = "fenced", "fenced"
                return
            assert reservation.attempt_id is not None
            assert reservation.attempt_count is not None
            attempt_id = reservation.attempt_id
            row.attempt_count = reservation.attempt_count
            if cancel is None or not cancel.is_set():
                with self._lock:
                    self._heartbeat_done.add(done)
                heartbeat = threading.Thread(
                    target=self._lease_heartbeat,
                    args=(projection_id, row.source_hash, done, owner, cancel),
                    name="daily-world-projection-heartbeat",
                    daemon=True,
                )
                heartbeat.start()
            # The reservation commit permit is the provider-call linearization
            # point: a stop after that permit still consumes one real call.
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
                owner,
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
                if self._retry_and_finish_attempt(
                    row,
                    now,
                    source_error,
                    source_error,
                    owner,
                    attempt_id,
                    cancel,
                ):
                    attempt_id = None
                outcome, error_code = source_error, source_error
                return
            if cancel is not None and cancel.is_set():
                outcome, error_code = "cancelled", "cancelled"
                return
            coverage = self._coverage_mapping(
                detect_world_change_signals(story, options, source.get("tracked_state"))
            )
            published, attempt_finalized = self._transaction(
                lambda _session, repo: self._publish_and_finish_attempt(
                    repo,
                    row,
                    owner,
                    payload,
                    coverage,
                    attempt_id,
                ),
                cancel_guard=cancel,
                after_commit=self.after_final_publish_commit,
            )
            if attempt_finalized:
                attempt_id = None
            if published:
                try:
                    self.apply_ready_for_game(row.game_id)
                except Exception:
                    logger.exception(
                        "daily world projection serial apply failed game_id=%s projection_id=%s",
                        row.game_id,
                        row.projection_id,
                    )
            outcome, error_code = (
                ("success", None) if published else ("lease_lost", "lease_lost")
            )
        except GenerationCancelled:
            if provider_called:
                outcome, error_code = "cancelled", "cancelled"
            else:
                return
        except WorldProjectionExtractionError as exc:
            error_code = exc.code
            if cancel is not None and cancel.is_set() and provider_called:
                outcome, error_code = "cancelled", "cancelled"
            else:
                if provider_called and self._retry_and_finish_attempt(
                    row,
                    now,
                    error_code,
                    "extraction_error",
                    owner,
                    attempt_id,
                    cancel,
                ):
                    attempt_id = None
                elif not provider_called:
                    self._retry(row, now, error_code, owner, cancel)
                outcome = "extraction_error"
        except Exception:
            logger.exception(
                "daily world projection extraction failed projection_id=%s",
                projection_id,
            )
            if cancel is not None and cancel.is_set() and provider_called:
                outcome, error_code = "cancelled", "cancelled"
            else:
                if provider_called and self._retry_and_finish_attempt(
                    row,
                    now,
                    "unexpected_error",
                    "unexpected_error",
                    owner,
                    attempt_id,
                    cancel,
                ):
                    attempt_id = None
                elif not provider_called:
                    self._retry(row, now, "unexpected_error", owner, cancel)
        finally:
            done.set()
            if heartbeat is not None:
                heartbeat.join(timeout=0)
            with self._lock:
                self._heartbeat_done.discard(done)
            cancel_finalized = False
            if attempt_id is not None and cancel is not None and cancel.is_set():
                cancel_finalized = self._cancel_and_finish_attempt(
                    row, owner, attempt_id, self.now_fn()
                )
                if cancel_finalized:
                    attempt_id = None
            if attempt_id is not None:
                self._finish_attempt(
                    attempt_id,
                    outcome,
                    error_code,
                    self.now_fn(),
                )
            if cancel is not None and cancel.is_set() and not cancel_finalized:
                self._release_claims(
                    [(projection_id, row.source_hash)],
                    owner,
                    self._as_utc_naive(self.now_fn()),
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


def enqueue_accepted_daily_world_projection(
    game_id: int,
    event: Any,
    player_state: Any,
    *,
    replacement: bool = False,
) -> bool:
    """Best-effort durable enqueue after an event's canonical save commits."""

    service: Optional[DailyWorldProjectionService] = None
    try:
        service = get_daily_world_projection_service()
        if replacement:
            service.ensure_replacement_world_projection(game_id, event, player_state)
        else:
            service.ensure_world_projection(game_id, event, player_state)
        return True
    except Exception:
        logger.exception(
            "accepted daily event projection enqueue failed game_id=%s event_id=%s revision=%s",
            game_id,
            getattr(event, "event_id", None),
            getattr(event, "revision", None),
        )
        return False
    finally:
        if service is not None:
            try:
                service.wake()
            except Exception:
                logger.exception(
                    "daily world projection wake failed game_id=%s", game_id
                )
