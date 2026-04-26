"""收集面板缓存优化 - 真实 DB 集成测试 (Layer 4).

验证 session 恢复和收集数据查询在真实数据库中的保存→读取链路完整。
"""

from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.api.services.session_service import SessionService
from src.database.models import Base, User


@pytest.fixture(scope="module")
def db_session():
    """使用内存 SQLite 创建测试数据库会话."""
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    session = Session()
    yield session
    session.close()


class TestSessionServiceRestore:
    """SessionService 恢复链路集成测试."""

    def test_session_service_has_restore_method(self, db_session):
        """验证 SessionService 有数据库恢复能力."""
        service = SessionService()
        assert hasattr(service, "_restore_from_database")
        assert callable(getattr(service, "_restore_from_database"))

    def test_gamedb_can_save_and_load_game(self, db_session):
        """验证 GameDatabase 能正确保存和加载游戏."""
        from src.database.game_repository import GameRepository
        from src.database.state_repository import StateRepository

        game_repo = GameRepository()
        state_repo = StateRepository()

        # Patch SessionLocal 让 StateRepository 使用测试数据库
        with patch(
            "src.database.state_repository.SessionLocal", return_value=db_session
        ):
            # 创建用户（外键约束）
            user = User(
                private_id="TEST-USER-001",
                public_id="TESTUSR1",
                display_name="TestUser",
            )
            db_session.add(user)
            db_session.commit()

            # 创建游戏
            game_id = game_repo.create_game(
                user_id=user.user_id,
                initial_state={"player_name": "测试主角", "week": 1, "age": 25},
                db=db_session,
            )
            assert game_id is not None

            # 保存游戏进度
            from src.game.state import PlayerState

            player_state = PlayerState.from_dict(
                {"player_name": "测试主角", "week": 2, "age": 25}
            )

            saved = state_repo.save_game_progress(
                game_id=game_id,
                player_state=player_state,
            )
            assert saved is True

            # 读取保存的游戏
            loaded = state_repo.load_saved_game(game_id, user.user_id)
            assert loaded is not None
            assert loaded["player_name"] == "测试主角"

    def test_collection_service_get_collection(self, db_session):
        """验证 CollectionService 能正确构建收集数据."""
        from src.database.game_repository import GameRepository
        from src.database.state_repository import StateRepository
        from src.game.state import PlayerState
        from src.services.collection_service import CollectionService

        game_repo = GameRepository()
        state_repo = StateRepository()

        with patch(
            "src.database.state_repository.SessionLocal", return_value=db_session
        ):
            # 创建用户
            user = User(
                private_id="TEST-USER-002",
                public_id="TESTUSR2",
                display_name="TestUser2",
            )
            db_session.add(user)
            db_session.commit()

            # 创建游戏
            game_id = game_repo.create_game(
                user_id=user.user_id,
                initial_state={"player_name": "测试主角2", "week": 1, "age": 20},
                db=db_session,
            )

            # 保存带有一些收集数据的游戏进度
            player_state_data = {
                "player_name": "测试主角2",
                "week": 1,
                "age": 20,
                "characters": {
                    "NPC1": {
                        "role": "朋友",
                        "relationship_desc": "一个好朋友",
                        "affinity": 80,
                    }
                },
                "items": {
                    "宝剑": {
                        "description": "一把锋利的剑",
                        "importance": "important",
                        "category": "weapon",
                    }
                },
                "landmarks": {
                    "古城": {
                        "description": "一座古老的城",
                        "category": "building",
                        "importance": "normal",
                    }
                },
            }
            player_state = PlayerState.from_dict(player_state_data)

            state_repo.save_game_progress(
                game_id=game_id,
                player_state=player_state,
            )

            # 加载并构建 PlayerState
            loaded = state_repo.load_saved_game(game_id, user.user_id)
            assert loaded is not None

            restored_state = PlayerState.from_dict(loaded)

            # 使用 CollectionService 获取收集数据
            service = CollectionService(db_session)
            result = service.get_collection(game_id, restored_state)

            assert result.game_id == game_id
            assert len(result.characters) >= 1  # 至少包含主角
            assert len(result.items) == 1
            assert len(result.landmarks) == 1
            assert result.total_items == 1
            assert result.total_landmarks == 1
