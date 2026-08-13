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
