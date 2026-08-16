"""Durable, revision-fenced storage for daily world projection jobs."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any, Mapping, Optional, Protocol, Union

from sqlalchemy import and_, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.database.models import DailyWorldProjection, DailyWorldProjectionAttempt

if TYPE_CHECKING:
    from src.game.world_projection_schema import WorldProjectionPayload


logger = logging.getLogger(__name__)

LEASE_DURATION = timedelta(minutes=5)
CLAIMABLE_STATUSES = ("pending", "failed_retryable")
READY_STATUSES = ("ready", "ready_no_change")
REPROCESSABLE_STATUSES = CLAIMABLE_STATUSES + ("running",) + READY_STATUSES


class JsonModel(Protocol):
    """A typed model that can produce JSON-ready persistence data."""

    def model_dump(self, *, mode: str) -> Any: ...


CoverageInput = Union[Mapping[str, Any], JsonModel]


@dataclass(frozen=True)
class ProjectionIdentity:
    """Stable identity and ordering metadata for one accepted daily event."""

    game_id: int
    event_id: str
    revision: int
    day_index: int
    story_date: Optional[str] = None


class DailyWorldProjectionRepository:
    """Use compare-and-set updates so stale workers cannot publish projections."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def ensure_projection(
        self, identity: ProjectionIdentity, source_hash: str
    ) -> DailyWorldProjection:
        existing = self._find_identity(identity)
        if existing is not None:
            return self._ensure_existing_source(existing, identity, source_hash)

        task = DailyWorldProjection(
            game_id=identity.game_id,
            event_id=identity.event_id,
            revision=identity.revision,
            day_index=identity.day_index,
            story_date=identity.story_date,
            source_hash=source_hash,
            status="pending",
            next_attempt_at=datetime.utcnow(),
        )
        try:
            with self.db.begin_nested():
                self.db.add(task)
                self.db.flush()
        except IntegrityError:
            existing = self._find_identity(identity)
            if existing is None:
                raise
            return self._ensure_existing_source(existing, identity, source_hash)
        return task

    def claim_due(
        self, now: datetime, worker_id: str, limit: int
    ) -> list[DailyWorldProjection]:
        if limit <= 0:
            return []
        candidates = (
            self.db.query(DailyWorldProjection)
            .filter(
                or_(
                    and_(
                        DailyWorldProjection.status.in_(CLAIMABLE_STATUSES),
                        DailyWorldProjection.next_attempt_at <= now,
                    ),
                    and_(
                        DailyWorldProjection.status == "running",
                        DailyWorldProjection.lease_expires_at.is_not(None),
                        DailyWorldProjection.lease_expires_at <= now,
                    ),
                )
            )
            .order_by(
                DailyWorldProjection.next_attempt_at,
                DailyWorldProjection.day_index,
                DailyWorldProjection.projection_id,
            )
            .limit(limit)
            .all()
        )
        claimed_ids: list[int] = []
        for candidate in candidates:
            updated = (
                self.db.query(DailyWorldProjection)
                .filter(
                    DailyWorldProjection.projection_id == candidate.projection_id,
                    DailyWorldProjection.source_hash == candidate.source_hash,
                    or_(
                        and_(
                            DailyWorldProjection.status.in_(CLAIMABLE_STATUSES),
                            DailyWorldProjection.next_attempt_at <= now,
                        ),
                        and_(
                            DailyWorldProjection.status == "running",
                            DailyWorldProjection.lease_expires_at.is_not(None),
                            DailyWorldProjection.lease_expires_at <= now,
                        ),
                    ),
                )
                .update(
                    {
                        DailyWorldProjection.status: "running",
                        DailyWorldProjection.lease_owner: worker_id,
                        DailyWorldProjection.lease_expires_at: now + LEASE_DURATION,
                        DailyWorldProjection.attempt_count: (
                            DailyWorldProjection.attempt_count + 1
                        ),
                        DailyWorldProjection.updated_at: now,
                    },
                    synchronize_session=False,
                )
            )
            if updated == 1:
                claimed_ids.append(int(candidate.projection_id))
            else:
                self._log_fenced("claim_due", int(candidate.projection_id))
        self.db.flush()
        self.db.expire_all()
        return [
            self.db.get(DailyWorldProjection, projection_id)
            for projection_id in claimed_ids
            if self.db.get(DailyWorldProjection, projection_id) is not None
        ]

    def renew_lease(
        self,
        projection_id: int,
        worker_id: str,
        now: datetime,
        lease_until: datetime,
    ) -> bool:
        task = self.db.get(DailyWorldProjection, projection_id)
        if task is None:
            return False
        updated = (
            self.db.query(DailyWorldProjection)
            .filter(
                DailyWorldProjection.projection_id == projection_id,
                DailyWorldProjection.status == "running",
                DailyWorldProjection.lease_owner == worker_id,
                DailyWorldProjection.lease_expires_at > now,
                DailyWorldProjection.source_hash == task.source_hash,
            )
            .update(
                {
                    DailyWorldProjection.lease_expires_at: lease_until,
                    DailyWorldProjection.updated_at: now,
                },
                synchronize_session=False,
            )
        )
        return self._finish_fenced_update("renew_lease", projection_id, updated)

    def mark_ready(
        self,
        projection_id: int,
        worker_id: str,
        source_hash: str,
        payload: "WorldProjectionPayload",
        no_change: bool,
        *,
        coverage: Optional[CoverageInput] = None,
    ) -> bool:
        data = self._payload_data(payload)
        now = datetime.utcnow()
        updated = (
            self.db.query(DailyWorldProjection)
            .filter(
                DailyWorldProjection.projection_id == projection_id,
                DailyWorldProjection.status == "running",
                DailyWorldProjection.lease_owner == worker_id,
                DailyWorldProjection.lease_expires_at > now,
                DailyWorldProjection.source_hash == source_hash,
            )
            .update(
                {
                    DailyWorldProjection.status: (
                        "ready_no_change" if no_change else "ready"
                    ),
                    DailyWorldProjection.story_patch_json: data.get("story_patch"),
                    DailyWorldProjection.option_patches_json: data.get(
                        "option_patches"
                    ),
                    DailyWorldProjection.coverage_json: self._coverage_data(coverage),
                    DailyWorldProjection.error_code: None,
                    DailyWorldProjection.lease_owner: None,
                    DailyWorldProjection.lease_expires_at: None,
                    DailyWorldProjection.updated_at: now,
                },
                synchronize_session=False,
            )
        )
        return self._finish_fenced_update("mark_ready", projection_id, updated)

    def mark_retryable(
        self,
        projection_id: int,
        worker_id: str,
        error_code: str,
        next_attempt_at: datetime,
    ) -> bool:
        task = self.db.get(DailyWorldProjection, projection_id)
        if task is None:
            return False
        now = datetime.utcnow()
        updated = (
            self.db.query(DailyWorldProjection)
            .filter(
                DailyWorldProjection.projection_id == projection_id,
                DailyWorldProjection.status == "running",
                DailyWorldProjection.lease_owner == worker_id,
                DailyWorldProjection.lease_expires_at > now,
                DailyWorldProjection.source_hash == task.source_hash,
            )
            .update(
                {
                    DailyWorldProjection.status: "failed_retryable",
                    DailyWorldProjection.error_code: error_code,
                    DailyWorldProjection.next_attempt_at: next_attempt_at,
                    DailyWorldProjection.lease_owner: None,
                    DailyWorldProjection.lease_expires_at: None,
                    DailyWorldProjection.updated_at: now,
                },
                synchronize_session=False,
            )
        )
        return self._finish_fenced_update("mark_retryable", projection_id, updated)

    def mark_applied(
        self, projection_id: int, source_hash: str, applied_at: datetime
    ) -> bool:
        updated = (
            self.db.query(DailyWorldProjection)
            .filter(
                DailyWorldProjection.projection_id == projection_id,
                DailyWorldProjection.status.in_(READY_STATUSES),
                DailyWorldProjection.source_hash == source_hash,
            )
            .update(
                {
                    DailyWorldProjection.status: "applied",
                    DailyWorldProjection.applied_at: applied_at,
                    DailyWorldProjection.updated_at: applied_at,
                },
                synchronize_session=False,
            )
        )
        return self._finish_fenced_update("mark_applied", projection_id, updated)

    def supersede(self, game_id: int, event_id: str, before_revision: int) -> int:
        candidates = (
            self.db.query(
                DailyWorldProjection.projection_id,
                DailyWorldProjection.game_id,
                DailyWorldProjection.event_id,
                DailyWorldProjection.revision,
                DailyWorldProjection.source_hash,
            )
            .filter(
                DailyWorldProjection.game_id == game_id,
                DailyWorldProjection.event_id == event_id,
                DailyWorldProjection.revision < before_revision,
                DailyWorldProjection.status != "superseded",
            )
            .all()
        )
        now = datetime.utcnow()
        updated_count = 0
        for candidate in candidates:
            updated = (
                self.db.query(DailyWorldProjection)
                .filter(
                    DailyWorldProjection.projection_id == candidate.projection_id,
                    DailyWorldProjection.game_id == candidate.game_id,
                    DailyWorldProjection.event_id == candidate.event_id,
                    DailyWorldProjection.revision == candidate.revision,
                    DailyWorldProjection.source_hash == candidate.source_hash,
                    DailyWorldProjection.status != "superseded",
                )
                .update(
                    {
                        DailyWorldProjection.status: "superseded",
                        DailyWorldProjection.lease_owner: None,
                        DailyWorldProjection.lease_expires_at: None,
                        DailyWorldProjection.updated_at: now,
                    },
                    synchronize_session=False,
                )
            )
            updated_count += int(updated)
            if updated == 0:
                self._log_fenced("supersede", int(candidate.projection_id))
        self.db.flush()
        self.db.expire_all()
        return updated_count

    def start_attempt(self, projection_id: int, game_id: int, now: datetime) -> int:
        attempt = DailyWorldProjectionAttempt(
            projection_id=projection_id,
            game_id=game_id,
            started_at=now,
            outcome="running",
        )
        self.db.add(attempt)
        self.db.flush()
        return int(attempt.attempt_id)

    def finish_attempt(
        self,
        attempt_id: int,
        outcome: str,
        error_code: Optional[str],
        now: datetime,
    ) -> None:
        updated = (
            self.db.query(DailyWorldProjectionAttempt)
            .filter(
                DailyWorldProjectionAttempt.attempt_id == attempt_id,
                DailyWorldProjectionAttempt.outcome == "running",
            )
            .update(
                {
                    DailyWorldProjectionAttempt.finished_at: now,
                    DailyWorldProjectionAttempt.outcome: outcome,
                    DailyWorldProjectionAttempt.error_code: error_code,
                },
                synchronize_session=False,
            )
        )
        self.db.flush()
        if updated == 0:
            logger.warning(
                "daily_world_projection_fenced_write action=finish_attempt attempt_id=%s",
                attempt_id,
            )

    def count_game_attempts_between(
        self, game_id: int, start: datetime, end: datetime
    ) -> int:
        return int(
            self.db.query(DailyWorldProjectionAttempt)
            .filter(
                DailyWorldProjectionAttempt.game_id == game_id,
                DailyWorldProjectionAttempt.started_at >= start,
                DailyWorldProjectionAttempt.started_at <= end,
            )
            .count()
        )

    def _find_identity(
        self, identity: ProjectionIdentity
    ) -> Optional[DailyWorldProjection]:
        return (
            self.db.query(DailyWorldProjection)
            .filter(
                DailyWorldProjection.game_id == identity.game_id,
                DailyWorldProjection.event_id == identity.event_id,
                DailyWorldProjection.revision == identity.revision,
            )
            .one_or_none()
        )

    def _ensure_existing_source(
        self,
        existing: DailyWorldProjection,
        identity: ProjectionIdentity,
        source_hash: str,
    ) -> DailyWorldProjection:
        """Reset only a still-reprocessable row whose accepted source changed."""

        for _ in range(3):
            if existing.source_hash == source_hash:
                return existing
            if existing.status not in REPROCESSABLE_STATUSES:
                return existing
            now = datetime.utcnow()
            updated = (
                self.db.query(DailyWorldProjection)
                .filter(
                    DailyWorldProjection.projection_id == existing.projection_id,
                    DailyWorldProjection.game_id == identity.game_id,
                    DailyWorldProjection.event_id == identity.event_id,
                    DailyWorldProjection.revision == identity.revision,
                    DailyWorldProjection.source_hash == existing.source_hash,
                    DailyWorldProjection.status.in_(REPROCESSABLE_STATUSES),
                )
                .update(
                    {
                        DailyWorldProjection.day_index: identity.day_index,
                        DailyWorldProjection.story_date: identity.story_date,
                        DailyWorldProjection.source_hash: source_hash,
                        DailyWorldProjection.status: "pending",
                        DailyWorldProjection.story_patch_json: None,
                        DailyWorldProjection.option_patches_json: None,
                        DailyWorldProjection.coverage_json: None,
                        DailyWorldProjection.attempt_count: 0,
                        DailyWorldProjection.next_attempt_at: now,
                        DailyWorldProjection.lease_owner: None,
                        DailyWorldProjection.lease_expires_at: None,
                        DailyWorldProjection.error_code: None,
                        DailyWorldProjection.applied_at: None,
                        DailyWorldProjection.updated_at: now,
                    },
                    synchronize_session=False,
                )
            )
            self.db.flush()
            self.db.expire_all()
            if updated == 1:
                reset = self.db.get(DailyWorldProjection, existing.projection_id)
                if reset is not None:
                    return reset
            self._log_fenced("ensure_projection", int(existing.projection_id))
            refreshed = self._find_identity(identity)
            if refreshed is None:
                break
            existing = refreshed
        return existing

    @staticmethod
    def _payload_data(payload: "WorldProjectionPayload") -> dict[str, Any]:
        if hasattr(payload, "model_dump"):
            return payload.model_dump(mode="json")
        if isinstance(payload, dict):
            return dict(payload)
        raise TypeError("world_projection_payload_must_be_serializable")

    @staticmethod
    def _coverage_data(coverage: Optional[CoverageInput]) -> Optional[dict[str, Any]]:
        if coverage is None:
            return None
        if isinstance(coverage, Mapping):
            return dict(coverage)
        data = coverage.model_dump(mode="json")
        if isinstance(data, Mapping):
            return dict(data)
        raise TypeError("world_projection_coverage_must_be_a_mapping")

    def _finish_fenced_update(
        self, action: str, projection_id: int, updated: int
    ) -> bool:
        self.db.flush()
        self.db.expire_all()
        if updated != 1:
            self._log_fenced(action, projection_id)
            return False
        return True

    @staticmethod
    def _log_fenced(action: str, projection_id: int) -> None:
        logger.warning(
            "daily_world_projection_fenced_write action=%s projection_id=%s",
            action,
            projection_id,
        )
