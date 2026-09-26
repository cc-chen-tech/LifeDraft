"""Persistence helpers for story voice reading."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, Optional, Sequence

from sqlalchemy import or_
from sqlalchemy.orm import Session

from src.database.models import (
    DailyRecommendedPrefetch,
    GeneratedVoiceAsset,
    VOICE_ASSET_VERSION,
    VoiceReadingJob,
    VoiceReadingProgress,
    VoiceReadingSegment,
    VoiceReadingSetting,
)

PROCESSING_LEASE_DURATION = timedelta(minutes=10)


class StoryVoiceReadingRepository:
    """Repository for voice settings, narration jobs, and generated assets."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_settings(self, user_id: int) -> Optional[VoiceReadingSetting]:
        return (
            self.db.query(VoiceReadingSetting)
            .filter(VoiceReadingSetting.user_id == user_id)
            .one_or_none()
        )

    def upsert_settings(
        self,
        user_id: int,
        selected_voice_color: Optional[str],
        auto_read_enabled: Optional[bool],
        selected_speed: Optional[float] = None,
    ) -> VoiceReadingSetting:
        setting = self.get_settings(user_id)
        if setting is None:
            setting = VoiceReadingSetting(user_id=user_id)
            self.db.add(setting)

        if selected_voice_color is not None:
            setattr(setting, "selected_voice_color", selected_voice_color)
        if auto_read_enabled is not None:
            setattr(setting, "auto_read_enabled", auto_read_enabled)
        if selected_speed is not None:
            setattr(setting, "selected_speed", selected_speed)
        self.db.flush()
        return setting

    def find_ready_asset(
        self,
        text_hash: str,
        voice_id: str,
        speed: float,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        user_id: Optional[int] = None,
    ) -> Optional[GeneratedVoiceAsset]:
        query = self.db.query(GeneratedVoiceAsset).filter(
            GeneratedVoiceAsset.text_hash == text_hash,
            GeneratedVoiceAsset.voice_id == voice_id,
            GeneratedVoiceAsset.speed == speed,
            GeneratedVoiceAsset.status == "ready",
            GeneratedVoiceAsset.asset_version == VOICE_ASSET_VERSION,
        )
        if provider is not None:
            query = query.filter(GeneratedVoiceAsset.provider == provider)
        if model is not None:
            query = query.filter(GeneratedVoiceAsset.model == model)
        if user_id is not None:
            query = query.filter(GeneratedVoiceAsset.user_id == user_id)
        return query.order_by(GeneratedVoiceAsset.created_at.desc()).first()

    def create_asset(
        self,
        user_id: int,
        context: Dict[str, Any],
        voice_id: str,
        speed: float,
        provider: str,
        model: str,
        storage_path: str,
        duration_ms: int,
        status: str,
    ) -> GeneratedVoiceAsset:
        asset = GeneratedVoiceAsset(
            user_id=user_id,
            source_type=str(context["source_type"]),
            context_json=context,
            text_hash=str(context["text_hash"]),
            voice_id=voice_id,
            speed=speed,
            provider=provider,
            model=model,
            storage_path=storage_path,
            duration_ms=duration_ms,
            asset_version=VOICE_ASSET_VERSION,
            status=status,
        )
        self.db.add(asset)
        self.db.flush()
        return asset

    def create_job(
        self,
        user_id: int,
        context: Dict[str, Any],
        voice_id: str,
        speed: float,
        status: str,
        asset_id: Optional[int] = None,
        error_code: Optional[str] = None,
        error_message: Optional[str] = None,
        dedupe_key: Optional[str] = None,
    ) -> VoiceReadingJob:
        job = VoiceReadingJob(
            user_id=user_id,
            asset_id=asset_id,
            context_json=context,
            text_hash=str(context["text_hash"]),
            voice_id=voice_id,
            speed=speed,
            asset_version=VOICE_ASSET_VERSION,
            status=status,
            error_code=error_code,
            error_message=error_message,
            dedupe_key=dedupe_key,
        )
        self.db.add(job)
        self.db.flush()
        return job

    def find_job_by_dedupe_key(self, dedupe_key: str) -> Optional[VoiceReadingJob]:
        return (
            self.db.query(VoiceReadingJob)
            .filter(VoiceReadingJob.dedupe_key == dedupe_key)
            .one_or_none()
        )

    def create_chapter_job(
        self,
        *,
        user_id: int,
        context: Dict[str, Any],
        voice_id: str,
        speed: float,
        dedupe_key: str,
        paragraphs: Sequence[str],
    ) -> VoiceReadingJob:
        job = self.create_job(
            user_id=user_id,
            context=context,
            voice_id=voice_id,
            speed=speed,
            status="queued",
            dedupe_key=dedupe_key,
        )
        for index, paragraph in enumerate(paragraphs):
            job.segments.append(
                VoiceReadingSegment(
                    paragraph_index=index,
                    text_hash=_normalize_text_hash(paragraph),
                    text_content=paragraph,
                    status="queued",
                )
            )
        self.db.flush()
        return job

    def get_job(self, job_id: int, user_id: int) -> Optional[VoiceReadingJob]:
        return (
            self.db.query(VoiceReadingJob)
            .filter(VoiceReadingJob.job_id == job_id, VoiceReadingJob.user_id == user_id)
            .one_or_none()
        )

    def claim_queued_job_for_processing(self, user_id: int, job_id: int) -> bool:
        """Atomically transition a queued job to processing for one worker."""
        return self.claim_queued_job_for_processing_with_token(user_id, job_id) is not None

    def claim_queued_job_for_processing_with_token(
        self, user_id: int, job_id: int
    ) -> Optional[datetime]:
        """Claim a queued job and return its committed lease fencing token."""
        now = datetime.utcnow()
        claimed = (
            self.db.query(VoiceReadingJob)
            .filter(
                VoiceReadingJob.job_id == job_id,
                VoiceReadingJob.user_id == user_id,
                VoiceReadingJob.status == "queued",
            )
            .update(
                {
                    VoiceReadingJob.status: "processing",
                    VoiceReadingJob.updated_at: now,
                },
                synchronize_session=False,
            )
        )
        self.db.commit()
        if claimed != 1:
            return None
        self.db.expire_all()
        return now

    def requeue_stale_processing_job(
        self,
        user_id: int,
        job_id: int,
        *,
        now: Optional[datetime] = None,
    ) -> bool:
        """Atomically recover a processing job whose worker lease expired."""
        current_time = now or datetime.utcnow()
        stale_before = current_time - PROCESSING_LEASE_DURATION
        recovered = (
            self.db.query(VoiceReadingJob)
            .filter(
                VoiceReadingJob.job_id == job_id,
                VoiceReadingJob.user_id == user_id,
                VoiceReadingJob.status == "processing",
                or_(
                    VoiceReadingJob.updated_at.is_(None),
                    VoiceReadingJob.updated_at < stale_before,
                ),
            )
            .update(
                {
                    VoiceReadingJob.status: "queued",
                    VoiceReadingJob.error_code: None,
                    VoiceReadingJob.error_message: None,
                    VoiceReadingJob.updated_at: current_time,
                },
                synchronize_session="fetch",
            )
        )
        self.db.flush()
        return recovered == 1

    def recover_abandoned_job(self, user_id: int, job_id: int) -> bool:
        """Recover at most twice, with the counter in existing job metadata.

        The old timestamp is compared along with status, so concurrent scanners
        cannot both increment the counter or replace a live worker's lease.
        """
        job = self.get_job(job_id, user_id)
        now = datetime.utcnow()
        if (
            job is None
            or job.status != "processing"
            or (job.updated_at is not None and job.updated_at >= now - PROCESSING_LEASE_DURATION)
        ):
            self.db.rollback()
            return False
        context = dict(job.context_json)
        attempts = context.get("_voice_worker_recoveries", 0)
        attempts = attempts if isinstance(attempts, int) and attempts >= 0 else 0
        if attempts >= 2:
            return self.fail_stale_processing_job(user_id, job_id, now=now)
        context["_voice_worker_recoveries"] = attempts + 1
        recovered = (
            self.db.query(VoiceReadingJob)
            .filter(
                VoiceReadingJob.job_id == job_id,
                VoiceReadingJob.user_id == user_id,
                VoiceReadingJob.status == "processing",
                VoiceReadingJob.updated_at == job.updated_at,
            )
            .update(
                {
                    VoiceReadingJob.status: "queued",
                    VoiceReadingJob.context_json: context,
                    VoiceReadingJob.updated_at: now,
                    VoiceReadingJob.error_code: None,
                    VoiceReadingJob.error_message: None,
                },
                synchronize_session=False,
            )
        )
        if recovered == 1:
            self.db.query(VoiceReadingSegment).filter(
                VoiceReadingSegment.job_id == job_id,
                VoiceReadingSegment.status != "ready",
            ).update({VoiceReadingSegment.status: "queued"}, synchronize_session=False)
        self.db.commit()
        self.db.expire_all()
        return recovered == 1

    def force_requeue_processing_job(
        self,
        user_id: int,
        job_id: int,
        *,
        now: Optional[datetime] = None,
    ) -> bool:
        """Requeue a still-processing job after an explicit user retry."""
        current_time = now or datetime.utcnow()
        requeued = (
            self.db.query(VoiceReadingJob)
            .filter(
                VoiceReadingJob.job_id == job_id,
                VoiceReadingJob.user_id == user_id,
                VoiceReadingJob.status == "processing",
            )
            .update(
                {
                    VoiceReadingJob.status: "queued",
                    VoiceReadingJob.error_code: None,
                    VoiceReadingJob.error_message: None,
                    VoiceReadingJob.updated_at: current_time,
                },
                synchronize_session=False,
            )
        )
        if requeued != 1:
            return False
        self.db.query(VoiceReadingSegment).filter(
            VoiceReadingSegment.job_id == job_id,
            VoiceReadingSegment.status != "ready",
        ).update(
            {
                VoiceReadingSegment.status: "queued",
                VoiceReadingSegment.error_code: None,
                VoiceReadingSegment.error_message: None,
                VoiceReadingSegment.updated_at: current_time,
            },
            synchronize_session=False,
        )
        self.db.flush()
        self.db.expire_all()
        return True

    def fail_stale_processing_job(
        self,
        user_id: int,
        job_id: int,
        *,
        now: Optional[datetime] = None,
    ) -> bool:
        """Put an abandoned processing job into a durable terminal state."""
        current_time = now or datetime.utcnow()
        stale_before = current_time - PROCESSING_LEASE_DURATION
        failed = (
            self.db.query(VoiceReadingJob)
            .filter(
                VoiceReadingJob.job_id == job_id,
                VoiceReadingJob.user_id == user_id,
                VoiceReadingJob.status == "processing",
                or_(
                    VoiceReadingJob.updated_at.is_(None),
                    VoiceReadingJob.updated_at < stale_before,
                ),
            )
            .update(
                {
                    VoiceReadingJob.status: "failed",
                    VoiceReadingJob.error_code: "tts_processing_timeout",
                    VoiceReadingJob.error_message: (
                        "High-quality narration processing expired; please retry"
                    ),
                    VoiceReadingJob.updated_at: current_time,
                },
                synchronize_session=False,
            )
        )
        if failed != 1:
            return False
        self.db.query(VoiceReadingSegment).filter(
            VoiceReadingSegment.job_id == job_id,
            VoiceReadingSegment.status != "ready",
        ).update(
            {
                VoiceReadingSegment.status: "failed",
                VoiceReadingSegment.error_code: "tts_processing_timeout",
                VoiceReadingSegment.error_message: (
                    "High-quality narration processing expired; please retry"
                ),
                VoiceReadingSegment.updated_at: current_time,
            },
            synchronize_session=False,
        )
        self.db.commit()
        self.db.expire_all()
        return True

    def commit_processing_changes(
        self,
        user_id: int,
        job_id: int,
        lease_token: datetime,
        *,
        primary_asset_id: Optional[int] = None,
        terminal_status: Optional[str] = None,
        error_code: Optional[str] = None,
        error_message: Optional[str] = None,
        context_json: Optional[Dict[str, Any]] = None,
    ) -> Optional[datetime]:
        """Commit pending worker changes only while its exact lease token is current."""
        try:
            now = datetime.utcnow()
            updates: Dict[Any, Any] = {VoiceReadingJob.updated_at: now}
            if context_json is not None:
                updates[VoiceReadingJob.context_json] = context_json
            if primary_asset_id is not None:
                updates[VoiceReadingJob.asset_id] = primary_asset_id
            if terminal_status is not None:
                updates[VoiceReadingJob.status] = terminal_status
                updates[VoiceReadingJob.error_code] = error_code
                updates[VoiceReadingJob.error_message] = error_message
            committed = (
                self.db.query(VoiceReadingJob)
                .filter(
                    VoiceReadingJob.job_id == job_id,
                    VoiceReadingJob.user_id == user_id,
                    VoiceReadingJob.status == "processing",
                    VoiceReadingJob.updated_at == lease_token,
                )
                .update(updates, synchronize_session=False)
            )
            if committed != 1:
                self.db.rollback()
                return None
            if terminal_status == "ready":
                # The story stays consumable while narration is queued. Promote
                # only its still-current attached job, in the fenced commit.
                self.db.query(DailyRecommendedPrefetch).filter(
                    DailyRecommendedPrefetch.tts_job_id == job_id,
                    DailyRecommendedPrefetch.user_id == user_id,
                    DailyRecommendedPrefetch.status == "story_ready",
                ).update({DailyRecommendedPrefetch.status: "ready"}, synchronize_session=False)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        self.db.expire_all()
        return now

    def invalidate_asset(self, asset: GeneratedVoiceAsset, reason: str) -> None:
        """Retain an unusable older asset record but prevent further reuse."""
        setattr(asset, "status", "invalid")
        setattr(asset, "error_message", reason)
        self.db.flush()

    def mark_job_queued_for_retry(self, job: VoiceReadingJob) -> None:
        setattr(job, "status", "queued")
        setattr(job, "error_code", None)
        setattr(job, "error_message", None)
        for segment in job.segments:
            if segment.status == "failed":
                segment.status = "queued"
                segment.error_code = None
                segment.error_message = None
        self.db.flush()

    def get_progress(
        self,
        user_id: int,
        game_id: int,
        day_index: int,
        text_hash: str,
        voice_id: str,
        speed: float,
    ) -> Optional[VoiceReadingProgress]:
        return (
            self.db.query(VoiceReadingProgress)
            .filter(
                VoiceReadingProgress.user_id == user_id,
                VoiceReadingProgress.game_id == game_id,
                VoiceReadingProgress.day_index == day_index,
                VoiceReadingProgress.text_hash == text_hash,
                VoiceReadingProgress.voice_id == voice_id,
                VoiceReadingProgress.speed == speed,
            )
            .one_or_none()
        )

    def upsert_progress(
        self,
        *,
        user_id: int,
        game_id: int,
        day_index: int,
        story_date: Optional[str],
        text_hash: str,
        voice_id: str,
        speed: float,
        paragraph_index: int,
        position_ms: int,
        completed: bool,
    ) -> VoiceReadingProgress:
        progress = self.get_progress(user_id, game_id, day_index, text_hash, voice_id, speed)
        if progress is None:
            progress = VoiceReadingProgress(
                user_id=user_id,
                game_id=game_id,
                day_index=day_index,
                text_hash=text_hash,
                voice_id=voice_id,
                speed=speed,
            )
            self.db.add(progress)
        setattr(progress, "story_date", story_date)
        setattr(progress, "paragraph_index", max(0, paragraph_index))
        setattr(progress, "position_ms", max(0, position_ms))
        setattr(progress, "completed", completed)
        self.db.flush()
        return progress


def _normalize_text_hash(text: str) -> str:
    import hashlib

    normalized = " ".join(text.split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()
