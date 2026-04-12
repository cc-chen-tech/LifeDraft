"""SQL 查询计数测试 - 防止 N+1 回归。

验证 CollectionService.get_collection 使用批量查询，
查询次数不应随实体数量线性增长。
"""

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker
from unittest.mock import MagicMock, patch

from src.database.models import Base, Game, User
from src.database.models import Image as ImageModel
from src.game.state import PlayerState
from src.services.collection_service import CollectionService


@pytest.fixture
def perf_db_engine():
    """创建用于性能测试的内存数据库。"""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture
def perf_db_session(perf_db_engine):
    """创建性能测试数据库会话。"""
    Session = sessionmaker(bind=perf_db_engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def populated_game(perf_db_session):
    """创建一个包含多个实体和图片的游戏。"""
    user = User(
        private_id="PERF-TEST-USER-001",
        public_id="PERFUSR1",
        display_name="PerfTestUser",
    )
    perf_db_session.add(user)
    perf_db_session.commit()

    game = Game(
        user_id=user.user_id,
        initial_state={"player_name": "性能测试主角", "week": 10, "age": 25},
    )
    perf_db_session.add(game)
    perf_db_session.commit()

    # 创建多个角色的图片（模拟真实场景）
    character_names = [f"角色_{i}" for i in range(10)]
    item_names = [f"物品_{i}" for i in range(5)]
    landmark_names = [f"地点_{i}" for i in range(5)]

    for name in character_names:
        img = ImageModel(
            game_id=game.game_id,
            image_type="character",
            entity_name=name,
            entity_key=f"npc_{name}",
            prompt_text=f"prompt for {name}",
            storage_path=f"/tmp/test/{name}.png",
            storage_type="local",
            is_active=True,
        )
        perf_db_session.add(img)

    for name in item_names:
        img = ImageModel(
            game_id=game.game_id,
            image_type="item",
            entity_name=name,
            entity_key=f"item_{name}",
            prompt_text=f"prompt for {name}",
            storage_path=f"/tmp/test/{name}.png",
            storage_type="local",
            is_active=True,
        )
        perf_db_session.add(img)

    for name in landmark_names:
        img = ImageModel(
            game_id=game.game_id,
            image_type="landmark",
            entity_name=name,
            entity_key=f"landmark_{name}",
            prompt_text=f"prompt for {name}",
            storage_path=f"/tmp/test/{name}.png",
            storage_type="local",
            is_active=True,
        )
        perf_db_session.add(img)

    perf_db_session.commit()

    # 构建 PlayerState
    player_state = PlayerState(
        player_name="性能测试主角",
        character_settings={
            "relationships": {"key_people": []},
            "family": {"family_members": []},
        },
    )

    # 添加角色到 player_state
    for name in character_names:
        player_state.characters[name] = {
            "role": "NPC",
            "relationship_desc": f"{name} 的描述",
            "affinity": 50,
        }

    # 添加物品到 player_state
    for name in item_names:
        player_state.items[name] = {
            "description": f"{name} 的描述",
            "importance": "normal",
            "category": "other",
            "acquired_week": 1,
        }

    # 添加地点到 player_state
    for name in landmark_names:
        player_state.landmarks[name] = {
            "description": f"{name} 的描述",
            "category": "other",
            "importance": "normal",
            "first_appear_week": 1,
            "appear_count": 3,
            "last_appear_week": 5,
        }

    return game, player_state, character_names, item_names, landmark_names


class TestCollectionQueryCount:
    """验证 collection_service 的查询次数不会出现 N+1 问题。"""

    def test_collection_no_n_plus_one(self, perf_db_session, populated_game):
        """collection_service 查询次数应 ≤ 10（之前 N+1 时是 29+）。

        使用 SQLAlchemy event listener 精确计算查询次数。
        """
        game, player_state, char_names, item_names, landmark_names = populated_game
        query_count = 0
        queries = []

        def count_queries(conn, cursor, statement, parameters, context, executemany):
            nonlocal query_count
            query_count += 1
            queries.append(statement[:100])

        # 监听该 session 绑定的 engine
        target_engine = perf_db_session.get_bind()
        event.listen(target_engine, "before_cursor_execute", count_queries)

        try:
            with patch("src.services.collection_service.ImageService") as mock_img_cls:
                mock_img_service = MagicMock()
                mock_img_service.get_image_url.return_value = "/test/image.png"
                mock_img_cls.return_value = mock_img_service

                with patch("src.services.collection_service.ImageStorageService"):
                    service = CollectionService(perf_db_session)
                    service.image_service = mock_img_service

                    result = service.get_collection(game.game_id, player_state)

            # 验证返回数据完整
            assert result.total_characters > 0
            assert result.total_items == len(item_names)
            assert result.total_landmarks == len(landmark_names)

            # ★ 核心断言：查询次数应该是 O(1) 级别的批量查询
            # 3 次批量查询（character、item、landmark 各一次）+ 少量其他查询
            assert query_count <= 10, (
                f"查询次数过多：{query_count} 次（应 ≤ 10），"
                f"可能存在 N+1 问题。\n查询列表：\n"
                + "\n".join(f"  {i+1}. {q}" for i, q in enumerate(queries))
            )

        finally:
            event.remove(target_engine, "before_cursor_execute", count_queries)

    def test_batch_query_covers_all_entity_types(self, perf_db_session, populated_game):
        """验证批量查询分别覆盖 character、item、landmark 三种类型。"""
        game, player_state, _, _, _ = populated_game
        queried_types = []

        def track_image_queries(conn, cursor, statement, parameters, context, executemany):
            stmt_lower = statement.lower()
            if "images" in stmt_lower and "image_type" in stmt_lower:
                queried_types.append(statement)

        target_engine = perf_db_session.get_bind()
        event.listen(target_engine, "before_cursor_execute", track_image_queries)

        try:
            with patch("src.services.collection_service.ImageService") as mock_img_cls:
                mock_img_service = MagicMock()
                mock_img_service.get_image_url.return_value = "/test/image.png"
                mock_img_cls.return_value = mock_img_service

                with patch("src.services.collection_service.ImageStorageService"):
                    service = CollectionService(perf_db_session)
                    service.image_service = mock_img_service
                    service.get_collection(game.game_id, player_state)

            # 应该恰好有 3 次图片批量查询
            assert len(queried_types) == 3, (
                f"图片查询次数应为 3（character/item/landmark 各一次），"
                f"实际 {len(queried_types)} 次"
            )

        finally:
            event.remove(target_engine, "before_cursor_execute", track_image_queries)

    def test_empty_collection_minimal_queries(self, perf_db_session):
        """空收集数据的查询次数应很少。"""
        user = User(
            private_id="EMPTY-TEST-USER-001",
            public_id="EMTPUSR1",
            display_name="EmptyTestUser",
        )
        perf_db_session.add(user)
        perf_db_session.commit()

        game = Game(
            user_id=user.user_id,
            initial_state={"player_name": "空数据主角", "week": 1, "age": 25},
        )
        perf_db_session.add(game)
        perf_db_session.commit()

        player_state = PlayerState(
            player_name="空数据主角",
            character_settings={},
        )

        query_count = 0

        def count_queries(conn, cursor, statement, parameters, context, executemany):
            nonlocal query_count
            query_count += 1

        target_engine = perf_db_session.get_bind()
        event.listen(target_engine, "before_cursor_execute", count_queries)

        try:
            with patch("src.services.collection_service.ImageService") as mock_img_cls:
                mock_img_service = MagicMock()
                mock_img_cls.return_value = mock_img_service

                with patch("src.services.collection_service.ImageStorageService"):
                    service = CollectionService(perf_db_session)
                    service.image_service = mock_img_service
                    result = service.get_collection(game.game_id, player_state)

            # 空数据也应该有批量查询（3次），但无额外查询
            assert query_count <= 5, f"空数据查询次数过多：{query_count}"
            assert result.total_characters == 1  # 只有主角
            assert result.total_items == 0
            assert result.total_landmarks == 0

        finally:
            event.remove(target_engine, "before_cursor_execute", count_queries)
