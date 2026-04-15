"""constraint_level 真实 DB 集成测试 (Layer 4).

验证 Game 和 CharacterPreset 的 constraint_level 字段
在保存→读取链路中的完整性.
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database.models import Base, Game, CharacterPreset
from src.database.game_repository import GameRepository


@pytest.fixture(scope="module")
def db_session():
    """使用内存 SQLite 创建测试数据库会话."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


class TestGameConstraintLevel:
    """Game 表的 constraint_level 集成测试."""

    def test_create_game_with_constraint_level(self, db_session):
        """创建 Game 时传入 constraint_level，读取后值不变."""
        game = Game(
            initial_state={},
            constraint_level="master",
        )
        db_session.add(game)
        db_session.commit()
        db_session.refresh(game)

        assert game.constraint_level == "master"

    def test_game_constraint_level_default(self, db_session):
        """不传 constraint_level 时，默认值为 expert."""
        game = Game(initial_state={})
        db_session.add(game)
        db_session.commit()
        db_session.refresh(game)

        assert game.constraint_level == "expert"

    def test_game_repository_passes_constraint_level(self, db_session):
        """GameRepository.create_game 能正确传递 constraint_level."""
        repo = GameRepository()
        game_id = repo.create_game(
            initial_state={"week": 1},
            constraint_level="fast",
            db=db_session,
        )

        game = db_session.query(Game).filter_by(game_id=game_id).first()
        assert game is not None
        assert game.constraint_level == "fast"


class TestCharacterPresetConstraintLevel:
    """CharacterPreset 表的 constraint_level 集成测试."""

    def test_create_preset_with_constraint_level(self, db_session):
        """创建 CharacterPreset 时传入 constraint_level，读取后值不变."""
        preset = CharacterPreset(
            preset_name="测试预设",
            player_name="测试玩家",
            character_settings={},
            constraint_level="fast",
        )
        db_session.add(preset)
        db_session.commit()
        db_session.refresh(preset)

        assert preset.constraint_level == "fast"

    def test_preset_constraint_level_default(self, db_session):
        """不传 constraint_level 时，默认值为 expert."""
        preset = CharacterPreset(
            preset_name="测试预设",
            player_name="测试玩家",
            character_settings={},
        )
        db_session.add(preset)
        db_session.commit()
        db_session.refresh(preset)

        assert preset.constraint_level == "expert"
