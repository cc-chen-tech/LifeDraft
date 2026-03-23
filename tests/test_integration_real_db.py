"""真实数据库集成测试

使用真实数据库连接，验证完整的数据流。
比 mock 测试慢，但能发现更多问题。
"""

import pytest
from sqlalchemy.orm import Session

from src.database.models import SessionLocal, Game, User
from src.api.routers.collection import _add_entities_to_collection_sync


class TestRealDatabaseIntegration:
    """真实数据库集成测试"""

    @pytest.fixture(scope="function")
    def db_session(self):
        """提供数据库会话，测试后回滚"""
        session = SessionLocal()
        try:
            yield session
        finally:
            session.rollback()
            session.close()

    def test_add_entities_to_empty_game(self, db_session):
        """测试向空游戏添加实体"""
        # 创建测试用户（如果不存在）
        user = db_session.query(User).filter(User.user_id == 9999).first()
        if not user:
            import secrets
            user = User(
                user_id=9999,
                private_id=secrets.token_hex(16),
                public_id=secrets.token_hex(4)
            )
            db_session.add(user)
            db_session.commit()

        # 创建测试游戏
        game = Game(
            language="zh",
            user_id=9999,
            initial_state={
                "week": 1,
                "age": 22,
                "items": {},
                "relationships": {},
                "landmarks": {},
                "entity_appearances": {"items": {}, "characters": {}, "landmarks": {}}
            }
        )
        db_session.add(game)
        db_session.commit()
        db_session.refresh(game)

        try:
            # 调用真实函数
            result = _add_entities_to_collection_sync(
                db=db_session,
                game_id=game.game_id,
                user_id=9999,
                items=[{
                    "name": "测试宝剑",
                    "description": "一把锋利的剑",
                    "category": "weapon",
                    "importance": "critical",
                    "appear_count": 3,
                    "appear_contexts": ["在武器店发现"]
                }],
                characters=[],
                landmarks=[]
            )

            # 验证结果格式
            assert isinstance(result, dict)
            assert "added_items" in result
            assert "added_characters" in result
            assert "added_landmarks" in result

            # 注：由于 _add_entities_to_collection_sync 使用 GameDatabase
            # 它会通过 save_game_progress 保存到 GameState 表
            # 而不是直接更新 Game 表的 initial_state
            # 这里我们主要验证函数执行没有报错
            # 真实的数据验证需要查询 GameState 表

        finally:
            # 清理测试数据
            db_session.delete(game)
            db_session.commit()

    def test_add_entities_below_threshold(self, db_session):
        """测试添加出现次数不足的实体（不会被添加）"""
        # 创建测试用户
        user = db_session.query(User).filter(User.user_id == 9999).first()
        if not user:
            import secrets
            user = User(
                user_id=9999,
                private_id=secrets.token_hex(16),
                public_id=secrets.token_hex(4)
            )
            db_session.add(user)
            db_session.commit()

        # 创建测试游戏
        game = Game(
            language="zh",
            user_id=9999,
            initial_state={
                "week": 1,
                "age": 22,
                "items": {},
                "relationships": {},
                "landmarks": {},
                "entity_appearances": {"items": {}, "characters": {}, "landmarks": {}}
            }
        )
        db_session.add(game)
        db_session.commit()
        db_session.refresh(game)

        try:
            # 添加出现次数不足的实体
            result = _add_entities_to_collection_sync(
                db=db_session,
                game_id=game.game_id,
                user_id=9999,
                items=[{
                    "name": "普通石头",
                    "description": "一块石头",
                    "category": "other",
                    "importance": "normal",
                    "appear_count": 1,  # 不足3次
                    "appear_contexts": ["在地上看到"]
                }],
                characters=[],
                landmarks=[]
            )

           # 验证物品未被添加（因为 appear_count < 3）
            assert len(result["added_items"]) == 0

        finally:
            # 清理
            db_session.delete(game)
            db_session.commit()


class TestAddEntitiesIntegration:
    """_add_entities_to_collection_sync 集成测试
    
    测试关键场景：
    1. 游戏无有效状态时的优雅降级
    2. is_batch=True vs is_batch=False 的阈值差异
    3. 已存在实体不被重复添加
    4. entity_appearances 的累积逻辑
    5. session 失效验证
    """

    @pytest.fixture(scope="function")
    def db_session(self):
        """提供数据库会话，测试后回滚"""
        session = SessionLocal()
        try:
            yield session
        finally:
            session.rollback()
            session.close()

    @pytest.fixture(scope="function")
    def test_user(self, db_session):
        """创建或获取测试用户"""
        user = db_session.query(User).filter(User.user_id == 9998).first()
        if not user:
            import secrets
            user = User(
                user_id=9998,
                private_id=secrets.token_hex(16),
                public_id=secrets.token_hex(4)
            )
            db_session.add(user)
            db_session.commit()
        return user

    @pytest.fixture(scope="function")
    def test_game_with_state(self, db_session, test_user):
        """创建带有 GameState 的测试游戏"""
        from src.database.models import GameState as GameStateModel
        
        game = Game(
            language="zh",
            user_id=test_user.user_id,
            initial_state={
                "week": 3,
                "age": 22,
                "items": {},
                "relationships": {},
                "landmarks": {},
                "characters": {},
                "entity_appearances": {"items": {}, "characters": {}, "landmarks": {}}
            }
        )
        db_session.add(game)
        db_session.commit()
        db_session.refresh(game)
        
        # 创建 GameState 记录
        game_state = GameStateModel(
            game_id=game.game_id,
            week=3,
            age=22,
            state_json={
                "week": 3,
                "age": 22,
                "items": {},
                "relationships": {},
                "landmarks": {},
                "characters": {},
                "entity_appearances": {"items": {}, "characters": {}, "landmarks": {}}
            }
        )
        db_session.add(game_state)
        db_session.commit()
        
        yield game
        
        # 清理：删除 GameState 和 Game
        db_session.query(GameStateModel).filter(GameStateModel.game_id == game.game_id).delete()
        db_session.delete(game)
        db_session.commit()

    def test_no_saved_state_returns_empty(self, db_session, test_user):
        """游戏无有效状态时应优雅返回空结果"""
        # 创建游戏但不创建 GameState
        game = Game(
            language="zh",
            user_id=test_user.user_id,
            initial_state={}
        )
        db_session.add(game)
        db_session.commit()
        db_session.refresh(game)
        
        try:
            # 调用函数，应返回空结果而非报错
            result = _add_entities_to_collection_sync(
                db=db_session,
                game_id=game.game_id,
                user_id=test_user.user_id,
                items=[{"name": "测试物品", "appear_count": 5}],
                characters=[],
                landmarks=[],
                is_batch=True,
            )
            
            # 验证返回空结果
            assert result == {"added_items": [], "added_characters": [], "added_landmarks": []}
        
        finally:
            db_session.delete(game)
            db_session.commit()

    def test_is_batch_true_uses_threshold_1(self, db_session, test_game_with_state, test_user):
        """is_batch=True 时阈值为1，单次出现即可添加"""
        from unittest.mock import patch
        
        # 使用 mock 跳过 session_service.remove（避免影响其他测试）
        with patch('src.api.routers.collection.session_service'):
            result = _add_entities_to_collection_sync(
                db=db_session,
                game_id=test_game_with_state.game_id,
                user_id=test_user.user_id,
                items=[{
                    "name": "批量模式物品",
                    "description": "测试物品",
                    "appear_count": 1,  # 只出现1次
                    "importance": "normal",
                    "category": "other",
                }],
                characters=[],
                landmarks=[],
                is_batch=True,  # 批量模式，阈值为1
            )
            
            # 验证物品被添加（因为 is_batch=True，阈值为1）
            assert "批量模式物品" in result["added_items"]

    def test_is_batch_false_uses_threshold_3(self, db_session, test_game_with_state, test_user):
        """is_batch=False 时阈值为3，需要>=3次出现才能添加"""
        from unittest.mock import patch
        
        with patch('src.api.routers.collection.session_service'):
            # 传入 appear_count=2 的实体
            result1 = _add_entities_to_collection_sync(
                db=db_session,
                game_id=test_game_with_state.game_id,
                user_id=test_user.user_id,
                items=[{
                    "name": "增量模式物品",
                    "description": "测试物品",
                    "appear_count": 2,  # 只出现2次，不足3次
                    "importance": "normal",
                    "category": "other",
                }],
                characters=[],
                landmarks=[],
                is_batch=False,  # 增量模式，阈值为3
            )
            
            # 验证物品未被添加（因为 appear_count < 3）
            assert "增量模式物品" not in result1["added_items"]

    def test_existing_entity_not_duplicated(self, db_session, test_user):
        """已存在于 PlayerState 中的实体不被重复添加"""
        from src.database.models import GameState as GameStateModel
        from unittest.mock import patch
        
        # 创建包含物品"剑"的游戏状态
        game = Game(
            language="zh",
            user_id=test_user.user_id,
            initial_state={}
        )
        db_session.add(game)
        db_session.commit()
        db_session.refresh(game)
        
        # 创建带有已存在物品的 GameState
        state_with_item = {
            "week": 3,
            "age": 22,
            "items": {
                "剑": {
                    "name": "剑",
                    "description": "一把普通的剑",
                    "importance": "normal",
                    "category": "weapon",
                }
            },
            "relationships": {},
            "landmarks": {},
            "characters": {},
            "entity_appearances": {"items": {"剑": 5}, "characters": {}, "landmarks": {}}
        }
        game_state = GameStateModel(
            game_id=game.game_id,
            week=3,
            age=22,
            state_json=state_with_item
        )
        db_session.add(game_state)
        db_session.commit()
        
        try:
            with patch('src.api.routers.collection.session_service'):
                result = _add_entities_to_collection_sync(
                    db=db_session,
                    game_id=game.game_id,
                    user_id=test_user.user_id,
                    items=[{
                        "name": "剑",  # 已存在的物品
                        "description": "一把剑",
                        "appear_count": 5,
                        "importance": "normal",
                        "category": "weapon",
                    }],
                    characters=[],
                    landmarks=[],
                    is_batch=True,
                )
                
                # 验证"剑"不在 added_items 中（因为已存在）
                assert "剑" not in result["added_items"]
        
        finally:
            db_session.query(GameStateModel).filter(GameStateModel.game_id == game.game_id).delete()
            db_session.delete(game)
            db_session.commit()

    def test_session_invalidation_after_save(self, db_session, test_game_with_state, test_user):
        """保存后 session_service.remove() 被调用"""
        from unittest.mock import patch, MagicMock
        
        mock_session_service = MagicMock()
        
        with patch('src.api.routers.collection.session_service', mock_session_service):
            _add_entities_to_collection_sync(
                db=db_session,
                game_id=test_game_with_state.game_id,
                user_id=test_user.user_id,
                items=[{
                    "name": "会话失效测试物品",
                    "description": "测试",
                    "appear_count": 3,
                    "importance": "normal",
                    "category": "other",
                }],
                characters=[],
                landmarks=[],
                is_batch=True,
            )
            
            # 验证 remove 被调用了正确的 game_id
            mock_session_service.remove.assert_called_once_with(test_game_with_state.game_id)

    def test_multiple_entity_types_in_single_call(self, db_session, test_game_with_state, test_user):
        """单次调用可同时添加多种类型的实体"""
        from unittest.mock import patch
        
        with patch('src.api.routers.collection.session_service'):
            result = _add_entities_to_collection_sync(
                db=db_session,
                game_id=test_game_with_state.game_id,
                user_id=test_user.user_id,
                items=[{
                    "name": "测试物品",
                    "description": "一个物品",
                    "appear_count": 3,
                    "importance": "normal",
                    "category": "other",
                }],
                characters=[{
                    "name": "测试人物",
                    "description": "一个人物",
                    "role": "配角",
                    "appear_count": 3,
                }],
                landmarks=[{
                    "name": "测试地点",
                    "description": "一个地点",
                    "category": "building",
                    "importance": "normal",
                    "appear_count": 3,
                }],
                is_batch=True,
            )
            
            # 验证三种类型都被添加
            assert "测试物品" in result["added_items"]
            assert "测试人物" in result["added_characters"]
            assert "测试地点" in result["added_landmarks"]
