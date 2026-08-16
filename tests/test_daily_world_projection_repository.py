"""Database contracts for versioned daily world projection persistence."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from sqlalchemy import event

from src.database.models import DailyWorldProjection
from src.services.daily_world_projection_repository import (
    DailyWorldProjectionRepository,
    ProjectionIdentity,
)


@pytest.fixture
def frozen_now() -> datetime:
    """Use a near-future instant so newly enqueued work is due."""

    return datetime.utcnow() + timedelta(minutes=1)


def identity(*, revision: int = 1) -> ProjectionIdentity:
    return ProjectionIdentity(
        game_id=73,
        event_id="daily-event-73",
        revision=revision,
        day_index=4,
        story_date="2026-08-16",
    )


def test_projection_identity_is_unique(db_session) -> None:
    """A replayed accepted event must reuse its one durable projection row."""

    repo = DailyWorldProjectionRepository(db_session)

    first = repo.ensure_projection(identity(), source_hash="hash-a")
    second = repo.ensure_projection(identity(), source_hash="hash-a")
    db_session.commit()

    assert first.projection_id == second.projection_id
    assert db_session.query(DailyWorldProjection).count() == 1


def test_claim_due_uses_lease_fencing(db_session, frozen_now) -> None:
    """A live lease prevents another worker from claiming the same due row."""

    repo = DailyWorldProjectionRepository(db_session)
    task = repo.ensure_projection(identity(), source_hash="hash-a")

    claimed = repo.claim_due(now=frozen_now, worker_id="worker-a", limit=1)

    assert [row.projection_id for row in claimed] == [task.projection_id]
    assert repo.claim_due(now=frozen_now, worker_id="worker-b", limit=1) == []


def test_worker_and_source_hash_fence_late_projection_writes(
    db_session, frozen_now
) -> None:
    """Expired or replaced workers cannot change a projection they no longer own."""

    repo = DailyWorldProjectionRepository(db_session)
    task = repo.ensure_projection(identity(), source_hash="hash-a")
    [claimed] = repo.claim_due(now=frozen_now, worker_id="worker-a", limit=1)

    assert (
        repo.renew_lease(
            claimed.projection_id,
            "worker-b",
            frozen_now,
            frozen_now + timedelta(minutes=2),
        )
        is False
    )
    assert (
        repo.mark_retryable(
            claimed.projection_id,
            "worker-b",
            "provider_timeout",
            frozen_now + timedelta(minutes=5),
        )
        is False
    )
    assert (
        repo.mark_applied(
            claimed.projection_id,
            "hash-b",
            frozen_now,
        )
        is False
    )


def test_attempt_ledger_counts_only_requested_window(db_session, frozen_now) -> None:
    """Rate limiting derives from individual calls, not a projection total."""

    repo = DailyWorldProjectionRepository(db_session)
    task = repo.ensure_projection(identity(), source_hash="hash-a")
    attempt_id = repo.start_attempt(task.projection_id, task.game_id, frozen_now)
    repo.finish_attempt(attempt_id, "suspicious_empty", "suspicious_empty", frozen_now)
    outside = repo.start_attempt(
        task.projection_id,
        task.game_id,
        frozen_now + timedelta(hours=2),
    )
    repo.finish_attempt(outside, "ready", None, frozen_now + timedelta(hours=2))

    assert (
        repo.count_game_attempts_between(
            task.game_id,
            frozen_now - timedelta(minutes=1),
            frozen_now + timedelta(minutes=1),
        )
        == 1
    )


def test_supersede_only_fences_older_revisions(db_session) -> None:
    """Replacing a story invalidates only older projection revisions."""

    repo = DailyWorldProjectionRepository(db_session)
    older = repo.ensure_projection(identity(revision=1), source_hash="hash-old")
    current = repo.ensure_projection(identity(revision=2), source_hash="hash-current")

    assert repo.supersede(older.game_id, older.event_id, before_revision=2) == 1
    assert (
        db_session.get(DailyWorldProjection, older.projection_id).status == "superseded"
    )
    assert (
        db_session.get(DailyWorldProjection, current.projection_id).status == "pending"
    )


def test_supersede_fences_an_old_revision_that_becomes_ready_during_update(
    db_session,
) -> None:
    """A worker completion between scan and write cannot leave an old revision ready."""

    repo = DailyWorldProjectionRepository(db_session)
    older = repo.ensure_projection(identity(revision=1), source_hash="hash-old")
    db_session.flush()
    switched_to_ready = False

    def mark_ready_before_supersede(
        connection, cursor, statement, parameters, context, executemany
    ) -> None:
        nonlocal switched_to_ready
        if switched_to_ready or not statement.startswith(
            "UPDATE daily_world_projections"
        ):
            return
        switched_to_ready = True
        connection.exec_driver_sql(
            "UPDATE daily_world_projections SET status = 'ready' WHERE projection_id = ?",
            (older.projection_id,),
        )

    event.listen(
        db_session.bind,
        "before_cursor_execute",
        mark_ready_before_supersede,
    )
    try:
        assert repo.supersede(older.game_id, older.event_id, before_revision=2) == 1
    finally:
        event.remove(
            db_session.bind,
            "before_cursor_execute",
            mark_ready_before_supersede,
        )

    assert switched_to_ready is True
    db_session.expire_all()
    assert (
        db_session.get(DailyWorldProjection, older.projection_id).status == "superseded"
    )
