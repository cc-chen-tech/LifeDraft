"""Real database save-read coverage for qualified world facts."""

from __future__ import annotations

from uuid import uuid4

from src.database.db import GameDatabase
from src.database.models import Game, SessionLocal, User, init_db
from src.game.game_initializer import GameInitializer
from src.game.world_fact_safety import qualify_generated_world_facts


def test_qualified_world_setting_survives_real_database_round_trip() -> None:
    init_db()
    suffix = uuid4().hex[:10]
    session = SessionLocal()
    user_id: int | None = None
    game_id: int | None = None
    try:
        user = User(
            public_id=f"WF{suffix[:6].upper()}",
            private_id=f"world-fact-{suffix}",
            display_name="世界事实边界测试",
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        user_id = int(user.user_id)

        world = qualify_generated_world_facts(
            {
                "world_description": "需要取得数据隐私保护认证（DSR）。",
                "technology_level": "备案周期固定为4-6个月。",
                "social_system": "遵循现实社会制度。",
                "economy": "风险投资同比下降40%。",
            },
            language="zh",
        )
        initializer = GameInitializer(game_db=GameDatabase(), language="zh")
        _loop, game_id = initializer.initialize_game_from_settings(
            character_settings={
                "era": {"year": 2026, "era_description": "当代中国现实主义"},
                "world": world,
            },
            player_name="林晓",
            life_vision="现实主义教育科技产品经理成长",
            user_id=user_id,
        )

        loaded = GameDatabase().load_saved_game(game_id, user_id)

        assert loaded is not None
        loaded_world = loaded["character_settings"]["world"]
        assert loaded_world == world
        assert loaded_world["world_description"].startswith("故事设定假设")
        assert loaded_world["economy"].startswith("故事设定假设")
    finally:
        if game_id is not None:
            session.query(Game).filter(Game.game_id == game_id).delete()
        if user_id is not None:
            session.query(User).filter(User.user_id == user_id).delete()
        session.commit()
        session.close()

