"""Real SQLite lifecycle contracts for collection entity operations."""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.database.models import Base, Game, Image, User
from src.game.state import PlayerState
from src.services.collection_service import (
    CollectionService,
    EntityNotFoundError,
    PermissionDeniedError,
)

pytestmark = [pytest.mark.integration]



def _session() -> Session:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)()


def _user(session: Session, suffix: str) -> User:
    user = User(
        private_id=f"collection-private-{suffix}",
        public_id=f"c{suffix}",
        display_name=f"Collection {suffix}",
    )
    session.add(user)
    session.commit()
    return user


def _game(session: Session, *, user_id: int | None = None) -> Game:
    game = Game(language="zh", initial_state={"week": 4}, user_id=user_id)
    session.add(game)
    session.commit()
    return game


def test_recognized_entities_add_once_with_collection_metadata() -> None:
    session = _session()
    try:
        state = PlayerState(player_name="林岚", week=4)
        service = CollectionService(session)

        result = service.add_entities(
            state,
            characters=[
                {"name": "林岚", "description": "主角", "role": "重复"},
                {"name": "陈舟", "description": "同事", "role": "调查员", "affinity": 73},
                {"name": "陈舟", "description": "重复人物"},
            ],
            items=[
                {
                    "name": "青玉剑",
                    "description": "旧书院留下的信物",
                    "importance": "critical",
                    "category": "keepsake",
                    "appear_contexts": ["雨夜书院"],
                },
                {"name": "青玉剑", "description": "重复物品"},
            ],
            landmarks=[
                {
                    "name": "旧书院",
                    "description": "档案室所在的旧建筑",
                    "importance": "critical",
                    "category": "building",
                    "appear_count": 3,
                    "appear_contexts": ["门廊"],
                },
                {"name": "旧书院", "description": "重复地点"},
            ],
        )

        assert result == {
            "added_items": ["青玉剑"],
            "added_characters": ["陈舟"],
            "added_landmarks": ["旧书院"],
        }
        assert state.characters["陈舟"]["relationship_desc"] == "同事"
        assert state.characters["陈舟"]["affinity"] == 73
        assert state.items["青玉剑"]["acquired_week"] == 4
        assert state.items["青玉剑"]["acquired_context"] == "雨夜书院"
        assert state.items["青玉剑"]["is_key_item"] is True
        assert state.landmarks["旧书院"]["appear_count"] == 3
        assert state.landmarks["旧书院"]["context"] == "门廊"
        assert state.landmarks["旧书院"]["is_key_location"] is True
    finally:
        session.close()


def test_manual_character_and_landmark_creation_uses_safe_defaults_and_rejects_duplicates() -> None:
    session = _session()
    try:
        state = PlayerState(player_name="林岚", week=4)
        service = CollectionService(session)

        character = service.create_character(state, "  陈舟  ")
        landmark = service.create_landmark(state, "  旧书院  ")

        assert character == {
            "name": "陈舟",
            "role": "",
            "relationship_desc": "",
            "affinity": 50,
            "image_generated": False,
        }
        assert landmark == {
            "name": "旧书院",
            "description": "",
            "category": "other",
            "importance": "normal",
            "first_appear_week": 4,
            "appear_count": 1,
            "last_appear_week": 4,
            "context": "",
            "is_key_location": False,
            "image_generated": False,
        }
        assert state.characters["陈舟"]["affinity"] == 50
        assert state.landmarks["旧书院"]["first_appear_week"] == 4
        with pytest.raises(ValueError, match="已存在"):
            service.create_character(state, "陈舟")
        with pytest.raises(ValueError, match="主角"):
            service.create_character(state, "林岚")
        with pytest.raises(ValueError, match="不能为空"):
            service.create_landmark(state, "   ")
        with pytest.raises(ValueError, match="已存在"):
            service.create_landmark(state, "旧书院")
    finally:
        session.close()


def test_manual_character_creation_rejects_legacy_settings_protagonist_name() -> None:
    session = _session()
    try:
        state = PlayerState(
            player_name="",
            character_settings={"player_name": "林岚"},
            week=4,
        )

        with pytest.raises(ValueError, match="主角"):
            CollectionService(session).create_character(state, "林岚")
    finally:
        session.close()


def test_manual_character_creation_preserves_relationship_only_character() -> None:
    session = _session()
    try:
        state = PlayerState(
            player_name="林岚",
            relationships={"陈舟": 83},
            week=4,
        )

        with pytest.raises(ValueError, match="已存在"):
            CollectionService(session).create_character(state, "陈舟")

        assert "陈舟" not in state.characters
        assert state.relationships["陈舟"] == 83
    finally:
        session.close()


@pytest.mark.parametrize(
    ("character_settings", "name", "expected_role", "expected_description", "expected_affinity"),
    [
        (
            {
                "relationships": {
                    "key_people": [
                        {
                            "name": "陈舟",
                            "role": "导师",
                            "relationship_desc": "引路人",
                            "affinity": 73,
                        }
                    ]
                }
            },
            "陈舟",
            "导师",
            "引路人",
            73,
        ),
        (
            {
                "relationships": [
                    {
                        "name": "陆昊然",
                        "role": "直属导师",
                        "relationship": "产品团队导师",
                        "affinity": 70,
                    }
                ]
            },
            "陆昊然",
            "直属导师",
            "产品团队导师",
            70,
        ),
        (
            {
                "family": {
                    "family_members": [
                        {"name": "母亲", "role": "母亲", "relationship": "至亲"}
                    ]
                }
            },
            "母亲",
            "母亲",
            "至亲",
            80,
        ),
    ],
)
def test_manual_character_creation_rejects_partially_materialized_visible_people_without_shadowing_metadata(
    character_settings,
    name,
    expected_role,
    expected_description,
    expected_affinity,
) -> None:
    session = _session()
    try:
        state = PlayerState(
            player_name="林岚",
            character_settings=character_settings,
            relationships={name: expected_affinity},
            week=4,
        )
        service = CollectionService(session)

        with pytest.raises(ValueError, match="已存在"):
            service.create_character(state, name)

        assert name not in state.characters
        assert state.relationships[name] == expected_affinity
        visible = {
            character.name: character for character in service.get_collection(1, state).characters
        }[name]
        assert visible.role == expected_role
        assert visible.description == expected_description
        assert visible.affinity == expected_affinity
    finally:
        session.close()


def test_character_removal_cleans_linked_image_and_protects_player() -> None:
    session = _session()
    try:
        game = _game(session)
        image = Image(
            game_id=game.game_id,
            image_type="character",
            entity_name="陈舟",
            entity_key="npc-chen-zhou",
            prompt_text="contract image",
            storage_path="contracts/chen-zhou.png",
            storage_type="local",
            is_active=True,
        )
        session.add(image)
        session.commit()
        state = PlayerState.from_dict(
            {
                "player_name": "林岚",
                "week": 4,
                "characters": {"陈舟": {"name": "陈舟", "role": "同事"}},
            }
        )
        service = CollectionService(session)

        assert service.delete_character(int(game.game_id), "陈舟", state) is True
        assert "陈舟" not in state.characters
        assert session.get(Image, image.image_id) is None
        with pytest.raises(PermissionDeniedError, match="不能删除主角"):
            service.delete_character(int(game.game_id), "林岚", state)
        with pytest.raises(EntityNotFoundError, match="不存在"):
            service.delete_character(int(game.game_id), "陌生人", state)
    finally:
        session.close()


def test_character_removal_can_defer_linked_image_cleanup_until_state_is_persisted() -> None:
    session = _session()
    try:
        game = _game(session)
        image = Image(
            game_id=game.game_id,
            image_type="character",
            entity_name="陈舟",
            entity_key="npc-chen-zhou-deferred",
            prompt_text="deferred cleanup contract",
            storage_path="contracts/chen-zhou-deferred.png",
            storage_type="local",
            is_active=True,
        )
        session.add(image)
        session.commit()
        image_id = int(image.image_id)
        state = PlayerState.from_dict(
            {
                "player_name": "林岚",
                "week": 4,
                "characters": {"陈舟": {"name": "陈舟", "role": "同事"}},
            }
        )
        service = CollectionService(session)

        assert service.delete_character(
            int(game.game_id), "陈舟", state, delete_images=False
        ) is True
        assert session.get(Image, image_id) is not None

        service._delete_entity_image_records(int(game.game_id), "character", "陈舟")
        assert session.get(Image, image_id) is None
    finally:
        session.close()


@pytest.mark.parametrize(
    ("preset_section", "preset_name", "materialized_name"),
    [
        ("key_people", " 陈舟 ", " 陈舟 "),
        ("key_people", " 陈舟 ", "陈舟"),
        ("family_members", " 陈舟 ", " 陈舟 "),
        ("family_members", " 陈舟 ", "陈舟"),
    ],
)
def test_character_removal_rejects_materialized_preset_people(
    preset_section: str,
    preset_name: str,
    materialized_name: str,
) -> None:
    session = _session()
    try:
        settings = (
            {"relationships": {"key_people": [{"name": preset_name}]}}
            if preset_section == "key_people"
            else {"family": {"family_members": [{"name": preset_name}]}}
        )
        state = PlayerState.from_dict(
            {
                "player_name": "林岚",
                "character_settings": settings,
                "characters": {
                    materialized_name: {"name": materialized_name, "role": "旧识"}
                },
            }
        )
        service = CollectionService(session)

        visible = {
            character.name: character
            for character in service.get_collection(1, state).characters
        }[materialized_name]
        assert visible.can_delete is False

        with pytest.raises(PermissionDeniedError, match="预设人物"):
            service.delete_character(1, materialized_name, state)

        assert materialized_name in state.characters
    finally:
        session.close()


def test_game_ownership_lookup_rejects_missing_and_foreign_games() -> None:
    session = _session()
    try:
        owner = _user(session, "ownera")
        other = _user(session, "otherb")
        game = _game(session, user_id=int(owner.user_id))
        service = CollectionService(session)

        assert service.verify_game_ownership(int(game.game_id), int(owner.user_id)) is game
        with pytest.raises(EntityNotFoundError, match="无权访问"):
            service.verify_game_ownership(int(game.game_id), int(other.user_id))
        with pytest.raises(EntityNotFoundError, match="无权访问"):
            service.verify_game_ownership(999999, int(owner.user_id))
    finally:
        session.close()
