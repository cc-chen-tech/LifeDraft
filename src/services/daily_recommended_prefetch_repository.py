"""Database ownership and fencing for recommended daily prefetch jobs."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Optional
from uuid import uuid4

from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.database.models import DailyRecommendedPrefetch


LEASE_DURATION = timedelta(minutes=5)
TERMINAL_STATUSES = {"failed", "invalidated", "consumed"}


class DailyRecommendedPrefetchRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def enqueue(
        self,
        *,
        game_id: int,
        user_id: Optional[int],
        event_id: str,
        revision: int,
        day_index: int,
        option_index: int,
        state_fingerprint: str,
        voice_id: Optional[str] = None,
        voice_speed: Optional[float] = None,
    ) -> DailyRecommendedPrefetch:
        existing = self.find_valid(
            game_id=game_id,
            user_id=user_id,
            event_id=event_id,
            revision=revision,
            day_index=day_index,
            option_index=option_index,
            state_fingerprint=state_fingerprint,
        )
        if existing is not None:
            return existing
        task = DailyRecommendedPrefetch(
            game_id=game_id,
            user_id=user_id,
            event_id=event_id,
            revision=revision,
            day_index=day_index,
            option_index=option_index,
            state_fingerprint=state_fingerprint,
            status="queued",
            voice_id=voice_id,
            voice_speed=voice_speed,
        )
        self.db.add(task)
        try:
            self.db.flush()
        except IntegrityError:
            self.db.rollback()
            existing = self.find_valid(
                game_id=game_id,
                user_id=user_id,
                event_id=event_id,
                revision=revision,
                day_index=day_index,
                option_index=option_index,
                state_fingerprint=state_fingerprint,
            )
            if existing is None:
                raise
            return existing
        return task

    def find_valid(
        self,
        *,
        game_id: int,
        event_id: str,
        revision: int,
        option_index: int,
        state_fingerprint: str,
        user_id: Optional[int] = None,
        day_index: Optional[int] = None,
    ) -> Optional[DailyRecommendedPrefetch]:
        query = self.db.query(DailyRecommendedPrefetch).filter(
            DailyRecommendedPrefetch.game_id == game_id,
            DailyRecommendedPrefetch.event_id == event_id,
            DailyRecommendedPrefetch.revision == revision,
            DailyRecommendedPrefetch.option_index == option_index,
            DailyRecommendedPrefetch.state_fingerprint == state_fingerprint,
        )
        if user_id is not None:
            query = query.filter(DailyRecommendedPrefetch.user_id == user_id)
        if day_index is not None:
            query = query.filter(DailyRecommendedPrefetch.day_index == day_index)
        return query.one_or_none()

    def find_demanded_after_choice(
        self,
        *,
        game_id: int,
        event_id: str,
        revision: int,
        option_index: int,
        day_index: int,
    ) -> Optional[DailyRecommendedPrefetch]:
        """Find the durable speculative job joined by a committed daily choice."""

        return (
            self.db.query(DailyRecommendedPrefetch)
            .filter(
                DailyRecommendedPrefetch.game_id == game_id,
                DailyRecommendedPrefetch.event_id == event_id,
                DailyRecommendedPrefetch.revision == revision,
                DailyRecommendedPrefetch.option_index == option_index,
                DailyRecommendedPrefetch.day_index == day_index,
                DailyRecommendedPrefetch.demanded.is_(True),
            )
            .order_by(DailyRecommendedPrefetch.prefetch_id.desc())
            .first()
        )

    def claim(self, prefetch_id: int) -> Optional[str]:
        now = datetime.utcnow()
        token = uuid4().hex
        updated = (
            self.db.query(DailyRecommendedPrefetch)
            .filter(
                DailyRecommendedPrefetch.prefetch_id == prefetch_id,
                or_(
                    DailyRecommendedPrefetch.status == "queued",
                    (
                        (DailyRecommendedPrefetch.status == "processing")
                        & or_(
                            DailyRecommendedPrefetch.lease_expires_at.is_(None),
                            DailyRecommendedPrefetch.lease_expires_at < now,
                        )
                    ),
                ),
            )
            .update(
                {
                    DailyRecommendedPrefetch.status: "processing",
                    DailyRecommendedPrefetch.lease_token: token,
                    DailyRecommendedPrefetch.lease_expires_at: now + LEASE_DURATION,
                    DailyRecommendedPrefetch.updated_at: now,
                },
                synchronize_session=False,
            )
        )
        self.db.flush()
        self.db.expire_all()
        return token if updated == 1 else None

    def mark_story_ready(
        self, prefetch_id: int, lease_token: str, next_event_json: dict[str, Any]
    ) -> bool:
        updated = (
            self.db.query(DailyRecommendedPrefetch)
            .filter(
                DailyRecommendedPrefetch.prefetch_id == prefetch_id,
                DailyRecommendedPrefetch.status == "processing",
                DailyRecommendedPrefetch.lease_token == lease_token,
            )
            .update(
                {
                    DailyRecommendedPrefetch.status: "story_ready",
                    DailyRecommendedPrefetch.next_event_json: next_event_json,
                    DailyRecommendedPrefetch.lease_token: None,
                    DailyRecommendedPrefetch.lease_expires_at: None,
                    DailyRecommendedPrefetch.updated_at: datetime.utcnow(),
                },
                synchronize_session=False,
            )
        )
        self.db.flush()
        self.db.expire_all()
        return updated == 1

    def mark_failed(self, prefetch_id: int, lease_token: str, error: Exception) -> bool:
        updated = (
            self.db.query(DailyRecommendedPrefetch)
            .filter(
                DailyRecommendedPrefetch.prefetch_id == prefetch_id,
                DailyRecommendedPrefetch.lease_token == lease_token,
            )
            .update(
                {
                    DailyRecommendedPrefetch.status: "failed",
                    DailyRecommendedPrefetch.error_code: "prefetch_generation_failed",
                    DailyRecommendedPrefetch.error_message: str(error)[:1000],
                    DailyRecommendedPrefetch.lease_token: None,
                    DailyRecommendedPrefetch.lease_expires_at: None,
                    DailyRecommendedPrefetch.updated_at: datetime.utcnow(),
                },
                synchronize_session=False,
            )
        )
        self.db.flush()
        self.db.expire_all()
        return updated == 1

    def attach_tts(
        self,
        prefetch_id: int,
        *,
        job_id: int,
        voice_id: str,
        speed: float,
        ready: bool,
    ) -> bool:
        task = self.db.get(DailyRecommendedPrefetch, prefetch_id)
        if task is None or task.status in {"failed", "invalidated"}:
            return False
        setattr(task, "tts_job_id", job_id)
        setattr(task, "voice_id", voice_id)
        setattr(task, "voice_speed", speed)
        if ready and task.status == "story_ready":
            setattr(task, "status", "ready")
        self.db.flush()
        return True

    def consume_if_ready(
        self,
        *,
        game_id: int,
        event_id: str,
        revision: int,
        option_index: int,
        state_fingerprint: str,
    ) -> Optional[DailyRecommendedPrefetch]:
        task = self.find_valid(
            game_id=game_id,
            event_id=event_id,
            revision=revision,
            option_index=option_index,
            state_fingerprint=state_fingerprint,
        )
        if task is None or task.status not in {"story_ready", "ready"}:
            return None
        setattr(task, "status", "consumed")
        setattr(task, "demanded", True)
        setattr(task, "consumed_at", datetime.utcnow())
        self.db.flush()
        return task

    def consume_task(self, prefetch_id: int) -> bool:
        task = self.db.get(DailyRecommendedPrefetch, prefetch_id)
        if task is None or task.status not in {"story_ready", "ready"}:
            return False
        setattr(task, "status", "consumed")
        setattr(task, "demanded", True)
        setattr(task, "consumed_at", datetime.utcnow())
        self.db.flush()
        return True

    def mark_demanded(
        self,
        *,
        game_id: int,
        event_id: str,
        revision: int,
        option_index: int,
        state_fingerprint: str,
    ) -> Optional[DailyRecommendedPrefetch]:
        task = self.find_valid(
            game_id=game_id,
            event_id=event_id,
            revision=revision,
            option_index=option_index,
            state_fingerprint=state_fingerprint,
        )
        if task is not None and task.status not in TERMINAL_STATUSES:
            setattr(task, "demanded", True)
            self.db.flush()
        return task

    def invalidate_event(
        self,
        *,
        game_id: int,
        event_id: str,
        revision: int,
        selected_option_index: Optional[int] = None,
    ) -> int:
        query = self.db.query(DailyRecommendedPrefetch).filter(
            DailyRecommendedPrefetch.game_id == game_id,
            DailyRecommendedPrefetch.event_id == event_id,
            DailyRecommendedPrefetch.revision == revision,
            DailyRecommendedPrefetch.status.notin_(TERMINAL_STATUSES),
        )
        if selected_option_index is not None:
            query = query.filter(
                DailyRecommendedPrefetch.option_index != selected_option_index
            )
        updated = query.update(
            {
                DailyRecommendedPrefetch.status: "invalidated",
                DailyRecommendedPrefetch.lease_token: None,
                DailyRecommendedPrefetch.lease_expires_at: None,
                DailyRecommendedPrefetch.updated_at: datetime.utcnow(),
            },
            synchronize_session=False,
        )
        self.db.flush()
        self.db.expire_all()
        return int(updated)
