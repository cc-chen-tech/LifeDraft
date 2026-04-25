"""Era Validator Integration Tests

使用真实数据库连接，验证 Game 保存后 era 字段能正确传递至验证上下文。
Layer 4: 真实 DB 集成测试 — 保存→读取链路完整。
"""

import pytest

from src.database.models import Game, SessionLocal, User
from src.ai.story_generator import StoryGenerator
from src.ai.client import AIClient


class TestEraValidatorIntegration:
    """时代一致性验证器 DB 集成测试"""

    @pytest.fixture(scope="function")
    def db_session(self):
        """提供数据库会话，测试后回滚"""
        session = SessionLocal()
        try:
            yield session
        finally:
            session.rollback()
            session.close()

    def test_game_with_ancient_era_persists_character_settings(self, db_session):
        """古代 era 的 character_settings 保存→读取后，_extract_validation_context 包含 era/era_type"""
        # 查找或创建一个测试用户
        user = db_session.query(User).first()
        if not user:
            user = User(username="test_era_user", email="era@test.com")
            db_session.add(user)
            db_session.commit()
            db_session.refresh(user)

        character_settings = {
            "era": {
                "era_description": "南宋",
                "world_context": "中国历史上的南宋时期",
            },
            "world": {
                "world_description": "古代中国",
                "technology_level": "古代科技",
            },
        }

        game = Game(
            user_id=user.user_id,
            language="zh",
            initial_state={
                "player_name": "李逍遥",
                "character_settings": character_settings,
                "player_state": {"week": 1, "relationships": {}},
            },
        )
        db_session.add(game)
        db_session.commit()
        db_session.refresh(game)

        # 从 DB 重新加载
        loaded_game = db_session.query(Game).filter(Game.game_id == game.game_id).first()
        assert loaded_game is not None

        loaded_state = loaded_game.initial_state or {}
        loaded_character_settings = loaded_state.get("character_settings", {})

        # 使用 StoryGenerator 提取验证上下文
        gen = StoryGenerator(AIClient())
        player_state = loaded_state.get("player_state", {})
        ctx = gen._extract_validation_context(
            player_state=player_state,
            character_settings=loaded_character_settings,
        )

        assert "era" in ctx, "验证上下文缺少 'era' 键"
        assert "era_type" in ctx, "验证上下文缺少 'era_type' 键"
        assert ctx["era"] == "南宋"
        assert ctx["era_type"] == "ancient"

    def test_game_with_modern_era_returns_modern_type(self, db_session):
        """现代 era 保存→读取后，_extract_validation_context 返回 modern era_type"""
        user = db_session.query(User).first()
        if not user:
            user = User(username="test_era_user2", email="era2@test.com")
            db_session.add(user)
            db_session.commit()
            db_session.refresh(user)

        character_settings = {
            "era": {
                "era_description": "2024年现代中国",
                "world_context": "现代社会",
            },
        }

        game = Game(
            user_id=user.user_id,
            language="zh",
            initial_state={
                "player_name": "王小明",
                "character_settings": character_settings,
                "player_state": {"week": 1, "relationships": {}},
            },
        )
        db_session.add(game)
        db_session.commit()
        db_session.refresh(game)

        loaded_game = db_session.query(Game).filter(Game.game_id == game.game_id).first()
        loaded_state = loaded_game.initial_state or {}
        loaded_character_settings = loaded_state.get("character_settings", {})

        gen = StoryGenerator(AIClient())
        player_state = loaded_state.get("player_state", {})
        ctx = gen._extract_validation_context(
            player_state=player_state,
            character_settings=loaded_character_settings,
        )

        assert "era" in ctx
        assert "era_type" in ctx
        assert ctx["era"] == "2024年现代中国"
        assert ctx["era_type"] == "modern"

    def test_era_validator_with_db_loaded_ancient_context(self, db_session):
        """从 DB 加载的古代背景数据，验证器能正确检测现代元素"""
        from src.ai.harness.era_validator import validate_era_consistency

        user = db_session.query(User).first()
        if not user:
            user = User(username="test_era_user3", email="era3@test.com")
            db_session.add(user)
            db_session.commit()
            db_session.refresh(user)

        character_settings = {
            "era": {
                "era_description": "唐朝",
                "world_context": "古代中国",
            },
        }

        game = Game(
            user_id=user.user_id,
            language="zh",
            initial_state={
                "player_name": "李白",
                "character_settings": character_settings,
                "player_state": {"week": 1, "relationships": {}},
            },
        )
        db_session.add(game)
        db_session.commit()
        db_session.refresh(game)

        loaded_game = db_session.query(Game).filter(Game.game_id == game.game_id).first()
        loaded_state = loaded_game.initial_state or {}
        loaded_character_settings = loaded_state.get("character_settings", {})

        gen = StoryGenerator(AIClient())
        ctx = gen._extract_validation_context(
            player_state=loaded_state.get("player_state", {}),
            character_settings=loaded_character_settings,
        )

        # 验证 era_validator 能使用这个上下文正确工作
        passed, evidence, info = validate_era_consistency(
            "李白走进星巴克，点了一杯拿铁。",
            ctx,
        )
        assert passed is False, f"应检测到现代元素: {evidence}"
        assert "星巴克" in info.get("found_modern", []) or "拿铁" in info.get("found_modern", [])
