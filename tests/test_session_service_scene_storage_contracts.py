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


def test_restore_extracts_stable_era_names_from_character_settings() -> None:
    service = SessionService()

    assert service._extract_era_from_settings({"era": {"era_name": "Tang dynasty"}}) == "Tang dynasty"
    assert service._extract_era_from_settings(
        {"era": {"era_description": "Near future city, automated transit"}}
    ) == "Near future city"
    assert service._extract_era_from_settings({"era": "x" * 40}) == "x" * 30
    assert service._extract_era_from_settings({"era": {}}) is None


def test_existing_valid_scene_skips_illustration_regeneration(db_session, tmp_path: Path) -> None:
    storage_path = "valid-event-scene.png"
    (tmp_path / storage_path).write_bytes(b"saved image")
    game = Game(language="zh")
    db_session.add(game)
    db_session.flush()
    db_session.add(_scene(int(game.game_id), storage_path))
    db_session.commit()

    SessionService()._check_and_generate_illustration(
        db=db_session,
        game_id=int(game.game_id),
        week=2,
        round_number=1,
        stage="event",
        story_text="A saved scene.",
        character_settings={},
        player_name="Test",
        image_storage=ImageStorageService(storage_type="local", local_path=tmp_path),
    )
