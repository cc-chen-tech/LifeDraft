"""Real database contracts for the active image facade."""

from pathlib import Path

from src.database.models import Game
from src.database.models import Image as ImageModel
from src.services.image import ImageService
from src.services.image_storage import ImageStorageService


def _service(db_session, storage_root: Path) -> ImageService:
    service = ImageService.__new__(ImageService)
    service.db = db_session
    service.storage_service = ImageStorageService(storage_type="local", local_path=storage_root)
    return service


def _game(db_session) -> Game:
    game = Game(language="zh", initial_state={"week": 2})
    db_session.add(game)
    db_session.commit()
    return game


def _image(
    db_session,
    game_id: int,
    *,
    entity_name: str,
    image_type: str = "character",
    version: int = 1,
    is_active: bool = True,
    is_primary: bool = False,
    storage_path: str = "images/portrait.png",
) -> ImageModel:
    image = ImageModel(
        game_id=game_id,
        image_type=image_type,
        entity_name=entity_name,
        entity_key=f"{image_type}-{entity_name}-{version}",
        prompt_text="contract image",
        storage_path=storage_path,
        storage_type="local",
        version=version,
        is_active=is_active,
        is_primary=is_primary,
    )
    db_session.add(image)
    db_session.commit()
    return image


def test_facade_selects_newest_active_image_and_filters_game_assets(db_session, tmp_path: Path) -> None:
    service = _service(db_session, tmp_path)
    game = _game(db_session)
    older = _image(db_session, int(game.game_id), entity_name="林岚", version=1)
    newest = _image(db_session, int(game.game_id), entity_name="林岚", version=2)
    _image(db_session, int(game.game_id), entity_name="林岚", version=3, is_active=False)
    item = _image(db_session, int(game.game_id), entity_name="旧钥匙", image_type="item")

    assert service.get_image(int(older.image_id)) is older
    assert service.get_active_image(int(game.game_id), "character", "林岚") is newest
    assert {image.image_id for image in service.get_all_images_for_game(int(game.game_id))} == {
        older.image_id,
        newest.image_id,
        item.image_id,
    }
    assert [image.image_id for image in service.get_all_images_for_game(int(game.game_id), "item")] == [
        item.image_id
    ]


def test_facade_normalizes_character_context_and_local_image_data(db_session, tmp_path: Path) -> None:
    service = _service(db_session, tmp_path)
    game = _game(db_session)
    storage_path = "assets/linlan.png"
    full_path = service.storage_service.get_full_path(storage_path)
    full_path.parent.mkdir(parents=True)
    full_path.write_bytes(b"image-contract-bytes")
    image = _image(
        db_session,
        int(game.game_id),
        entity_name="林岚",
        is_primary=True,
        storage_path=storage_path,
    )
    settings = {
        "age": {"age_range": "二十多岁"},
        "gender": "女性",
        "world": {"cultural_context": "海港城市", "special_features": "雨季漫长"},
        "era": {"era_description": "1920年代上海，报馆林立，电车穿行"},
    }

    assert service._build_description_from_settings(settings) == "二十多岁，女性，海港城市，雨季漫长"
    assert service._extract_era_from_settings(settings) == "1920年代上海"
    assert service._build_char_info(settings, "林岚") == {
        "name": "林岚",
        "era": "1920年代上海",
        "gender": "女性",
        "age": "",
    }
    assert service.get_image_data(image) == b"image-contract-bytes"
    assert service.get_image_url(image) == "/api/images/file/assets/linlan.png"
