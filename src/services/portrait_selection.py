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
    if db.get(PortraitSelection, game_id) is not None:
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
    """Accept a ready candidate from the current origin or the legacy main image."""
    from src.services.portrait_image_jobs import _origin_is_current

    slots = (
        db.query(PortraitCandidateSlot, PortraitCandidateBatch)
        .join(PortraitCandidateBatch, PortraitCandidateBatch.batch_id == PortraitCandidateSlot.batch_id)
        .filter(PortraitCandidateBatch.game_id == game_id,
                PortraitCandidateSlot.image_id == image_id,
                PortraitCandidateSlot.status == "ready")
        .all()
    )
    if slots:
        return any(
            _origin_is_current(db, db.get(PortraitImageGenerationJob, batch.job_id))
            for _, batch in slots
        )
    image = db.get(Image, image_id)
    return bool(image and image.is_primary and selected_portrait(db, game_id) == image)


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
    row = db.get(PortraitSelection, game_id)
    if row is None:
        db.add(PortraitSelection(game_id=game_id, image_id=image_id, is_user_selected=True))
    else:
        row.image_id, row.is_user_selected = image_id, True
    db.commit()
    return image
