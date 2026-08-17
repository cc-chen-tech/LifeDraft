"""Read-only health contracts for durable daily world projections."""

from __future__ import annotations

import json
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from io import StringIO
from typing import Any, Iterator

import pytest
from sqlalchemy import event

from src.database.models import (
    DailyWorldProjection,
    DailyWorldProjectionAttempt,
    DailyWorldProjectionRepairAudit,
    Game,
)
from src.services.daily_world_projection_observability import (
    ProjectionHealthAlertLimiter,
    emit_projection_health,
    summarize_projection_health,
)
from scripts.world_projection_status import run as run_status


NOW = datetime(2026, 8, 17, 10, 0, tzinfo=timezone.utc)


def _projection(
    db: Any,
    game_id: int,
    *,
    status: str = "pending",
    age: timedelta = timedelta(),
) -> DailyWorldProjection:
    row = DailyWorldProjection(
        game_id=game_id,
        event_id=f"event-{game_id}-{status}",
        revision=1,
        day_index=0,
        source_hash=f"hash-{game_id}-{status}",
        status=status,
        next_attempt_at=NOW.replace(tzinfo=None),
        created_at=(NOW - age).replace(tzinfo=None),
        updated_at=(NOW - age).replace(tzinfo=None),
    )
    db.add(row)
    db.flush()
    return row


def _attempt(
    db: Any,
    projection: DailyWorldProjection,
    *,
    outcome: str,
    age: timedelta,
) -> None:
    started = (NOW - age).replace(tzinfo=None)
    db.add(
        DailyWorldProjectionAttempt(
            projection_id=projection.projection_id,
            game_id=projection.game_id,
            started_at=started,
            finished_at=started + timedelta(seconds=1),
            outcome=outcome,
            error_code=None if outcome == "success" else outcome,
        )
    )


def _audit(db: Any, game_id: int, status: str) -> DailyWorldProjectionRepairAudit:
    row = DailyWorldProjectionRepairAudit(
        game_id=game_id,
        state_id=1,
        report_hash="a" * 64,
        backup_path="/redacted/backup.json",
        backup_sha256="b" * 64,
        non_projection_digest_before="c" * 64,
        status=status,
        detail_json={},
        completed_at=(NOW.replace(tzinfo=None) if status == "complete" else None),
    )
    db.add(row)
    db.flush()
    return row


def _game(db: Any) -> int:
    game = Game(initial_state={})
    db.add(game)
    db.flush()
    return int(game.game_id)


def test_health_snapshot_reports_exact_read_only_aggregates(db_session) -> None:
    game_id = _game(db_session)
    pending = _projection(
        db_session, game_id, status="pending", age=timedelta(minutes=12)
    )
    _projection(db_session, game_id, status="ready_no_change")
    _projection(db_session, game_id, status="superseded")
    _projection(db_session, game_id, status="applied")
    for index in range(40):
        _attempt(
            db_session,
            pending,
            outcome="suspicious_empty" if index < 2 else "success",
            age=timedelta(minutes=30),
        )
    _attempt(
        db_session,
        pending,
        outcome="suspicious_empty",
        age=timedelta(hours=2),
    )
    _attempt(db_session, pending, outcome="lease_lost", age=timedelta(minutes=10))
    _attempt(
        db_session,
        pending,
        outcome="source_superseded",
        age=timedelta(minutes=5),
    )
    queued = _audit(db_session, game_id, "queued")
    _audit(db_session, game_id, "restored")
    completed = _audit(db_session, game_id, "complete")
    _audit(db_session, game_id, "failed_invariant")
    db_session.commit()

    statements: list[str] = []

    def record_statement(
        _conn: Any,
        _cursor: Any,
        statement: str,
        _parameters: Any,
        _context: Any,
        _executemany: bool,
    ) -> None:
        statements.append(statement.lstrip().split(None, 1)[0].upper())

    event.listen(db_session.get_bind(), "before_cursor_execute", record_statement)
    try:
        health = summarize_projection_health(db_session, NOW)
    finally:
        event.remove(db_session.get_bind(), "before_cursor_execute", record_statement)

    assert health.to_dict() == {
        "projection_status_counts": {
            "applied": 1,
            "pending": 1,
            "ready_no_change": 1,
            "superseded": 1,
        },
        "oldest_pending_seconds": 720.0,
        "attempts_last_hour": 42,
        "suspicious_empty_count": 2,
        "suspicious_empty_rate": pytest.approx(2 / 42),
        "ready_no_change_count": 1,
        "fenced_late_writes": 2,
        "superseded_rows": 1,
        "incomplete_repair_audits": 2,
        "latest_completed_repair_audit_id": completed.audit_id,
    }
    assert queued.audit_id < completed.audit_id
    assert statements and set(statements) == {"SELECT"}


def test_health_snapshot_accepts_naive_now_and_empty_database(db_session) -> None:
    health = summarize_projection_health(db_session, NOW.replace(tzinfo=None))

    assert health.to_dict() == {
        "projection_status_counts": {},
        "oldest_pending_seconds": None,
        "attempts_last_hour": 0,
        "suspicious_empty_count": 0,
        "suspicious_empty_rate": 0.0,
        "ready_no_change_count": 0,
        "fenced_late_writes": 0,
        "superseded_rows": 0,
        "incomplete_repair_audits": 0,
        "latest_completed_repair_audit_id": None,
    }


class _Scope:
    def __init__(self, contexts: list[tuple[str, dict[str, Any]]]) -> None:
        self.contexts = contexts

    def set_context(self, name: str, context: dict[str, Any]) -> None:
        self.contexts.append((name, context))


class _Sentry:
    def __init__(self) -> None:
        self.contexts: list[tuple[str, dict[str, Any]]] = []
        self.messages: list[tuple[str, str]] = []

    @contextmanager
    def push_scope(self) -> Iterator[_Scope]:
        yield _Scope(self.contexts)

    def capture_message(self, message: str, *, level: str) -> None:
        self.messages.append((message, level))


def test_alert_requires_minimum_sample_and_strict_thresholds(db_session) -> None:
    game_id = _game(db_session)
    pending = _projection(
        db_session, game_id, status="pending", age=timedelta(minutes=10)
    )
    for _index in range(3):
        _attempt(
            db_session,
            pending,
            outcome="suspicious_empty",
            age=timedelta(minutes=5),
        )
    for _index in range(5):
        _attempt(
            db_session,
            pending,
            outcome="lease_lost",
            age=timedelta(minutes=5),
        )
    db_session.commit()
    sentry = _Sentry()

    emitted = emit_projection_health(
        summarize_projection_health(db_session, NOW),
        sentry=sentry,
        limiter=ProjectionHealthAlertLimiter(),
    )

    assert emitted == ()
    assert sentry.messages == []


def test_alerts_are_thresholded_redacted_and_rate_limited(db_session) -> None:
    game_id = _game(db_session)
    pending = _projection(
        db_session, game_id, status="failed_retryable", age=timedelta(minutes=11)
    )
    for index in range(20):
        _attempt(
            db_session,
            pending,
            outcome="suspicious_empty" if index == 0 else "success",
            age=timedelta(minutes=5),
        )
    for _index in range(6):
        _attempt(
            db_session,
            pending,
            outcome="source_superseded",
            age=timedelta(minutes=5),
        )
    failed = _audit(db_session, game_id, "failed_invariant")
    db_session.commit()
    sentry = _Sentry()
    limiter = ProjectionHealthAlertLimiter()

    first = emit_projection_health(
        summarize_projection_health(db_session, NOW),
        sentry=sentry,
        limiter=limiter,
    )
    suppressed = emit_projection_health(
        summarize_projection_health(db_session, NOW + timedelta(minutes=14)),
        sentry=sentry,
        limiter=limiter,
    )

    assert first == (
        "oldest_pending",
        "suspicious_empty_rate",
        "failed_invariant_audit",
        "fenced_late_writes",
    )
    assert suppressed == ()
    assert len(sentry.messages) == 4
    assert all(level == "warning" for _message, level in sentry.messages)
    assert all(str(game_id) not in message for message, _level in sentry.messages)
    contexts = [
        context
        for name, context in sentry.contexts
        if name == "world_projection_health"
    ]
    assert len(contexts) == 4
    assert all(context["game_ids"] == [game_id] for context in contexts)
    failed_context = next(
        context
        for context in contexts
        if context["alert_key"] == "failed_invariant_audit"
    )
    assert failed_context["audit_ids"] == [failed.audit_id]


def test_alert_limiter_allows_each_key_again_after_fifteen_minutes(db_session) -> None:
    game_id = _game(db_session)
    _projection(db_session, game_id, age=timedelta(minutes=30))
    db_session.commit()
    sentry = _Sentry()
    limiter = ProjectionHealthAlertLimiter()

    emit_projection_health(
        summarize_projection_health(db_session, NOW),
        sentry=sentry,
        limiter=limiter,
    )
    emitted = emit_projection_health(
        summarize_projection_health(db_session, NOW + timedelta(minutes=15)),
        sentry=sentry,
        limiter=limiter,
    )

    assert emitted == ("oldest_pending",)
    assert len(sentry.messages) == 2


def test_status_cli_prints_unhealthy_snapshot_and_exits_zero(db_session) -> None:
    game_id = _game(db_session)
    _projection(db_session, game_id, age=timedelta(minutes=20))
    db_session.commit()
    output = StringIO()
    errors = StringIO()

    result = run_status(
        ["--json"],
        session_factory=lambda: db_session,
        now_fn=lambda: NOW,
        stdout=output,
        stderr=errors,
    )

    assert result == 0
    assert json.loads(output.getvalue())["oldest_pending_seconds"] == 1200.0
    assert errors.getvalue() == ""


def test_status_cli_returns_nonzero_only_for_query_failure() -> None:
    class BrokenSession:
        def query(self, *_args: Any) -> Any:
            raise RuntimeError("database unavailable")

        def close(self) -> None:
            pass

    output = StringIO()
    errors = StringIO()

    result = run_status(
        ["--json"],
        session_factory=BrokenSession,
        now_fn=lambda: NOW,
        stdout=output,
        stderr=errors,
    )

    assert result == 1
    assert output.getvalue() == ""
    assert "projection health query failed" in errors.getvalue()


def test_service_health_interval_reuses_scanner_without_claim_mutation() -> None:
    from src.services.daily_world_projection import DailyWorldProjectionService

    class ReadSession:
        def __init__(self) -> None:
            self.closed = False

        def close(self) -> None:
            self.closed = True

    sessions: list[ReadSession] = []
    snapshots: list[object] = []
    emitted: list[object] = []

    def session_factory() -> ReadSession:
        session = ReadSession()
        sessions.append(session)
        return session

    def summarize(db: ReadSession, now: datetime) -> object:
        assert db is sessions[-1]
        snapshots.append(now)
        return now

    service = DailyWorldProjectionService(
        session_factory=session_factory,
        health_summary_fn=summarize,
        health_emitter=emitted.append,
    )

    service._emit_health_if_due(NOW)
    service._emit_health_if_due(NOW + timedelta(seconds=59))
    service._emit_health_if_due(NOW + timedelta(seconds=60))

    assert snapshots == [NOW, NOW + timedelta(seconds=60)]
    assert emitted == snapshots
    assert len(sessions) == 2
    assert all(session.closed for session in sessions)
