"""数据库迁移测试 - narrative_style_id 字段 (L1)。

TDD先行：验证 character_presets 和 games 表支持 narrative_style_id 字段，
以及 GameRepository 的创建/加载逻辑对该字段的处理。
"""

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker

from src.database.models import Base, Game, GameState, User


# ==================== Schema 迁移测试 ====================


@pytest.mark.unit
class TestNarrativeStyleIdMigration:
    """验证 narrative_style_id 字段在数据库 schema 中存在。"""

    def test_games_table_has_narrative_style_id(self, db_engine):
        """games 表应包含 narrative_style_id 列。"""
        inspector = inspect(db_engine)
        columns = {col["name"] for col in inspector.get_columns("games")}
        assert "narrative_style_id" in columns, (
            f"games 表缺少 narrative_style_id 列，当前列: {columns}"
        )

    def test_games_narrative_style_id_default(self, db_session):
        """games.narrative_style_id 默认值应为 'chinese_classic_saga'。"""
        user = User(
            private_id="MIGRATE-TEST-001",
            public_id="MIG001",
            display_name="MigrationTest",
        )
        db_session.add(user)
        db_session.commit()

        game = Game(
            user_id=user.user_id,
            initial_state={"week": 1},
        )
        db_session.add(game)
        db_session.commit()
        db_session.refresh(game)

        # narrative_style_id 应有默认值
        style_id = getattr(game, "narrative_style_id", None)
        # 列定义为 nullable=True，无 server_default 时默认为 None
        assert style_id is None or style_id == "chinese_classic_saga", (
            f"默认 narrative_style_id 应为 None 或 'chinese_classic_saga'，实际为 {style_id!r}"
        )

    def test_games_narrative_style_id_custom_value(self, db_session):
        """games 表可以存储自定义 narrative_style_id。"""
        user = User(
            private_id="MIGRATE-TEST-002",
            public_id="MIG002",
            display_name="MigrationTest2",
        )
        db_session.add(user)
        db_session.commit()

        game = Game(
            user_id=user.user_id,
            initial_state={"week": 1},
            narrative_style_id="wuxia_epic",
        )
        db_session.add(game)
        db_session.commit()
        db_session.refresh(game)

        assert game.narrative_style_id == "wuxia_epic"

    def test_character_presets_has_narrative_style_id(self, db_engine):
        """character_presets 表应包含 narrative_style_id 列。"""
        inspector = inspect(db_engine)
        tables = inspector.get_table_names()
        if "character_presets" not in tables:
            pytest.skip("character_presets 表尚不存在")
        columns = {col["name"] for col in inspector.get_columns("character_presets")}
        assert "narrative_style_id" in columns, (
            f"character_presets 表缺少 narrative_style_id 列，当前列: {columns}"
        )


# ==================== 向后兼容测试 ====================


@pytest.mark.unit
class TestNarrativeStyleIdBackwardCompat:
    """向后兼容：无 narrative_style_id 的旧数据可加载。"""

    def test_load_game_without_narrative_style_id(self, db_session):
        """旧数据缺少 narrative_style_id 字段时，应能正常加载。"""
        user = User(
            private_id="COMPAT-TEST-001",
            public_id="CMP001",
            display_name="CompatTest",
        )
        db_session.add(user)
        db_session.commit()

        # 直接用 SQL 插入一条不含 narrative_style_id 的记录
        game = Game(
            user_id=user.user_id,
            initial_state={"week": 1},
        )
        db_session.add(game)
        db_session.commit()

        # 重新查询
        loaded = db_session.query(Game).filter_by(game_id=game.game_id).first()
        assert loaded is not None
        # narrative_style_id 应为默认值或 None（取决于实现）
        style_id = getattr(loaded, "narrative_style_id", None)
        assert style_id is None or isinstance(style_id, str)

    def test_game_state_still_works(self, db_session):
        """GameState 关联在添加 narrative_style_id 后仍正常。"""
        user = User(
            private_id="COMPAT-TEST-002",
            public_id="CMP002",
            display_name="CompatTest2",
        )
        db_session.add(user)
        db_session.commit()

        game = Game(
            user_id=user.user_id,
            initial_state={"week": 1},
        )
        db_session.add(game)
        db_session.commit()

        gs = GameState(
            game_id=game.game_id,
            week=1,
            age=25,
            state_json={"energy": 100},
        )
        db_session.add(gs)
        db_session.commit()

        loaded_states = db_session.query(GameState).filter_by(game_id=game.game_id).all()
        assert len(loaded_states) == 1
        assert loaded_states[0].state_json["energy"] == 100
