"""Real database save-read coverage for recognized collection entities."""

from uuid import uuid4

from src.database.db import GameDatabase
from src.database.models import SessionLocal, User, init_db
from src.game.state import PlayerState
from src.services.collection_service import CollectionService


def test_recognized_entities_survive_real_database_save_read() -> None:
    init_db()
    suffix = uuid4().hex[:10]
    session = SessionLocal()
    database = GameDatabase()
    try:
        user = User(
            private_id=f"entity-private-{suffix}",
            public_id=f"ec{suffix[:6]}",
            display_name="Entity Reliability",
        )
        session.add(user)
        session.commit()
        session.refresh(user)

        state = PlayerState.from_dict(
            {"player_name": "沈砚秋", "age": 29, "week": 3, "characters": {}, "items": {}, "landmarks": {}}
        )
        game_id = database.create_game(
            language="zh", initial_state=state.to_dict(), user_id=int(user.user_id)
        )

        result = CollectionService(session).add_entities(
            state,
            items=[{"name": "银色戒指", "description": "一枚旧戒指", "category": "other"}],
            characters=[{"name": "陈远", "description": "审计联系人", "role": "同事"}],
            landmarks=[{"name": "浦东办公室", "description": "项目会议地点", "category": "building"}],
        )
        assert database.save_game_progress(game_id, state) is True

        loaded = database.load_saved_game(game_id, int(user.user_id))

        assert result == {
            "added_items": ["银色戒指"],
            "added_characters": ["陈远"],
            "added_landmarks": ["浦东办公室"],
        }
        assert loaded is not None
        assert "陈远" in loaded["characters"]
        assert "银色戒指" in loaded["items"]
        assert "浦东办公室" in loaded["landmarks"]
    finally:
        session.rollback()
        session.close()
