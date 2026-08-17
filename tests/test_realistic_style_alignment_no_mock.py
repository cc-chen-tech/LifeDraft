"""No-mock contracts for realistic narrative-style authority."""

from __future__ import annotations

from uuid import uuid4

from src.ai.narrative.style_matcher import StyleMatcher
from src.database.db import GameDatabase
from src.database.models import Game, SessionLocal, User, init_db
from src.game.game_initializer import GameInitializer
import pytest

pytestmark = [pytest.mark.unit]



REALISTIC_PRODUCT_SETTINGS = {
    "era": {
        "year": 2026,
        "era_description": "当代上海现实主义职场，不使用未来科技设定",
    },
    "world": {
        "world_description": "与现实世界一致的产品经理成长故事，明确无超自然元素、禁止赛博朋克",
        "technology_level": "现实中的人工智能产品、企业网络和普通办公软件",
        "social_system": "现实法律和商业制度",
    },
    "background": {"occupation": "产品经理"},
    "traits": {"personality": ["务实", "理性"]},
}


def test_explicit_realism_overrides_incidental_cyberpunk_keywords() -> None:
    result = StyleMatcher().match(REALISTIC_PRODUCT_SETTINGS)

    assert result.style_id == "nonfiction_novel"
    assert result.style_id not in {"cyberpunk", "magical_realism"}
    assert result.confidence >= 0.15


def test_explicit_positive_cyberpunk_remains_cyberpunk() -> None:
    result = StyleMatcher().match(
        {
            "era": {"year": 2077, "era_description": "原创赛博朋克未来都市"},
            "world": {
                "world_description": "高科技低生活、义体和企业控制构成核心世界观",
                "technology_level": "神经芯片、黑客网络和机械义体",
            },
        }
    )

    assert result.style_id == "cyberpunk"


def test_realistic_style_survives_initializer_database_round_trip() -> None:
    init_db()
    suffix = uuid4().hex[:10]
    session = SessionLocal()
    user_id: int | None = None
    game_id: int | None = None
    try:
        user = User(
            public_id=f"RS{suffix[:6].upper()}",
            private_id=f"realistic-style-{suffix}",
            display_name="现实风格测试",
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        user_id = int(user.user_id)

        initializer = GameInitializer(game_db=GameDatabase(), language="zh")
        _loop, game_id = initializer.initialize_game_from_settings(
            character_settings=REALISTIC_PRODUCT_SETTINGS,
            player_name="林晓",
            life_vision="现实主义产品经理成长，不要超自然或赛博朋克",
            user_id=user_id,
        )

        session.expire_all()
        stored = session.query(Game).filter(Game.game_id == game_id).one()
        loaded = GameDatabase().load_saved_game(game_id, user_id)

        assert stored.narrative_style_id == "nonfiction_novel"
        assert loaded is not None
        assert loaded["narrative_style_id"] == "nonfiction_novel"
    finally:
        if game_id is not None:
            session.query(Game).filter(Game.game_id == game_id).delete()
        if user_id is not None:
            session.query(User).filter(User.user_id == user_id).delete()
        session.commit()
        session.close()
