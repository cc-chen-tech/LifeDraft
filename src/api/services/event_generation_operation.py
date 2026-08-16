"""Thread-safe state for one durable round-event generation operation.

The operation belongs to a game session rather than an HTTP response. SSE
connections are subscribers: they can disconnect and later replay unseen
chunks without taking ownership of the background generation worker.
"""

from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass
from typing import Any, Literal, Optional

EventGenerationStatus = Literal["running", "completed", "failed"]


@dataclass(frozen=True)
class EventGenerationKey:
    """Identity of one logical event-generation operation."""

    game_id: int
    week: int
    round_number: int
    stage: str = "event"
    resolved_mode: str = "event"
    base_event_id: str = ""
    base_revision: int = 0


@dataclass(frozen=True)
class EventGenerationSnapshot:
    """Immutable subscriber view of an operation at one instant."""

    status: EventGenerationStatus
    phase: str
    chunks: tuple[tuple[int, str], ...]
    result: Optional[Any]
    error: Optional[str]
    failure: Optional[dict[str, Any]]
    phase_payload: dict[str, Any]
    retry_version: int
    retry_payload: dict[str, Any]
    retry_start_event_id: int


class EventGenerationConflict(RuntimeError):
    """Raised when a different operation tries to replace a running one."""


class EventGenerationOperation:
    """Thread-safe event log and terminal state for one generation job."""

    MAX_CHUNKS = 500

    def __init__(self, key: EventGenerationKey):
        self.key = key
        self.operation_id = uuid.uuid4().hex
        self._lock = threading.RLock()
        self._status: EventGenerationStatus = "running"
        self._phase = "preparing"
        self._phase_payload: dict[str, Any] = {"phase": "preparing"}
        self._retry_version = 0
        self._retry_payload: dict[str, Any] = {}
        self._retry_start_event_id = -1
        self._chunks: list[tuple[int, str]] = []
        self._next_event_id = 0
        self._result: Optional[Any] = None
        self._error: Optional[str] = None
        self._failure: Optional[dict[str, Any]] = None

    @property
    def status(self) -> EventGenerationStatus:
        with self._lock:
            return self._status

    def publish_story(self, chunk: str) -> int:
        """Append a story chunk and return its monotonically increasing SSE ID."""
        with self._lock:
            event_id = self._next_event_id
            self._next_event_id += 1
            self._chunks.append((event_id, chunk))
            if len(self._chunks) > self.MAX_CHUNKS:
                self._chunks = self._chunks[-self.MAX_CHUNKS :]
            return event_id

    def publish_phase(self, phase: Any) -> None:
        with self._lock:
            if isinstance(phase, dict):
                payload = dict(phase)
                self._phase = str(payload.get("phase") or "processing")
                payload["phase"] = self._phase
                self._phase_payload = payload
            else:
                self._phase = str(phase)
                self._phase_payload = {"phase": self._phase}
            if self._phase == "retry":
                # A retry starts a new candidate generation. Rejected prose must
                # never be replayed to a current or reconnecting subscriber.
                self._chunks.clear()
                self._retry_version += 1
                self._retry_payload = dict(self._phase_payload)
                self._retry_start_event_id = self._next_event_id

    def complete(self, result: Any) -> None:
        with self._lock:
            self._result = result
            self._error = None
            self._failure = None
            self._status = "completed"
            self._phase = "completed"
            self._phase_payload = {"phase": "completed"}

    def fail(self, error: str, *, failure: Optional[dict[str, Any]] = None) -> None:
        with self._lock:
            self._result = None
            self._error = error
            self._failure = failure
            self._status = "failed"
            self._phase = "failed"
            self._phase_payload = {"phase": "failed"}

    def snapshot_after(self, last_event_id: int) -> EventGenerationSnapshot:
        """Return terminal state plus chunks newer than ``last_event_id``."""
        with self._lock:
            return EventGenerationSnapshot(
                status=self._status,
                phase=self._phase,
                chunks=tuple(
                    (event_id, chunk)
                    for event_id, chunk in self._chunks
                    if event_id > last_event_id
                ),
                result=self._result,
                error=self._error,
                failure=self._failure,
                phase_payload=dict(self._phase_payload),
                retry_version=self._retry_version,
                retry_payload=dict(self._retry_payload),
                retry_start_event_id=self._retry_start_event_id,
            )


class EventGenerationCoordinator:
    """Own the current operation for one game session."""

    def __init__(self):
        self._lock = threading.Lock()
        self._current: Optional[EventGenerationOperation] = None

    def get_or_create(
        self,
        key: EventGenerationKey,
        *,
        restart_completed: bool = False,
    ) -> tuple[EventGenerationOperation, bool]:
        """Return the operation and whether the caller must start its worker."""
        with self._lock:
            current = self._current
            if current is not None and current.status == "running":
                if current.key != key:
                    raise EventGenerationConflict(
                        f"generation already running for {current.key}"
                    )
                return current, False
            if (
                current is not None
                and current.key == key
                and current.status == "completed"
                and not restart_completed
            ):
                return current, False
            return self._create_unlocked(key)

    def get_or_create_for_slot(
        self,
        key: EventGenerationKey,
        *,
        restart_completed: bool = False,
    ) -> tuple[EventGenerationOperation, bool]:
        """Coalesce all daily requests targeting the same saved day."""

        with self._lock:
            current = self._current
            if current is not None and current.status == "running":
                same_slot = (
                    current.key.game_id,
                    current.key.week,
                    current.key.round_number,
                ) == (key.game_id, key.week, key.round_number)
                if same_slot:
                    return current, False
                raise EventGenerationConflict(
                    f"generation already running for {current.key}"
                )
            if (
                current is not None
                and current.key == key
                and current.status == "completed"
                and not restart_completed
            ):
                return current, False
            return self._create_unlocked(key)

    def _create_unlocked(
        self, key: EventGenerationKey
    ) -> tuple[EventGenerationOperation, bool]:
        operation = EventGenerationOperation(key)
        self._current = operation
        return operation, True

    def current(self) -> Optional[EventGenerationOperation]:
        """Return the current durable operation without changing its state."""
        with self._lock:
            return self._current
