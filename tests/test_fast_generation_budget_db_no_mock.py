"""Real DB save-read coverage for fast quality level."""

from uuid import uuid4

from src.database.db import GameDatabase
from src.database.models import SessionLocal, User, init_db


def test_fast_constraint_level_survives_real_database_save_read() -> None:
    init_db()
    session = SessionLocal()
    game_id: int | None = None
    try:
        suffix = uuid4().hex[:10]
        user = User(
            private_id=f"fast-budget-{suffix}",
            public_id=f"FB{suffix[:6].upper()}",
            display_name="快速预算测试",
        )
        session.add(user)
        session.commit()
        session.refresh(user)

        database = GameDatabase()
        game_id = database.create_game(
            language="zh",
            initial_state={"player_name": "林晓", "constraint_level": "fast"},
            user_id=int(user.user_id),
            constraint_level="fast",
        )
        loaded = database.get_game(game_id, int(user.user_id))

        assert loaded is not None
        assert loaded.constraint_level == "fast"
    finally:
        if game_id is not None:
            game = GameDatabase().get_game(game_id)
            if game is not None:
                session.delete(session.merge(game))
        session.commit()
        session.close()

