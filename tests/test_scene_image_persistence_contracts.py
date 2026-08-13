"""Provider-free persistence contracts for scene image reuse and anchors."""

from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.database.models import Base, Game
from src.database.models import Image as ImageModel
from src.database.models import SceneImage
from src.services.image.scene_service import SceneImageService
from src.services.image_storage import ImageStorageService


def _session() -> Session:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)()


def _game(session: Session) -> Game:
    game = Game(language="zh", initial_state={})
    session.add(game)
    session.commit()
    return game


def test_existing_scene_with_local_asset_returns_without_regeneration(tmp_path: Path) -> None:
    session = _session()
    try:
        game = _game(session)
        storage = ImageStorageService(storage_type="local", local_path=tmp_path)
        storage_path = "scene-cache/round.png"
        target = storage.get_full_path(storage_path)
        target.parent.mkdir(parents=True)
        target.write_bytes(b"scene-cache")
        existing = SceneImage(
            game_id=game.game_id,
            week=2,
            round_number=1,
            stage="event",
            scene_description="已保存的雨夜书院",
            final_prompt="saved prompt",
            storage_path=storage_path,
            storage_type="local",
        )
        session.add(existing)
        session.commit()
        service = SceneImageService(db=session, storage_service=storage)

        reused = service.generate_round_scene_image(
            game_id=int(game.game_id),
            round_number=1,
            story_text="这段文字不应触发生成。",
            character_settings={},
            player_name="林岚",
            week=2,
            stage="event",
        )

        assert reused.scene_id == existing.scene_id
        assert reused.storage_path == storage_path
        assert session.query(SceneImage).count() == 1
    finally:
        session.close()


def test_persisted_appearance_anchor_is_recovered_for_player_manifest() -> None:
    session = _session()
    try:
        game = _game(session)
        image = ImageModel(
            game_id=game.game_id,
            image_type="character",
            entity_name="林岚",
            entity_key="player-lin-lan",
            prompt_text="character anchor",
            storage_path="characters/lin-lan.png",
            storage_type="local",
            metadata_json={
                "appearance_anchor": {
                    "name": "林岚",
                    "face_shape": "鹅蛋脸",
                    "facial_features": "明亮杏眼",
                    "hair_style": "黑色短发",
                    "body_type": "匀称",
                    "version": 1,
                }
            },
        )
        session.add(image)
        session.commit()
        service = SceneImageService(db=session)

        anchor = service._get_appearance_anchor(int(image.image_id))
        manifest = service._build_character_manifest(
            [{"name": "林岚", "description": "29岁，建筑师"}],
            appearance_anchor=anchor,
            player_name="林岚",
        )

        assert anchor is not None
        assert anchor.name == "林岚"
        assert "外貌锚点" in manifest
        assert "鹅蛋脸" in manifest
        assert "黑色短发" in manifest
    finally:
        session.close()
