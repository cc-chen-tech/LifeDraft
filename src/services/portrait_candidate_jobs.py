"""Durable, independently recoverable protagonist portrait candidate batches."""

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import json
import logging
from threading import BoundedSemaphore

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.api.schemas import PortraitCandidateBatchResponse, PortraitCandidateSlotResponse
from src.database.models import (Game, GameState, Image, PortraitCandidateBatch,
                                 PortraitCandidateSlot, PortraitImageGenerationJob,
                                 PortraitSelection, SessionLocal)
from src.services.image_service import ImageService
from src.services.portrait_image_jobs import _origin_is_current, _safe_failure
from src.services.portrait_selection import selected_portrait, set_default_portrait

logger = logging.getLogger(__name__)
_candidate_slot_capacity = BoundedSemaphore(3)
DIRECTIONS = (
    "方案一：偏柔和的椭圆脸，整齐收束的发式，简洁素雅的衣着搭配；遵循共同角色设定与时代文化。",
    "方案二：偏方正的脸部轮廓，层次分明的发式，利落的衣着搭配；遵循共同角色设定与时代文化。",
    "方案三：偏圆润的脸部轮廓，自然蓬松的发式，细节丰富的衣着搭配；遵循共同角色设定与时代文化。",
)


def _owned_game(db, game_id, user_id):
    game = db.get(Game, game_id)
    if game is None or game.user_id != user_id:
        raise HTTPException(status_code=404, detail="游戏不存在或无权访问")
    return game


def _lock_game(db, game_id):
    # A real database write serializes enqueue/retry across processes, including
    # SQLite (where SELECT FOR UPDATE does not acquire a row lock).
    db.query(Game).filter_by(game_id=game_id).update(
        {Game.game_id: Game.game_id}, synchronize_session=False)


def _snapshot(db, game):
    latest = db.query(GameState).filter_by(game_id=game.game_id).order_by(GameState.state_id.desc()).first()
    state = deepcopy((latest.state_json if latest else game.initial_state) or {})
    settings = state.get("character_settings") or {}
    identity = settings.get("identity") or {}
    origin = settings.get("story_origin") or {}
    revision = origin.get("revision")
    if not isinstance(revision, int) or isinstance(revision, bool):
        revision = None
    era = settings.get("era") or "现代"
    if isinstance(era, dict):
        era = era.get("era_name") or era.get("era_description") or "现代"
    return {
        "operation": "candidate_batch", "game_id": game.game_id,
        "snapshot_version": 1, "origin_revision": revision,
        "name": state.get("player_name") or identity.get("name") or "主角",
        "description": json.dumps(settings, ensure_ascii=False),
        "era": str(era), "character_settings": settings,
    }


def _active_batch(db, game_id):
    return db.query(PortraitCandidateBatch).filter(
        PortraitCandidateBatch.game_id == game_id,
        PortraitCandidateBatch.active_key.isnot(None),
    ).order_by(PortraitCandidateBatch.batch_id.desc()).first()


def _supersede(db, job, batch):
    job.status = "failed"
    job.error_code = "story_origin_superseded"
    job.error_message = "故事起点已更新，旧人物形象任务已作废"
    batch.active_key = None
    for slot in db.query(PortraitCandidateSlot).filter_by(batch_id=batch.batch_id):
        if slot.status != "ready":
            slot.status, slot.error_code = "failed", "story_origin_superseded"
    db.commit()


def enqueue_candidate_batch(db: Session, user_id: int, game_id: int, mode: str):
    if mode not in ("initial", "fresh"):
        raise HTTPException(status_code=422, detail="无效的候选批次模式")
    game = _owned_game(db, game_id, user_id)
    _lock_game(db, game_id)
    snapshot = _snapshot(db, game)
    revision = snapshot["origin_revision"]
    active = _active_batch(db, game_id)
    if active is not None:
        existing = db.get(PortraitImageGenerationJob, active.job_id)
        if active.origin_revision == revision:
            db.commit()
            return existing
        _supersede(db, existing, active)
        # Reacquire after the supersession commit before inspecting/creating.
        return enqueue_candidate_batch(db, user_id, game_id, mode)
    if mode == "initial":
        previous = db.query(PortraitCandidateBatch).filter_by(
            game_id=game_id, origin_revision=revision, mode="initial",
        ).order_by(PortraitCandidateBatch.batch_id.desc()).first()
        if previous is not None:
            # Failed slots are retried explicitly; a lost enqueue response must
            # never start a second paid batch for the same origin.
            db.commit()
            return db.get(PortraitImageGenerationJob, previous.job_id)
    key = f"initial:{game_id}:{revision}" if mode == "initial" else f"fresh:{game_id}"
    job = PortraitImageGenerationJob(game_id=game_id, user_id=user_id,
        entity_key="player_main", request_json=snapshot, status="queued")
    try:
        db.add(job)
        db.flush()
        batch = PortraitCandidateBatch(game_id=game_id, user_id=user_id, job_id=job.job_id,
            mode=mode, origin_revision=revision, active_key=key)
        db.add(batch)
        db.flush()
        db.add_all([PortraitCandidateSlot(batch_id=batch.batch_id, slot_index=i) for i in range(3)])
        db.commit()
        return job
    except IntegrityError:
        db.rollback()
        existing = db.query(PortraitCandidateBatch).filter_by(active_key=key).first()
        if existing is None:
            raise
        return db.get(PortraitImageGenerationJob, existing.job_id)


def retry_candidate_batch(db, batch_id, user_id):
    batch = db.get(PortraitCandidateBatch, batch_id)
    if batch is None or batch.user_id != user_id:
        raise HTTPException(status_code=404, detail="候选批次不存在")
    _owned_game(db, batch.game_id, user_id)
    _lock_game(db, batch.game_id)
    db.refresh(batch)
    job = db.get(PortraitImageGenerationJob, batch.job_id)
    db.refresh(job)
    if not _origin_is_current(db, job):
        db.rollback()
        raise HTTPException(status_code=409, detail="故事起点已更新，请生成新的候选批次")
    active = _active_batch(db, batch.game_id)
    if active is not None and active.batch_id != batch_id:
        db.rollback()
        raise HTTPException(status_code=409, detail="另一候选批次正在生成")
    if job.status in ("queued", "running", "succeeded"):
        db.commit()
        return job
    batch.active_key = (f"initial:{batch.game_id}:{batch.origin_revision}"
                        if batch.mode == "initial" else f"fresh:{batch.game_id}")
    for slot in db.query(PortraitCandidateSlot).filter_by(batch_id=batch_id):
        if slot.status != "ready":
            slot.status, slot.error_code = "queued", None
    job.status, job.error_code, job.error_message = "queued", None, None
    db.commit()
    return job


def candidate_batch_state(db, game_id, user_id):
    _owned_game(db, game_id, user_id)
    batch = db.query(PortraitCandidateBatch).filter_by(game_id=game_id, user_id=user_id).order_by(
        PortraitCandidateBatch.batch_id.desc()).first()
    if batch is None or not _origin_is_current(db, db.get(PortraitImageGenerationJob, batch.job_id)):
        # Read-only recovery exposes only the current origin. A stale completed
        # batch is not evidence that a new-origin POST was accepted.
        return None
    return _batch_state(db, batch)


def _batch_state(db, batch):
    job = db.get(PortraitImageGenerationJob, batch.job_id)
    slots = db.query(PortraitCandidateSlot).filter_by(batch_id=batch.batch_id).order_by(
        PortraitCandidateSlot.slot_index).all()
    selected = selected_portrait(db, batch.game_id)
    return PortraitCandidateBatchResponse(
        batch_id=batch.batch_id, job_id=job.job_id, game_id=batch.game_id,
        mode=batch.mode, origin_revision=batch.origin_revision, status=job.status,
        completed_count=sum(slot.status == "ready" for slot in slots),
        selected_image_id=selected.image_id if selected else None,
        error_code=job.error_code, error_message=job.error_message,
        slots=[PortraitCandidateSlotResponse(slot_index=s.slot_index, status=s.status,
            image_id=s.image_id, error_code=s.error_code) for s in slots],
    )


def _saved_image(db, batch, slot):
    # Constrain by game/type/entity before scanning JSON for SQLite portability.
    images = db.query(Image).filter_by(game_id=batch.game_id, image_type="character",
                                      entity_key="player_main").order_by(Image.image_id).all()
    return next((image for image in images if (image.metadata_json or {}).get("batch_id") == batch.batch_id
                 and (image.metadata_json or {}).get("slot_index") == slot.slot_index), None)


def _discard_stale_candidate_images(db, batch, image_service_factory):
    """Remove unreferenced files after all slots of a superseded batch stop."""
    referenced = {slot.image_id for slot in db.query(PortraitCandidateSlot).filter_by(
        batch_id=batch.batch_id) if slot.image_id is not None}
    job = db.get(PortraitImageGenerationJob, batch.job_id)
    if job.image_id is not None:
        referenced.add(job.image_id)
    selection = db.get(PortraitSelection, batch.game_id)
    if selection is not None:
        referenced.add(selection.image_id)
    images = db.query(Image).filter_by(
        game_id=batch.game_id, image_type="character", entity_key="player_main",
        is_active=False,
    ).all()
    stale = [image for image in images
             if image.image_id not in referenced
             and (image.metadata_json or {}).get("batch_id") == batch.batch_id]
    if not stale:
        return
    for image in stale:
        db.delete(image)
    db.commit()
    image_service_factory(db).delete_image_files(stale)


def _run_candidate_slot(job_id, index, *, session_factory, image_service_factory):
    # Bound provider calls and database sessions across batches in this process.
    with _candidate_slot_capacity:
        _process_candidate_slot(job_id, index, session_factory=session_factory,
                                image_service_factory=image_service_factory)


def _process_candidate_slot(job_id, index, *, session_factory, image_service_factory):
    db = session_factory()
    try:
        job = db.get(PortraitImageGenerationJob, job_id)
        batch = db.query(PortraitCandidateBatch).filter_by(job_id=job_id).one()
        request = deepcopy(job.request_json)
        db.expire_all()
        if job.status != "running":
            return
        if not _origin_is_current(db, job):
            _supersede(db, job, batch)
            return
        slot = db.get(PortraitCandidateSlot, (batch.batch_id, index))
        if slot.status == "ready":
            return
        image = _saved_image(db, batch, slot)
        slot.status, slot.error_code = "running", None
        db.commit()
        try:
            if image is None:
                image = image_service_factory(db).generate_character_candidate(
                    game_id=job.game_id,
                    name=request["name"],
                    description=request["description"],
                    era=request["era"],
                    character_settings=deepcopy(request["character_settings"]),
                    direction=DIRECTIONS[index],
                    batch_id=batch.batch_id,
                    slot_index=index,
                )
            image_id = image.image_id
            _lock_game(db, job.game_id)
            db.refresh(job)
            if job.status != "running":
                db.rollback()
                return
            if not _origin_is_current(db, job):
                _supersede(db, job, batch)
                return
            image = db.get(Image, image_id)
            if (
                image is None
                or image.game_id != batch.game_id
                or image.image_type != "character"
                or image.entity_key != "player_main"
            ):
                raise ValueError("invalid saved candidate")
            image.is_active = True
            slot.status, slot.image_id, slot.error_code = "ready", image_id, None
            # Preserve an old game's usable portrait through a fresh batch.
            previous = selected_portrait(db, batch.game_id)
            set_default_portrait(db, batch.game_id, previous.image_id if previous else image_id)
            if job.image_id is None:
                job.image_id = image_id
            db.commit()
        except Exception as error:
            db.rollback()
            db.refresh(job)
            if job.status != "running":
                return
            slot = db.get(PortraitCandidateSlot, (batch.batch_id, index))
            slot.status, slot.error_code = "failed", _safe_failure(error)[0]
            db.commit()
            logger.warning(
                "candidate slot failed job_id=%s slot=%s code=%s", job_id, index, slot.error_code
            )
    finally:
        db.close()


def run_candidate_batch(
    job_id, *, session_factory=SessionLocal, image_service_factory=ImageService
):
    db = session_factory()
    try:
        # Atomic claim prevents duplicate scheduler deliveries from generating
        # the same paid slots. Startup recovery resets interrupted running jobs.
        claimed = (
            db.query(PortraitImageGenerationJob)
            .filter_by(job_id=job_id, status="queued")
            .update(
                {
                    "status": "running",
                    "attempt_count": PortraitImageGenerationJob.attempt_count + 1,
                    "error_code": None,
                    "error_message": None,
                },
                synchronize_session=False,
            )
        )
        db.commit()
        if not claimed:
            return
        # Release the coordinator's transaction before slot writers start.
        db.rollback()
        # This dedicated pool avoids waiting inside the shared image pool for
        # child work queued behind other waiting batches.
        with ThreadPoolExecutor(max_workers=3, thread_name_prefix="portrait-slot") as pool:
            futures = [
                pool.submit(
                    _run_candidate_slot,
                    job_id,
                    index,
                    session_factory=session_factory,
                    image_service_factory=image_service_factory,
                )
                for index in range(3)
            ]
            for future in futures:
                future.result()
        db.expire_all()
        job = db.get(PortraitImageGenerationJob, job_id)
        _lock_game(db, job.game_id)
        db.refresh(job)
        batch = db.query(PortraitCandidateBatch).filter_by(job_id=job_id).one()
        if job.status != "running":
            stale = job.error_code == "story_origin_superseded"
            db.rollback()
            if stale:
                _discard_stale_candidate_images(db, batch, image_service_factory)
            return
        if not _origin_is_current(db, job):
            _supersede(db, job, batch)
            _discard_stale_candidate_images(db, batch, image_service_factory)
            return
        slots = db.query(PortraitCandidateSlot).filter_by(batch_id=batch.batch_id).all()
        completed = sum(s.status == "ready" for s in slots)
        job.status = "succeeded" if completed == 3 else "partial_failed" if completed else "failed"
        if completed < 3:
            job.error_code, job.error_message = (
                "image_generation_failed",
                "部分候选形象未完成，请重试未完成的图片",
            )
        batch.active_key = None
        db.commit()
    finally:
        db.close()
