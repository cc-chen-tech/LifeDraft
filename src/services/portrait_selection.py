"""Read and initialize a game's persisted protagonist portrait selection."""

from typing import Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.database.models import (Image, PortraitCandidateBatch, PortraitCandidateSlot,
                                 PortraitImageGenerationJob, PortraitSelection)
from src.services.image_storage import ImageStorageError, ImageStorageService


def selected_portrait(db: Session, game_id: int) -> Optional[Image]:
    selection = db.get(PortraitSelection, game_id)
    if selection is not None:
        image = (
            db.query(Image)
            .filter(
                Image.image_id == selection.image_id,
                Image.game_id == game_id,
                Image.image_type == "character",
                Image.entity_key == "player_main",
                Image.is_active.is_(True),
            )
            .first()
        )
        if image is not None:
            return image

    return (
        db.query(Image)
        .filter(
            Image.game_id == game_id,
            Image.image_type == "character",
            Image.entity_key == "player_main",
            Image.is_active.is_(True),
            Image.is_primary.is_(True),
        )
        .order_by(Image.created_at.desc(), Image.image_id.desc())
        .first()
    )


def set_default_portrait(db: Session, game_id: int, image_id: int) -> None:
    from src.services.portrait_candidate_jobs import _lock_game

    # Serialize with manual selection and feedback completion. Refresh after the
    # lock so a stale session cannot replace a newly committed valid choice.
    _lock_game(db, game_id)
    row = db.get(PortraitSelection, game_id, populate_existing=True)
    if row is not None:
        current = db.query(Image).filter_by(
            image_id=row.image_id, game_id=game_id, image_type="character",
            entity_key="player_main", is_active=True,
        ).first()
        if current is not None:
            return
        row.image_id, row.is_user_selected = image_id, False
        db.flush()
        return

    try:
        with db.begin_nested():
            db.add(PortraitSelection(game_id=game_id, image_id=image_id, is_user_selected=False))
            db.flush()
    except IntegrityError:
        # Another transaction may have selected a portrait since the empty read.
        # Roll back only the insert, leaving the caller's image and slot writes intact.
        if db.get(PortraitSelection, game_id) is None:
            raise


def is_selectable_candidate(db: Session, game_id: int, image_id: int) -> bool:
    """Accept ready portraits from the selected batch or latest staged batch."""
    from src.services.portrait_image_jobs import _origin_is_current

    batches = (
        db.query(PortraitCandidateBatch)
        .filter(PortraitCandidateBatch.game_id == game_id)
        .order_by(PortraitCandidateBatch.batch_id.desc())
        .all()
    )
    current_batches = [
        batch for batch in batches
        if _origin_is_current(db, db.get(PortraitImageGenerationJob, batch.job_id))
    ]
    selected = selected_portrait(db, game_id)
    selected_batch_id = None
    if selected is not None:
        for batch in current_batches:
            selected_slot = db.query(PortraitCandidateSlot).filter_by(
                batch_id=batch.batch_id, image_id=selected.image_id, status="ready"
            ).first()
            if selected_slot is not None:
                selected_batch_id = batch.batch_id
                break
    eligible_batch_ids = {current_batches[0].batch_id} if current_batches else set()
    if selected_batch_id is not None:
        eligible_batch_ids.add(selected_batch_id)
    candidate_slot = (
        db.query(PortraitCandidateSlot, PortraitCandidateBatch)
        .join(PortraitCandidateBatch, PortraitCandidateBatch.batch_id == PortraitCandidateSlot.batch_id)
        .filter(PortraitCandidateBatch.batch_id.in_(eligible_batch_ids),
                PortraitCandidateSlot.image_id == image_id,
                PortraitCandidateSlot.status == "ready")
        .first()
    )
    if candidate_slot is not None:
        return True
    image = db.get(Image, image_id)
    # Legacy variants have no slot. Candidate images must never fall through
    # this compatibility path when their batch is superseded.
    has_slot = db.query(PortraitCandidateSlot).filter_by(image_id=image_id).first() is not None
    return bool(image and image.game_id == game_id and image.image_type == "character"
                and image.entity_key == "player_main" and image.is_active
                and not has_slot and not (image.metadata_json or {}).get("batch_id"))


def select_portrait(db: Session, game_id: int, image_id: int) -> Image:
    image = db.get(Image, image_id)
    if (image is None or image.game_id != game_id or image.image_type != "character"
            or image.entity_key != "player_main"):
        raise ValueError("图片不属于当前主角")
    if not image.is_active or not is_selectable_candidate(db, game_id, image_id):
        raise ValueError("图片不可选择")
    try:
        if not ImageStorageService(storage_type=image.storage_type).get_image_data(
            image.storage_path, image.storage_type
        ):
            raise ValueError("图片文件不可用")
    except (ImageStorageError, OSError) as exc:
        raise ValueError("图片文件不可用") from exc
    # Storage may involve remote IO. Only lock after it returns, then repeat
    # eligibility checks against fresh database state before saving the choice.
    from src.services.portrait_candidate_jobs import _lock_game

    try:
        _lock_game(db, game_id)
        db.expire_all()
        image = db.get(Image, image_id)
        if (image is None or image.game_id != game_id or image.image_type != "character"
                or image.entity_key != "player_main"):
            raise ValueError("图片不属于当前主角")
        if not image.is_active or not is_selectable_candidate(db, game_id, image_id):
            raise ValueError("图片不可选择")
        row = db.get(PortraitSelection, game_id)
        if row is None:
            db.add(PortraitSelection(game_id=game_id, image_id=image_id, is_user_selected=True))
        else:
            row.image_id, row.is_user_selected = image_id, True
        db.commit()
        return image
    except Exception:
        db.rollback()
        raise
