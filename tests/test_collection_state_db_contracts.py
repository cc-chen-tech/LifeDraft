"""No-mock collection state and database consistency contracts."""

import pytest

from src.database.models import Game
from src.database.models import Image as ImageModel
from src.game.state import PlayerState
from src.services.collection_service import (
    CollectionService,
    EntityNotFoundError,
    PermissionDeniedError,
)

pytestmark = [pytest.mark.integration]



def _create_game(db_session) -> int:
    game = Game(language="zh", initial_state={"week": 4})
    db_session.add(game)
    db_session.commit()
    return int(game.game_id)


def _add_image(db_session, game_id: int, image_type: str, entity_name: str) -> int:
    image = ImageModel(
        game_id=game_id,
        image_type=image_type,
        entity_name=entity_name,
        entity_key=f"{image_type}_{entity_name}",
        prompt_text="contract fixture",
        storage_path=f"fixtures/{entity_name}.png",
        storage_type="local",
        is_active=True,
    )
    db_session.add(image)
    db_session.commit()
    return int(image.image_id)


def test_delete_url_encoded_item_removes_state_and_linked_image(db_session):
    game_id = _create_game(db_session)
    image_id = _add_image(db_session, game_id, "item", "旧戒指")
    state = PlayerState.from_dict(
        {"player_name": "林舟", "week": 4, "age": 26, "items": {"旧戒指": {"name": "旧戒指"}}}
    )

    deleted = CollectionService(db_session).delete_item(game_id, "%E6%97%A7%E6%88%92%E6%8C%87", state)

    assert deleted is True
    assert "旧戒指" not in state.items
    assert db_session.get(ImageModel, image_id) is None


def test_delete_url_encoded_landmark_removes_state_and_linked_image(db_session):
    game_id = _create_game(db_session)
    image_id = _add_image(db_session, game_id, "landmark", "旧码头")
    state = PlayerState.from_dict(
        {"player_name": "林舟", "week": 4, "age": 26, "landmarks": {"旧码头": {"name": "旧码头"}}}
    )

    deleted = CollectionService(db_session).delete_landmark(game_id, "%E6%97%A7%E7%A0%81%E5%A4%B4", state)

    assert deleted is True
    assert "旧码头" not in state.landmarks
    assert db_session.get(ImageModel, image_id) is None


def test_create_item_strips_name_and_rejects_duplicates(db_session):
    state = PlayerState.from_dict({"player_name": "林舟", "week": 4, "age": 26})
    service = CollectionService(db_session)

    item = service.create_item(state, "  留声机  ")

    assert item["name"] == "留声机"
    assert state.items["留声机"]["acquired_week"] == 4
    with pytest.raises(ValueError, match="已存在"):
        service.create_item(state, "留声机")


def test_character_regeneration_validation_enforces_affinity_and_known_people(db_session):
    state = PlayerState.from_dict(
        {
            "player_name": "林舟",
            "week": 4,
            "age": 26,
            "characters": {"疏远同事": {"name": "疏远同事", "affinity": 49}},
            "character_settings": {"relationships": {"key_people": [{"name": "导师"}]}},
        }
    )
    service = CollectionService(db_session)

    service.validate_character_for_regenerate("林舟", state)
    service.validate_character_for_regenerate("导师", state)
    with pytest.raises(PermissionDeniedError):
        service.validate_character_for_regenerate("疏远同事", state)
    with pytest.raises(EntityNotFoundError):
        service.validate_character_for_regenerate("陌生人", state)
