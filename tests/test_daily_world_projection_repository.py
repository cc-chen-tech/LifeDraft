"""Database contracts for versioned daily world projection persistence."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from sqlalchemy import event

from src.database.models import DailyWorldProjection, DailyWorldProjectionAttempt
from src.services.daily_world_projection_repository import (
    DailyWorldProjectionRepository,
    ProjectionIdentity,
    ProjectionSourceHashConflict,
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


def test_controlled_source_replacement_blocks_delayed_generic_ensures_and_terminals(
    db_session, frozen_now
) -> None:
    """Only an ordered source CAS can replace a reprocessable projection row."""

    repo = DailyWorldProjectionRepository(db_session)
    payload = {"story_patch": {"fact_updates": [{"fact": "old"}]}, "option_patches": {}}
    original = repo.ensure_projection(identity(), source_hash="hash-a")
    [claimed] = repo.claim_due(now=frozen_now, worker_id="worker-a", limit=1)
    assert repo.mark_ready(
        claimed.projection_id,
        "worker-a",
        "hash-a",
        payload,
        no_change=False,
    )
    original.coverage_json = {"categories": ["location_updates"]}
    original.error_code = "old_error"
    original.applied_at = frozen_now
    db_session.flush()

    with pytest.raises(ProjectionSourceHashConflict):
        repo.ensure_projection(identity(), source_hash="hash-b")
    assert original.source_hash == "hash-a"
    assert original.status == "ready"

    replacement = repo.replace_projection_source(
        identity(), expected_old_hash="hash-a", new_hash="hash-b"
    )

    assert replacement is not None
    assert replacement.projection_id == original.projection_id
    assert replacement.source_hash == "hash-b"
    assert replacement.status == "pending"
    assert replacement.attempt_count == 0
    assert replacement.next_attempt_at <= frozen_now
    assert replacement.story_patch_json is None
    assert replacement.option_patches_json is None
    assert replacement.coverage_json is None
    assert replacement.error_code is None
    assert replacement.lease_owner is None
    assert replacement.lease_expires_at is None
    assert replacement.applied_at is None

    with pytest.raises(ProjectionSourceHashConflict):
        repo.ensure_projection(identity(), source_hash="hash-a")
    assert replacement.source_hash == "hash-b"
    assert replacement.status == "pending"
    assert (
        repo.replace_projection_source(
            identity(), expected_old_hash="hash-a", new_hash="hash-c"
        )
        is None
    )

    [replacement_claim] = repo.claim_due(now=frozen_now, worker_id="worker-b", limit=1)
    assert replacement_claim.source_hash == "hash-b"
    assert (
        repo.mark_ready(
            replacement_claim.projection_id,
            "worker-b",
            "hash-a",
            payload,
            no_change=False,
        )
        is False
    )
    assert repo.mark_ready(
        replacement_claim.projection_id,
        "worker-b",
        "hash-b",
        payload,
        no_change=False,
    )

    assert repo.mark_applied(replacement.projection_id, "hash-b", frozen_now)
    applied = repo.ensure_projection(identity(), source_hash="hash-b")
    assert applied.source_hash == "hash-b"
    assert applied.status == "applied"
    assert (
        repo.replace_projection_source(
            identity(), expected_old_hash="hash-b", new_hash="hash-c"
        )
        is None
    )
    assert repo.supersede(applied.game_id, applied.event_id, before_revision=2) == 1
    superseded = repo.ensure_projection(identity(), source_hash="hash-b")
    assert superseded.source_hash == "hash-b"
    assert superseded.status == "superseded"
    assert (
        repo.replace_projection_source(
            identity(), expected_old_hash="hash-b", new_hash="hash-d"
        )
        is None
    )


def test_mark_ready_persists_explicit_coverage_argument(db_session, frozen_now) -> None:
    """Coverage evidence is stored from its explicit Task 2 boundary argument."""

    repo = DailyWorldProjectionRepository(db_session)
    task = repo.ensure_projection(identity(), source_hash="hash-a")
    [claimed] = repo.claim_due(now=frozen_now, worker_id="worker-a", limit=1)
    coverage = {
        "requires_nonempty_patch": True,
        "categories": ["location_updates"],
        "evidence": {"location_updates": ["抵达东海"]},
    }

    assert repo.mark_ready(
        claimed.projection_id,
        "worker-a",
        "hash-a",
        {"story_patch": {}, "option_patches": {}},
        no_change=False,
        coverage=coverage,
    )

    db_session.expire_all()
    assert (
        db_session.get(DailyWorldProjection, task.projection_id).coverage_json
        == coverage
    )


def test_claim_due_uses_lease_fencing(db_session, frozen_now) -> None:
    """A live lease prevents another worker from claiming the same due row."""

    repo = DailyWorldProjectionRepository(db_session)
    task = repo.ensure_projection(identity(), source_hash="hash-a")

    claimed = repo.claim_due(now=frozen_now, worker_id="worker-a", limit=1)

    assert [row.projection_id for row in claimed] == [task.projection_id]
    assert repo.claim_due(now=frozen_now, worker_id="worker-b", limit=1) == []


def test_old_source_cannot_renew_or_retry_after_same_worker_reclaims_reset_row(
    db_session, frozen_now
) -> None:
    """A reset does not let a same-worker stale call inherit the new source lease."""

    repo = DailyWorldProjectionRepository(db_session)
    original = repo.ensure_projection(identity(), source_hash="hash-a")
    [first_claim] = repo.claim_due(now=frozen_now, worker_id="worker-a", limit=1)
    old_source_hash = str(first_claim.source_hash)

    replacement = repo.replace_projection_source(
        identity(), expected_old_hash="hash-a", new_hash="hash-b"
    )
    assert replacement is not None
    [replacement_claim] = repo.claim_due(now=frozen_now, worker_id="worker-a", limit=1)
    lease_before = replacement_claim.lease_expires_at
    next_attempt_before = replacement_claim.next_attempt_at

    assert replacement.projection_id == original.projection_id
    assert replacement_claim.source_hash == "hash-b"
    assert (
        repo.renew_lease(
            replacement_claim.projection_id,
            "worker-a",
            frozen_now,
            frozen_now + timedelta(minutes=15),
            source_hash=old_source_hash,
        )
        is False
    )
    assert (
        repo.mark_retryable(
            replacement_claim.projection_id,
            "worker-a",
            "provider_timeout",
            frozen_now + timedelta(minutes=30),
            source_hash=old_source_hash,
        )
        is False
    )

    db_session.expire_all()
    persisted = db_session.get(DailyWorldProjection, replacement_claim.projection_id)
    assert persisted.source_hash == "hash-b"
    assert persisted.status == "running"
    assert persisted.lease_owner == "worker-a"
    assert persisted.lease_expires_at == lease_before
    assert persisted.next_attempt_at == next_attempt_before
    assert persisted.error_code is None


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
            source_hash=claimed.source_hash,
        )
        is False
    )
    assert (
        repo.mark_retryable(
            claimed.projection_id,
            "worker-b",
            "provider_timeout",
            frozen_now + timedelta(minutes=5),
            source_hash=claimed.source_hash,
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


def test_successful_retry_finalization_preserves_source_superseded_outcome(
    db_session, frozen_now
) -> None:
    """A handled source replacement is not a rejected late write."""

    repo = DailyWorldProjectionRepository(db_session)
    task = repo.ensure_projection(identity(), source_hash="hash-a")
    [claimed] = repo.claim_due(now=frozen_now, worker_id="worker-a", limit=1)
    attempt_id = repo.start_attempt(task.projection_id, task.game_id, frozen_now)

    assert repo.mark_retryable_and_finish_attempt(
        claimed.projection_id,
        "worker-a",
        "source_superseded",
        frozen_now + timedelta(minutes=5),
        source_hash=claimed.source_hash,
        attempt_id=attempt_id,
        outcome="source_superseded",
        now=frozen_now,
    )

    attempt = db_session.get(DailyWorldProjectionAttempt, attempt_id)
    assert (attempt.outcome, attempt.error_code) == (
        "source_superseded",
        "source_superseded",
    )


def test_fenced_retry_finalization_records_rejected_late_write(
    db_session, frozen_now
) -> None:
    """A retry CAS rejected after supersede must become durable lease_lost."""

    repo = DailyWorldProjectionRepository(db_session)
    task = repo.ensure_projection(identity(), source_hash="hash-a")
    [claimed] = repo.claim_due(now=frozen_now, worker_id="worker-a", limit=1)
    attempt_id = repo.start_attempt(task.projection_id, task.game_id, frozen_now)
    assert repo.supersede(task.game_id, task.event_id, before_revision=2) == 1

    assert not repo.mark_retryable_and_finish_attempt(
        claimed.projection_id,
        "worker-a",
        "suspicious_empty",
        frozen_now + timedelta(minutes=5),
        source_hash=claimed.source_hash,
        attempt_id=attempt_id,
        outcome="extraction_error",
        now=frozen_now,
    )

    attempt = db_session.get(DailyWorldProjectionAttempt, attempt_id)
    assert (attempt.outcome, attempt.error_code) == ("lease_lost", "lease_lost")


def test_fenced_cancel_finalization_records_rejected_late_write(
    db_session, frozen_now
) -> None:
    """A cancel release rejected after lease loss must become durable lease_lost."""

    repo = DailyWorldProjectionRepository(db_session)
    task = repo.ensure_projection(identity(), source_hash="hash-a")
    [claimed] = repo.claim_due(now=frozen_now, worker_id="worker-a", limit=1)
    attempt_id = repo.start_attempt(task.projection_id, task.game_id, frozen_now)
    assert repo.supersede(task.game_id, task.event_id, before_revision=2) == 1

    assert not repo.release_lease_and_finish_attempt(
        claimed.projection_id,
        "worker-a",
        claimed.source_hash,
        frozen_now,
        attempt_id=attempt_id,
        outcome="cancelled",
        error_code="cancelled",
    )

    attempt = db_session.get(DailyWorldProjectionAttempt, attempt_id)
    assert (attempt.outcome, attempt.error_code) == ("lease_lost", "lease_lost")


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


def test_supersede_retries_when_source_hash_changes_during_update(
    db_session,
) -> None:
    """A controlled source replacement cannot leave an obsolete revision runnable."""

    repo = DailyWorldProjectionRepository(db_session)
    older = repo.ensure_projection(identity(revision=1), source_hash="hash-old")
    db_session.flush()
    source_hash_changed = False

    def replace_source_before_supersede(
        connection, cursor, statement, parameters, context, executemany
    ) -> None:
        nonlocal source_hash_changed
        if source_hash_changed or not statement.startswith(
            "UPDATE daily_world_projections"
        ):
            return
        source_hash_changed = True
        connection.exec_driver_sql(
            "UPDATE daily_world_projections SET source_hash = 'hash-new' "
            "WHERE projection_id = ?",
            (older.projection_id,),
        )

    event.listen(
        db_session.bind,
        "before_cursor_execute",
        replace_source_before_supersede,
    )
    try:
        assert repo.supersede(older.game_id, older.event_id, before_revision=2) == 1
    finally:
        event.remove(
            db_session.bind,
            "before_cursor_execute",
            replace_source_before_supersede,
        )

    assert source_hash_changed is True
    db_session.expire_all()
    persisted = db_session.get(DailyWorldProjection, older.projection_id)
    assert persisted.source_hash == "hash-new"
    assert persisted.status == "superseded"


def test_identical_source_replacement_does_not_reset_a_ready_projection(
    db_session, frozen_now
) -> None:
    """A no-op replacement retains all completed work for the identical source."""

    repo = DailyWorldProjectionRepository(db_session)
    task = repo.ensure_projection(identity(), source_hash="hash-a")
    [claimed] = repo.claim_due(now=frozen_now, worker_id="worker-a", limit=1)
    payload = {
        "story_patch": {"fact_updates": [{"fact": "kept"}]},
        "option_patches": {},
    }
    assert repo.mark_ready(
        claimed.projection_id, "worker-a", "hash-a", payload, no_change=False
    )
    before = db_session.get(DailyWorldProjection, task.projection_id)
    before_attempts = before.attempt_count
    before_updated_at = before.updated_at

    unchanged = repo.replace_projection_source(
        identity(), expected_old_hash="hash-a", new_hash="hash-a"
    )

    assert unchanged is not None
    db_session.expire_all()
    persisted = db_session.get(DailyWorldProjection, task.projection_id)
    assert persisted.status == "ready"
    assert persisted.story_patch_json == payload["story_patch"]
    assert persisted.attempt_count == before_attempts
    assert persisted.updated_at == before_updated_at
