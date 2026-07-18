"""Provider-free persistence contracts for the ImageService facade."""

import base64
from io import BytesIO
from pathlib import Path

from PIL import Image as PillowImage

from src.database.models import Game, GameState
from src.database.models import Image as ImageModel
from src.services.image_service import ImageService
from src.services.image_storage import ImageStorageService


def _service(db_session, storage_root: Path) -> ImageService:
    service = ImageService.__new__(ImageService)
    service.db = db_session
    service.storage_service = ImageStorageService(storage_type="local", local_path=storage_root)
    return service


def _game(db_session, initial_state: dict | None = None) -> Game:
    game = Game(language="zh", initial_state=initial_state or {})
    db_session.add(game)
    db_session.commit()
    return game


def _image(
    db_session,
    game: Game,
    storage_path: str,
    *,
    entity_name: str = "林岚",
    version: int = 1,
    is_active: bool = True,
    is_primary: bool = False,
) -> ImageModel:
    image = ImageModel(
        game_id=game.game_id,
        image_type="character",
        entity_name=entity_name,
        entity_key=f"character-{entity_name}",
        prompt_text="character image",
        storage_path=storage_path,
        storage_type="local",
        version=version,
        is_active=is_active,
        is_primary=is_primary,
    )
    db_session.add(image)
    db_session.commit()
    return image


def test_active_image_queries_select_highest_active_version_and_filter_type(db_session, tmp_path: Path) -> None:
    service = _service(db_session, tmp_path)
    game = _game(db_session)
    older = _image(db_session, game, "1/character/older.png", version=1)
    newest = _image(db_session, game, "1/character/newest.png", version=2)
    _image(db_session, game, "1/character/inactive.png", version=3, is_active=False)
    item = ImageModel(
        game_id=game.game_id,
        image_type="item",
        entity_name="青玉剑",
        prompt_text="item image",
        storage_path="1/item/sword.png",
        storage_type="local",
        is_active=True,
    )
    db_session.add(item)
    db_session.commit()

    assert service.get_image(int(older.image_id)) is older
    assert service.get_active_image(int(game.game_id), "character", "林岚") is newest
    assert {image.image_id for image in service.get_all_images_for_game(int(game.game_id), "character")} == {
        older.image_id,
        newest.image_id,
    }
    assert {image.image_id for image in service.get_all_images_for_game(int(game.game_id))} == {
        older.image_id,
        newest.image_id,
        item.image_id,
    }


def test_foreign_player_image_id_falls_back_to_local_primary_and_compresses_reference(
    db_session, tmp_path: Path
) -> None:
    service = _service(db_session, tmp_path)
    owner_game = _game(db_session)
    foreign_game = _game(db_session)
    primary_path = "owner/character/primary.png"
    full_path = service.storage_service.get_full_path(primary_path)
    full_path.parent.mkdir(parents=True)
    image = PillowImage.new("RGBA", (900, 600), color=(38, 85, 117, 180))
    image.save(full_path, format="PNG")
    primary = _image(db_session, owner_game, primary_path, is_primary=True)
    foreign = _image(db_session, foreign_game, "foreign/character/other.png", is_primary=True)

    data_url, selected_id = service._get_player_image_base64(
        int(owner_game.game_id), int(foreign.image_id)
    )

    assert selected_id == primary.image_id
    assert data_url is not None and data_url.startswith("data:image/jpeg;base64,")
    reference = base64.b64decode(data_url.split(",", 1)[1])
    with PillowImage.open(BytesIO(reference)) as decoded:
        assert decoded.mode == "RGB"
        assert decoded.size == (512, 341)
    assert service.get_image_data(primary) == full_path.read_bytes()
    assert service.get_image_url(primary) == "/api/images/file/owner/character/primary.png"


def test_saved_character_context_prefers_latest_state_then_initial_state(db_session, tmp_path: Path) -> None:
    service = _service(db_session, tmp_path)
    saved_game = _game(
        db_session,
        {"character_settings": {"era": {"era_name": "现代"}}, "player_name": "初始名"},
    )
    db_session.add(
        GameState(
            game_id=saved_game.game_id,
            week=3,
            age=28,
            state_json={
                "character_settings": {"era": {"era_name": "民国"}},
                "player_name": "存档名",
            },
        )
    )
    db_session.commit()

    fallback_game = _game(
        db_session,
        {"character_settings": {"era": {"era_name": "唐代"}}, "player_name": "初始回退名"},
    )
    db_session.add(
        GameState(game_id=fallback_game.game_id, week=1, age=21, state_json={"week": 1})
    )
    db_session.commit()

    assert service._get_character_settings_from_db(int(saved_game.game_id)) == (
        {"era": {"era_name": "民国"}},
        "存档名",
    )
    assert service._get_character_settings_from_db(int(fallback_game.game_id)) == (
        {"era": {"era_name": "唐代"}},
        "初始回退名",
    )
