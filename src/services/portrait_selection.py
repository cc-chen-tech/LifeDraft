"""Read and initialize a game's persisted protagonist portrait selection."""

from typing import Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.database.models import Image, PortraitSelection


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
