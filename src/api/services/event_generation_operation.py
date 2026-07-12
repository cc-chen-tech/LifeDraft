"""Thread-safe state for one durable round-event generation operation.

The operation belongs to a game session rather than an HTTP response. SSE
connections are subscribers: they can disconnect and later replay unseen
chunks without taking ownership of the background generation worker.
"""

from __future__ import annotations

import threading
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


@dataclass(frozen=True)
class EventGenerationSnapshot:
    """Immutable subscriber view of an operation at one instant."""

    status: EventGenerationStatus
    phase: str
    chunks: tuple[tuple[int, str], ...]
    result: Optional[Any]
    error: Optional[str]


class EventGenerationConflict(RuntimeError):
    """Raised when a different operation tries to replace a running one."""


class EventGenerationOperation:
    """Thread-safe event log and terminal state for one generation job."""

    MAX_CHUNKS = 500

    def __init__(self, key: EventGenerationKey):
        self.key = key
        self._lock = threading.RLock()
        self._status: EventGenerationStatus = "running"
        self._phase = "preparing"
        self._chunks: list[tuple[int, str]] = []
        self._next_event_id = 0
        self._result: Optional[Any] = None
        self._error: Optional[str] = None

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

    def publish_phase(self, phase: str) -> None:
        with self._lock:
            self._phase = phase

    def complete(self, result: Any) -> None:
        with self._lock:
            self._result = result
            self._error = None
            self._status = "completed"
            self._phase = "completed"

    def fail(self, error: str) -> None:
        with self._lock:
            self._result = None
            self._error = error
            self._status = "failed"
            self._phase = "failed"

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
            )


class EventGenerationCoordinator:
    """Own the current operation for one game session."""

    def __init__(self):
        self._lock = threading.Lock()
        self._current: Optional[EventGenerationOperation] = None

    def get_or_create(
        self, key: EventGenerationKey
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
            if current is not None and current.key == key and current.status == "completed":
                return current, False

            operation = EventGenerationOperation(key)
            self._current = operation
            return operation, True
