"""Read-only health summaries and thresholded alerts for world projections."""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping, Optional

from sqlalchemy import func

from src.database.models import (
    DailyWorldProjection,
    DailyWorldProjectionAttempt,
    DailyWorldProjectionRepairAudit,
)


logger = logging.getLogger(__name__)

ATTEMPT_WINDOW = timedelta(hours=1)
ALERT_INTERVAL = timedelta(minutes=15)
PENDING_ALERT_SECONDS = 10 * 60
SUSPICIOUS_EMPTY_MINIMUM_ATTEMPTS = 20
SUSPICIOUS_EMPTY_RATE_THRESHOLD = 0.02
FENCED_LATE_WRITE_THRESHOLD = 5

_PENDING_STATUSES = ("pending", "running", "failed_retryable")
_COMPLETE_REPAIR_STATUSES = ("complete", "restored")
_FENCED_LATE_WRITE_OUTCOMES = ("lease_lost",)


def _as_utc_naive(value: datetime) -> datetime:
    """Match the projection tables' naive-UTC timestamp convention."""

    if value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


@dataclass(frozen=True)
class ProjectionHealthSnapshot:
    """The stable, JSON-ready public projection health contract."""

    projection_status_counts: Mapping[str, int]
    oldest_pending_seconds: Optional[float]
    attempts_last_hour: int
    suspicious_empty_count: int
    suspicious_empty_rate: float
    ready_no_change_count: int
    fenced_late_writes: int
    superseded_rows: int
    incomplete_repair_audits: int
    latest_completed_repair_audit_id: Optional[int]

    def to_dict(self) -> dict[str, Any]:
        """Return only the documented snapshot fields in deterministic order."""

        return {
            "projection_status_counts": dict(
                sorted(self.projection_status_counts.items())
            ),
            "oldest_pending_seconds": self.oldest_pending_seconds,
            "attempts_last_hour": self.attempts_last_hour,
            "suspicious_empty_count": self.suspicious_empty_count,
            "suspicious_empty_rate": self.suspicious_empty_rate,
            "ready_no_change_count": self.ready_no_change_count,
            "fenced_late_writes": self.fenced_late_writes,
            "superseded_rows": self.superseded_rows,
            "incomplete_repair_audits": self.incomplete_repair_audits,
            "latest_completed_repair_audit_id": (self.latest_completed_repair_audit_id),
        }


class ProjectionHealthAlertLimiter:
    """Thread-safe per-process alert-key limiter with an injectable instance."""

    def __init__(self, interval: timedelta = ALERT_INTERVAL) -> None:
        self.interval = interval
        self._lock = threading.Lock()
        self._last_emitted: dict[str, datetime] = {}

    def allow(self, key: str, now: datetime) -> bool:
        """Reserve an alert key when its process-local interval has elapsed."""

        current = _as_utc_naive(now)
        with self._lock:
            previous = self._last_emitted.get(key)
            if previous is not None and current - previous < self.interval:
                return False
            self._last_emitted[key] = current
            return True


_PROCESS_ALERT_LIMITER = ProjectionHealthAlertLimiter()


def summarize_projection_health(db: Any, now: datetime) -> ProjectionHealthSnapshot:
    """Aggregate durable health without claiming or modifying any database row."""

    db_now = _as_utc_naive(now)
    window_start = db_now - ATTEMPT_WINDOW

    status_counts = {
        str(status): int(count)
        for status, count in (
            db.query(DailyWorldProjection.status, func.count())
            .group_by(DailyWorldProjection.status)
            .all()
        )
    }
    pending_rows = (
        db.query(DailyWorldProjection.game_id, DailyWorldProjection.created_at)
        .filter(DailyWorldProjection.status.in_(_PENDING_STATUSES))
        .all()
    )
    attempts = (
        db.query(
            DailyWorldProjectionAttempt.game_id,
            DailyWorldProjectionAttempt.outcome,
            DailyWorldProjectionAttempt.error_code,
        )
        .filter(
            DailyWorldProjectionAttempt.started_at >= window_start,
            DailyWorldProjectionAttempt.started_at <= db_now,
        )
        .all()
    )
    audits = db.query(
        DailyWorldProjectionRepairAudit.audit_id,
        DailyWorldProjectionRepairAudit.game_id,
        DailyWorldProjectionRepairAudit.status,
    ).all()

    pending_ages = [
        max(0.0, (db_now - _as_utc_naive(created_at)).total_seconds())
        for _game_id, created_at in pending_rows
        if isinstance(created_at, datetime)
    ]
    suspicious = [
        row
        for row in attempts
        if row.outcome == "suspicious_empty" or row.error_code == "suspicious_empty"
    ]
    fenced = [
        row
        for row in attempts
        if row.outcome in _FENCED_LATE_WRITE_OUTCOMES
        or row.error_code in _FENCED_LATE_WRITE_OUTCOMES
    ]
    failed_audits = [row for row in audits if row.status == "failed_invariant"]
    completed_ids = [int(row.audit_id) for row in audits if row.status == "complete"]
    attempts_count = len(attempts)

    snapshot = ProjectionHealthSnapshot(
        projection_status_counts=status_counts,
        oldest_pending_seconds=max(pending_ages) if pending_ages else None,
        attempts_last_hour=attempts_count,
        suspicious_empty_count=len(suspicious),
        suspicious_empty_rate=(
            len(suspicious) / attempts_count if attempts_count else 0.0
        ),
        ready_no_change_count=status_counts.get("ready_no_change", 0),
        fenced_late_writes=len(fenced),
        superseded_rows=status_counts.get("superseded", 0),
        incomplete_repair_audits=sum(
            1 for row in audits if row.status not in _COMPLETE_REPAIR_STATUSES
        ),
        latest_completed_repair_audit_id=(
            max(completed_ids) if completed_ids else None
        ),
    )
    # Alert routing metadata is intentionally private: the serialized snapshot
    # stays stable, while identifiers can be attached only as structured context.
    object.__setattr__(snapshot, "_observed_at", db_now)
    object.__setattr__(
        snapshot,
        "_alert_context",
        {
            "oldest_pending": {
                "game_ids": sorted(
                    {
                        int(game_id)
                        for game_id, created_at in pending_rows
                        if isinstance(created_at, datetime)
                        and (db_now - _as_utc_naive(created_at)).total_seconds()
                        > PENDING_ALERT_SECONDS
                    }
                )
            },
            "suspicious_empty_rate": {
                "game_ids": sorted({int(row.game_id) for row in suspicious})
            },
            "failed_invariant_audit": {
                "game_ids": sorted({int(row.game_id) for row in failed_audits}),
                "audit_ids": sorted(int(row.audit_id) for row in failed_audits),
            },
            "fenced_late_writes": {
                "game_ids": sorted({int(row.game_id) for row in fenced})
            },
        },
    )
    return snapshot


def _alerts(snapshot: ProjectionHealthSnapshot) -> tuple[tuple[str, str], ...]:
    alerts: list[tuple[str, str]] = []
    if (
        snapshot.oldest_pending_seconds is not None
        and snapshot.oldest_pending_seconds > PENDING_ALERT_SECONDS
    ):
        alerts.append(
            (
                "oldest_pending",
                "Daily world projection backlog exceeds the age threshold",
            )
        )
    if (
        snapshot.attempts_last_hour >= SUSPICIOUS_EMPTY_MINIMUM_ATTEMPTS
        and snapshot.suspicious_empty_rate > SUSPICIOUS_EMPTY_RATE_THRESHOLD
    ):
        alerts.append(
            (
                "suspicious_empty_rate",
                "Daily world projection suspicious-empty rate exceeds the threshold",
            )
        )
    context = getattr(snapshot, "_alert_context", {})
    if context.get("failed_invariant_audit", {}).get("audit_ids"):
        alerts.append(
            (
                "failed_invariant_audit",
                "Daily world projection repair failed its invariant check",
            )
        )
    if snapshot.fenced_late_writes > FENCED_LATE_WRITE_THRESHOLD:
        alerts.append(
            (
                "fenced_late_writes",
                "Daily world projection late-write rejections exceed the threshold",
            )
        )
    return tuple(alerts)


def _capture_warning(
    sentry: Any, message: str, key: str, context: Mapping[str, Any]
) -> None:
    structured = {"alert_key": key, **dict(context)}
    scope_factory = getattr(sentry, "new_scope", None) or getattr(
        sentry, "push_scope", None
    )
    if callable(scope_factory):
        with scope_factory() as scope:
            scope.set_context("world_projection_health", structured)
            sentry.capture_message(message, level="warning")
        return
    sentry.capture_message(message, level="warning")


def emit_projection_health(
    snapshot: ProjectionHealthSnapshot,
    *,
    sentry: Optional[Any] = None,
    limiter: Optional[ProjectionHealthAlertLimiter] = None,
) -> tuple[str, ...]:
    """Emit one structured summary log and rate-limited warning alerts."""

    logger.info(
        "daily_world_projection_health",
        extra={"projection_health": snapshot.to_dict()},
    )
    if sentry is None:
        import sentry_sdk

        sentry = sentry_sdk
    active_limiter = limiter or _PROCESS_ALERT_LIMITER
    observed_at = getattr(snapshot, "_observed_at", datetime.utcnow())
    alert_context = getattr(snapshot, "_alert_context", {})
    emitted: list[str] = []
    for key, message in _alerts(snapshot):
        if not active_limiter.allow(key, observed_at):
            continue
        _capture_warning(sentry, message, key, alert_context.get(key, {}))
        emitted.append(key)
    return tuple(emitted)
