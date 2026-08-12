"""Durable main-character portrait generation jobs."""

import logging
import threading
from collections.abc import Callable
from typing import Any, Optional

from sqlalchemy.orm import Session

from src.database.models import PortraitImageGenerationJob, SessionLocal
from src.services.image import ImageContentError, ImageProviderServiceError, ImageServiceError
from src.services.image_service import ImageService, get_image_thread_pool

logger = logging.getLogger(__name__)

ACTIVE_JOB_STATUSES = ("queued", "running")
_job_lock = threading.Lock()
_scheduled_job_ids: set[int] = set()


class PortraitImageJobService:
    """Create and read durable portrait jobs with process-local de-duplication."""

    def __init__(self, db: Session):
        self.db = db

    def enqueue(
        self, user_id: int, request_json: dict[str, Any]
    ) -> tuple[PortraitImageGenerationJob, bool]:
        game_id = int(request_json["game_id"])
        entity_key = str(request_json.get("entity_key") or "player_main")

        with _job_lock:
            existing = (
                self.db.query(PortraitImageGenerationJob)
                .filter(
                    PortraitImageGenerationJob.game_id == game_id,
                    PortraitImageGenerationJob.user_id == user_id,
                    PortraitImageGenerationJob.entity_key == entity_key,
                    PortraitImageGenerationJob.status.in_(ACTIVE_JOB_STATUSES),
                )
                .order_by(PortraitImageGenerationJob.created_at.desc())
                .first()
            )
            if existing:
                return existing, True

            job = PortraitImageGenerationJob(
                game_id=game_id,
                user_id=user_id,
                entity_key=entity_key,
                request_json=request_json,
                status="queued",
            )
            self.db.add(job)
            self.db.commit()
            self.db.refresh(job)
            return job, False

    def latest_for_game(
        self, user_id: int, game_id: int
    ) -> Optional[PortraitImageGenerationJob]:
        return (
            self.db.query(PortraitImageGenerationJob)
            .filter(
                PortraitImageGenerationJob.user_id == user_id,
                PortraitImageGenerationJob.game_id == game_id,
                PortraitImageGenerationJob.entity_key == "player_main",
            )
            .order_by(PortraitImageGenerationJob.created_at.desc())
            .first()
        )


def requeue_interrupted_portrait_jobs(db: Session) -> list[int]:
    """Return running jobs to the queue after a process restart."""
    jobs = (
        db.query(PortraitImageGenerationJob)
        .filter(PortraitImageGenerationJob.status == "running")
        .all()
    )
    job_ids = [int(job.job_id) for job in jobs]
    if job_ids:
        for job in jobs:
            job.status = "queued"
        db.commit()
    return job_ids


def _safe_failure(error: Exception) -> tuple[str, str]:
    if isinstance(error, ImageProviderServiceError):
        return error.code, error.public_message
    if isinstance(error, ImageContentError):
        return "image_content_rejected", "人物形象生成未通过内容检查，请修改设定后重试"
    return "image_generation_failed", "人物形象生成失败，请稍后重试"


def run_portrait_image_job(
    job_id: int,
    *,
    session_factory: Callable[[], Session] = SessionLocal,
    image_service_factory: Callable[[Session], ImageService] = ImageService,
) -> None:
    """Run one persisted job using a session owned by the worker thread."""
    db = session_factory()
    try:
        job = db.get(PortraitImageGenerationJob, job_id)
        if job is None or job.status not in ACTIVE_JOB_STATUSES:
            return

        job.status = "running"
        job.attempt_count += 1
        job.error_code = None
        job.error_message = None
        db.commit()

        request = job.request_json
        images = image_service_factory(db).generate_character_image(
            game_id=int(request["game_id"]),
            name=str(request["entity_name"]),
            description=str(request["description"]),
            era=str(request.get("era") or "现代"),
            entity_key="player_main",
            metadata=request.get("extra_context"),
            num_images=1,
            feedback=request.get("feedback"),
        )
        if not images or images[0].image_id is None:
            raise ImageServiceError("no image was persisted")

        job.image_id = int(images[0].image_id)
        job.status = "succeeded"
        db.commit()
        logger.info("portrait image job completed job_id=%s status=succeeded", job_id)
    except Exception as error:
        db.rollback()
        job = db.get(PortraitImageGenerationJob, job_id)
        if job is not None:
            error_code, error_message = _safe_failure(error)
            job.status = "failed"
            job.error_code = error_code
            job.error_message = error_message
            db.commit()
            logger.warning(
                "portrait image job completed job_id=%s status=failed error_code=%s",
                job_id,
                error_code,
            )
    finally:
        db.close()


def schedule_portrait_image_job(job_id: int) -> None:
    """Submit a job once; persistence keeps it recoverable if submission is interrupted."""
    with _job_lock:
        if job_id in _scheduled_job_ids:
            return
        _scheduled_job_ids.add(job_id)

    def _run() -> None:
        try:
            run_portrait_image_job(job_id)
        finally:
            with _job_lock:
                _scheduled_job_ids.discard(job_id)

    get_image_thread_pool().submit(_run)


def recover_pending_portrait_image_jobs() -> list[int]:
    """Requeue interrupted jobs then schedule all durable queued jobs at startup."""
    db = SessionLocal()
    try:
        requeue_interrupted_portrait_jobs(db)
        queued_ids = [
            int(job_id)
            for job_id, in db.query(PortraitImageGenerationJob.job_id)
            .filter(PortraitImageGenerationJob.status == "queued")
            .all()
        ]
    finally:
        db.close()

    for job_id in queued_ids:
        schedule_portrait_image_job(job_id)
    return queued_ids
