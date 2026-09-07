"""Bounded durable voice job execution and recovery, off the ASGI event loop."""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from threading import BoundedSemaphore, Event, Lock, Thread
from typing import Callable, Optional

from sqlalchemy import create_engine, or_
from sqlalchemy.orm import Session, sessionmaker

from src.database.models import VoiceReadingJob, engine
from src.services.story_tts_provider import StoryTTSProvider
from src.services.story_voice_reading import StoryVoiceReadingService
from src.services.story_voice_repository import (
    PROCESSING_LEASE_DURATION,
    StoryVoiceReadingRepository,
)

logger = logging.getLogger(__name__)


class StoryVoiceWorker:
    """Admit only jobs with an execution slot; excess work stays in the DB."""

    def __init__(
        self,
        *,
        session_factory: Optional[Callable[[], Session]] = None,
        provider_factory: Optional[Callable[[], StoryTTSProvider]] = None,
        max_workers: int = 2,
        poll_interval: float = 30,
    ) -> None:
        self._engine = None
        if session_factory is None:
            # Separate pool and bounded lock wait; no journal-mode changes or
            # timeout mutation on the shared application connections.
            options = (
                {"connect_args": {"timeout": 0.5, "check_same_thread": False}}
                if engine.dialect.name == "sqlite"
                else {}
            )
            self._engine = create_engine(engine.url, **options)
            session_factory = sessionmaker(bind=self._engine, expire_on_commit=False)
        self._sessions = session_factory
        self._providers = provider_factory
        self._executor = ThreadPoolExecutor(
            max_workers=max_workers, thread_name_prefix="story-voice"
        )
        self._slots = BoundedSemaphore(max_workers)
        self._lock = Lock()
        self._active: set[tuple[int, int]] = set()
        self._stopped = Event()
        self._scanner: Optional[Thread] = None
        self._poll_interval = poll_interval

    def start(self) -> None:
        with self._lock:
            if self._scanner is not None or self._stopped.is_set():
                return
            self._scanner = Thread(target=self._scan_loop, name="story-voice-recovery", daemon=True)
            self._scanner.start()

    def submit(self, user_id: int, job_id: int) -> bool:
        key = (user_id, job_id)
        with self._lock:
            if (
                self._stopped.is_set()
                or key in self._active
                or not self._slots.acquire(blocking=False)
            ):
                return False
            self._active.add(key)
            try:
                self._executor.submit(self._run, user_id, job_id)
            except RuntimeError:
                self._active.remove(key)
                self._slots.release()
                return False
        return True

    def _run(self, user_id: int, job_id: int) -> None:
        try:
            with self._sessions() as db:
                repository = StoryVoiceReadingRepository(db)
                repository.recover_abandoned_job(user_id, job_id)
                provider = self._providers() if self._providers is not None else None
                StoryVoiceReadingService(repository, provider=provider).process_job(user_id, job_id)
        except Exception:
            # No failed Session is reused here. A committed processing lease
            # eventually expires, and a queued job remains discoverable.
            logger.exception("Voice worker failed job_id=%s", job_id)
        finally:
            with self._lock:
                self._active.discard((user_id, job_id))
                self._slots.release()

    def scan_once(self) -> None:
        stale_before = datetime.utcnow() - PROCESSING_LEASE_DURATION
        with self._sessions() as db:
            candidates = (
                db.query(VoiceReadingJob.user_id, VoiceReadingJob.job_id)
                .filter(
                    or_(
                        VoiceReadingJob.status == "queued",
                        (VoiceReadingJob.status == "processing")
                        & or_(
                            VoiceReadingJob.updated_at.is_(None),
                            VoiceReadingJob.updated_at < stale_before,
                        ),
                    )
                )
                .order_by(VoiceReadingJob.updated_at, VoiceReadingJob.job_id)
                .limit(20)
                .all()
            )
        for user_id, job_id in candidates:
            if self._stopped.is_set():
                break
            self.submit(int(user_id), int(job_id))

    def _scan_loop(self) -> None:
        while not self._stopped.is_set():
            try:
                self.scan_once()
            except Exception:
                logger.exception("Voice recovery scan failed")
            self._stopped.wait(self._poll_interval)

    def stop(self, *, wait: bool = False) -> None:
        self._stopped.set()
        if self._scanner is not None:
            self._scanner.join(timeout=1)
        self._executor.shutdown(wait=wait, cancel_futures=False)
        if self._engine is not None:
            self._engine.dispose()


_worker: Optional[StoryVoiceWorker] = None
_worker_lock = Lock()


def get_story_voice_worker() -> StoryVoiceWorker:
    global _worker
    with _worker_lock:
        if _worker is None:
            _worker = StoryVoiceWorker()
        return _worker


def submit_story_voice_job(user_id: int, job_id: int) -> bool:
    return get_story_voice_worker().submit(user_id, job_id)


def stop_story_voice_worker(*, wait: bool = False) -> None:
    global _worker
    with _worker_lock:
        worker, _worker = _worker, None
    if worker is not None:
        worker.stop(wait=wait)
