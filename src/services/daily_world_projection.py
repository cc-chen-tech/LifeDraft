"""Durable, lease-fenced worker for daily world projection extraction.

The scanner deliberately owns no SQLAlchemy session. Each claim, extraction
completion, and heartbeat opens and closes its own short-lived session so a
stalled model request can never leak a session across worker threads.
"""

from __future__ import annotations

import logging
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from typing import Any, Callable, Mapping, Optional, Sequence

from src.database.models import DailyWorldProjection, GameState, SessionLocal
from src.game.world_projection_coverage import detect_world_change_signals
from src.game.world_projection_schema import (
    WorldProjectionExtractionError,
    compute_projection_source_hash,
)
from src.services.daily_world_projection_repository import (
    LEASE_DURATION,
    DailyWorldProjectionRepository,
    ProjectionIdentity,
)

logger = logging.getLogger(__name__)

RETRY_DELAYS = (5, 30, 120, 300, 1800, 7200)
MAX_DAILY_MODEL_CALLS = 8


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
        now_fn: Callable[[], datetime] = datetime.utcnow,
        wake_event: Optional[Any] = None,
        worker_id: Optional[str] = None,
        scan_seconds: float = 1.0,
        claim_limit: int = 4,
        extraction_workers: int = 2,
        heartbeat_interval: float = 60.0,
    ) -> None:
        self.session_factory = session_factory
        self.repository_factory = repository_factory
        self.extractor = extractor
        self.canonical_loader = canonical_loader or self._load_canonical_source
        self.now_fn = now_fn
        self.wake_event = wake_event or threading.Event()
        self.worker_id = worker_id or f"daily-world-projection-{uuid.uuid4()}"
        self.scan_seconds = scan_seconds
        self.claim_limit = claim_limit
        self.extraction_workers = extraction_workers
        self.heartbeat_interval = heartbeat_interval
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._scanner: Optional[threading.Thread] = None
        self._pool: Optional[ThreadPoolExecutor] = None
        self._started = False

    @property
    def is_running(self) -> bool:
        return self._started

    @staticmethod
    def next_retry_at(attempt_count: int, now: datetime) -> datetime:
        """Return the persisted retry deadline for a completed call count."""

        if attempt_count <= len(RETRY_DELAYS):
            return now + timedelta(seconds=RETRY_DELAYS[max(0, attempt_count - 1)])
        tomorrow = now.date() + timedelta(days=1)
        return datetime.combine(tomorrow, datetime.min.time(), tzinfo=now.tzinfo)

    @staticmethod
    def next_local_day(now: datetime) -> datetime:
        """Return the calendar reset point used by the per-game daily cap."""

        tomorrow = now.date() + timedelta(days=1)
        return datetime.combine(tomorrow, datetime.min.time(), tzinfo=now.tzinfo)

    def start(self) -> None:
        """Start exactly one daemon scanner and a bounded extraction pool."""

        with self._lock:
            if self._started:
                return
            self._stop.clear()
            self._pool = ThreadPoolExecutor(
                max_workers=self.extraction_workers,
                thread_name_prefix="daily-world-projection",
            )
            self._started = True
            self._scanner = threading.Thread(
                target=self._scan_loop,
                name="daily-world-projection-scanner",
                daemon=True,
            )
            self._scanner.start()

    def stop(self, *, wait: bool = False) -> None:
        """Fence future scanner claims and promptly release background resources."""

        with self._lock:
            if not self._started:
                return
            self._started = False
            self._stop.set()
            self.wake_event.set()
            pool, self._pool = self._pool, None
            scanner, self._scanner = self._scanner, None
        if pool is not None:
            pool.shutdown(wait=wait, cancel_futures=True)
        if wait and scanner is not None:
            scanner.join(timeout=1)

    def wake(self) -> None:
        self.wake_event.set()

    def ensure_world_projection(
        self, identity_or_game_id: Any, story_or_event: Any, options_or_state: Any
    ) -> Any:
        """Persist an idempotent row without starting a model or worker.

        The explicit ``(ProjectionIdentity, story, options)`` form keeps the
        durable repository boundary easy to test. The accepted-event form
        ``(game_id, event, player_state)`` is the enqueue hook used by gameplay.
        """

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
            day_index = field(
                timeline, "day_index", field(player_state, "day_index", 0)
            )
            event_id = field(event, "event_id")
            revision = field(event, "revision", 1)
            if not event_id or int(revision) < 1:
                raise ValueError("invalid_daily_world_projection_event")
            identity = ProjectionIdentity(
                game_id=game_id,
                event_id=str(event_id),
                revision=int(revision),
                day_index=int(day_index),
                story_date=field(event, "story_date", field(timeline, "current_date")),
            )
            story = str(field(event, "event_description", field(event, "story", "")))
            options = field(event, "options", [])

        session = self.session_factory()
        try:
            return self.repository_factory(session).ensure_projection(
                identity, compute_projection_source_hash(story, options)
            )
        finally:
            session.close()

    def run_once(self, now: Optional[datetime] = None) -> int:
        """Claim due projections, submitting them to the pool when running."""

        if self._stop.is_set():
            return 0
        now = now or self.now_fn()
        session = self.session_factory()
        try:
            claimed = self.repository_factory(session).claim_due(
                now=now, worker_id=self.worker_id, limit=self.claim_limit
            )
            claimed_ids = [int(row.projection_id) for row in claimed]
        finally:
            session.close()

        pool = self._pool
        for projection_id in claimed_ids:
            if self._stop.is_set():
                break
            if pool is None:
                self._process_claim(projection_id, now)
            else:
                try:
                    pool.submit(self._process_claim, projection_id, now)
                except RuntimeError:
                    # stop() may race a scan; no claim is made after this point.
                    break
        return len(claimed_ids)

    def _scan_loop(self) -> None:
        while not self._stop.is_set():
            try:
                self.run_once(self.now_fn())
            except Exception:
                logger.exception("daily world projection scan failed")
            self.wake_event.clear()
            self.wake_event.wait(self.scan_seconds)

    def _with_repository(self, callback: Callable[[Any], Any]) -> Any:
        session = self.session_factory()
        try:
            return callback(self.repository_factory(session))
        finally:
            session.close()

    def _load_canonical_source(
        self, game_id: int, event_id: str, revision: int
    ) -> Optional[Mapping[str, Any]]:
        """Load one accepted event from the latest durable player-state snapshot."""

        session = self.session_factory()
        try:
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
                if not isinstance(story, str) or not isinstance(options, list):
                    return None
                return {
                    "revision": revision,
                    "story": story,
                    "options": options,
                    "tracked_state": data,
                }
            return None
        finally:
            session.close()

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

    def _extract(self, story: str, options: Sequence[Any], tracked_state: Any) -> Any:
        """Construct the model facade only in a claimed worker, never at import."""

        if self.extractor is not None:
            return self.extractor(story, options, tracked_state)
        from src.ai.generator import EventGenerator

        return EventGenerator().extract_daily_world_projection(
            story, list(options), tracked_state
        )

    def _renew_lease(self, projection_id: int, source_hash: str) -> bool:
        now = self.now_fn()
        return bool(
            self._with_repository(
                lambda repo: repo.renew_lease(
                    projection_id,
                    self.worker_id,
                    now,
                    now + LEASE_DURATION,
                    source_hash=source_hash,
                )
            )
        )

    def _lease_heartbeat(
        self, projection_id: int, source_hash: str, done: threading.Event
    ) -> None:
        """Renew with an independent session until the extraction returns."""

        while not done.wait(self.heartbeat_interval):
            if self._stop.is_set() or not self._renew_lease(projection_id, source_hash):
                return

    def _retry(self, repo: Any, row: Any, now: datetime, error_code: str) -> bool:
        return bool(
            repo.mark_retryable(
                row.projection_id,
                self.worker_id,
                error_code,
                self.next_retry_at(row.attempt_count, now),
                source_hash=row.source_hash,
            )
        )

    def _process_claim(self, projection_id: int, now: datetime) -> None:
        """Extract one claimed row. Every model call records an attempt in finally."""

        session = self.session_factory()
        repo = self.repository_factory(session)
        attempt_id: Optional[int] = None
        row: Any = None
        outcome = "unexpected_error"
        error_code: Optional[str] = "unexpected_error"
        heartbeat_done = threading.Event()
        heartbeat: Optional[threading.Thread] = None
        try:
            row = session.get(DailyWorldProjection, projection_id)
            if (
                row is None
                or row.lease_owner != self.worker_id
                or row.status != "running"
            ):
                return
            day_start = datetime.combine(
                now.date(), datetime.min.time(), tzinfo=now.tzinfo
            )
            if (
                repo.count_game_attempts_between(row.game_id, day_start, now)
                >= MAX_DAILY_MODEL_CALLS
            ):
                repo.mark_retryable(
                    row.projection_id,
                    self.worker_id,
                    "daily_call_cap",
                    self.next_local_day(now),
                    source_hash=row.source_hash,
                )
                outcome, error_code = "daily_call_cap", "daily_call_cap"
                return

            source, source_error = self._validated_canonical_source(row)
            if source is None:
                assert source_error is not None
                self._retry(repo, row, now, source_error)
                outcome, error_code = source_error, source_error
                return
            story, options = str(source.get("story", "")), list(
                source.get("options", [])
            )

            attempt_id = repo.start_attempt(projection_id, row.game_id, now)
            if not self._renew_lease(projection_id, row.source_hash):
                outcome, error_code = "lease_lost", "lease_lost"
                return
            heartbeat = threading.Thread(
                target=self._lease_heartbeat,
                args=(projection_id, row.source_hash, heartbeat_done),
                name="daily-world-projection-heartbeat",
                daemon=True,
            )
            heartbeat.start()
            payload = self._extract(story, options, source.get("tracked_state"))
            heartbeat_done.set()
            if not self._renew_lease(projection_id, row.source_hash):
                outcome, error_code = "lease_lost", "lease_lost"
                return

            latest_source, source_error = self._validated_canonical_source(row)
            if latest_source is None:
                assert source_error is not None
                self._retry(repo, row, now, source_error)
                outcome, error_code = source_error, source_error
                return

            coverage = detect_world_change_signals(
                story, options, source.get("tracked_state")
            )
            if repo.mark_ready(
                projection_id,
                self.worker_id,
                row.source_hash,
                payload,
                bool(getattr(payload, "no_change", False)),
                coverage=coverage,
            ):
                outcome, error_code = "success", None
            else:
                outcome, error_code = "lease_lost", "lease_lost"
        except WorldProjectionExtractionError as exc:
            error_code = exc.code
            if row is not None:
                self._retry(repo, row, now, error_code)
            outcome = "extraction_error"
        except Exception:
            logger.exception(
                "daily world projection extraction failed projection_id=%s",
                projection_id,
            )
            if row is not None:
                self._retry(repo, row, now, "unexpected_error")
        finally:
            heartbeat_done.set()
            if heartbeat is not None:
                heartbeat.join(timeout=0)
            if attempt_id is not None:
                repo.finish_attempt(attempt_id, outcome, error_code, self.now_fn())
            session.close()


_service: Optional[DailyWorldProjectionService] = None
_service_lock = threading.Lock()


def get_daily_world_projection_service() -> DailyWorldProjectionService:
    """Lazily construct the process singleton after startup enables the flag."""

    global _service
    with _service_lock:
        if _service is None:
            _service = DailyWorldProjectionService()
        return _service
