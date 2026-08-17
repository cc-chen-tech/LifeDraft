"""Real database contracts for image-router read and deletion paths."""

import pytest
from starlette.requests import Request

from src.api.routers.images import (
    delete_image,
    get_all_round_scene_images,
    get_game_images,
    get_image,
    get_round_scene_image,
    verify_game_ownership,
)
from src.database.models import Game, SceneImage, User
from src.database.models import Image as ImageModel

pytestmark = [pytest.mark.api]



def _owner_game(db_session) -> tuple[User, Game]:
    owner = User(private_id="image-router-owner", public_id="imgown01", display_name="Owner")
    db_session.add(owner)
    db_session.flush()
    game = Game(user_id=owner.user_id, language="zh", initial_state={"player_name": "林岚"})
    db_session.add(game)
    db_session.commit()
    return owner, game


def _image(db_session, game: Game, *, active: bool = True) -> ImageModel:
    image = ImageModel(
        game_id=game.game_id,
        image_type="character",
        entity_name="林岚",
        entity_key="player-main",
        prompt_text="portrait prompt",
        storage_path="contracts/linlan.png",
        storage_type="local",
        version=2,
        is_active=active,
    )
    db_session.add(image)
    db_session.commit()
    return image


def _request() -> Request:
    return Request({"type": "http", "headers": [], "method": "GET", "path": "/"})


@pytest.mark.asyncio
async def test_owned_image_read_and_soft_delete_change_game_listing(db_session) -> None:
    owner, game = _owner_game(db_session)
    image = _image(db_session, game)

    read = await get_image(int(image.image_id), db=db_session, user=int(owner.user_id))
    listed = await get_game_images(int(game.game_id), db=db_session, user=int(owner.user_id))
    deleted = await delete_image(int(image.image_id), db=db_session, user=int(owner.user_id))
    after_delete = await get_game_images(int(game.game_id), db=db_session, user=int(owner.user_id))

    assert read.image_id == image.image_id
    assert read.entity_key == "player-main"
    assert listed.total == 1 and listed.images[0].image_url.endswith("contracts/linlan.png")
    assert deleted.success is True
    assert image.is_active is False
    assert after_delete.total == 0


@pytest.mark.asyncio
async def test_scene_reads_select_requested_week_stage_and_list_identity_fields(db_session) -> None:
    owner, game = _owner_game(db_session)
    previous = SceneImage(
        game_id=game.game_id,
        week=2,
        round_number=1,
        stage="event",
        scene_description="旧周事件",
        final_prompt="old",
        storage_path="scene/old.png",
        storage_type="local",
        referenced_images=[1],
        importance_score="normal",
    )
    target = SceneImage(
        game_id=game.game_id,
        week=3,
        round_number=1,
        stage="result",
        scene_description="本周结果",
        final_prompt="target",
        storage_path="scene/target.png",
        storage_type="local",
        referenced_images=[2, 3],
        importance_score="high",
    )
    db_session.add_all([previous, target])
    db_session.commit()

    scene = await get_round_scene_image(
        _request(),
        int(game.game_id),
        1,
        week=3,
        stage="result",
        db=db_session,
        user=int(owner.user_id),
    )
    listed = await get_all_round_scene_images(
        _request(), int(game.game_id), db=db_session, user=int(owner.user_id)
    )

    assert scene["scene_id"] == target.scene_id
    assert scene["week"] == 3 and scene["stage"] == "result"
    assert scene["referenced_images"] == [2, 3]
    assert listed["total"] == 2
    assert [(entry["week"], entry["stage"]) for entry in listed["scenes"]] == [
        (2, "event"),
        (3, "result"),
    ]


def test_game_ownership_keeps_legacy_unowned_games_visible_to_signed_in_users(db_session) -> None:
    game = Game(language="zh", initial_state={})
    db_session.add(game)
    db_session.commit()

    assert verify_game_ownership(db_session, int(game.game_id), 999).game_id == game.game_id
