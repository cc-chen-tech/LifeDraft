"""Real DB and storage contracts for session restoration image checks."""

from pathlib import Path

from src.api.services.session_service import SessionService
from src.database.models import Game, SceneImage
from src.game.state import PlayerState
from src.services.image_storage import ImageStorageService


def _scene(game_id: int, storage_path: str) -> SceneImage:
    return SceneImage(
        game_id=game_id,
        week=2,
        round_number=1,
        stage="event",
        scene_description="A saved scene.",
        final_prompt="saved scene prompt",
        storage_path=storage_path,
        storage_type="local",
    )


def test_restore_check_marks_missing_recent_scene_image_in_real_database(db_session, tmp_path: Path) -> None:
    game = Game(language="zh")
    db_session.add(game)
    db_session.flush()
    scene = _scene(int(game.game_id), "missing-scene.png")
    db_session.add(scene)
    db_session.commit()

    SessionService()._check_recent_scene_images(
        db=db_session,
        game_id=int(game.game_id),
        player_state=PlayerState(week=2, current_round=1),
        image_storage=ImageStorageService(storage_type="local", local_path=tmp_path),
    )

    db_session.refresh(scene)
    assert scene.importance_score == "missing"


def test_restore_check_keeps_existing_scene_image_unmarked(db_session, tmp_path: Path) -> None:
    storage_path = "present-scene.png"
    (tmp_path / storage_path).write_bytes(b"saved image")
    game = Game(language="zh")
    db_session.add(game)
    db_session.flush()
    scene = _scene(int(game.game_id), storage_path)
    db_session.add(scene)
    db_session.commit()

    SessionService()._check_recent_scene_images(
        db=db_session,
        game_id=int(game.game_id),
        player_state=PlayerState(week=2, current_round=1),
        image_storage=ImageStorageService(storage_type="local", local_path=tmp_path),
    )

    db_session.refresh(scene)
    assert scene.importance_score is None
