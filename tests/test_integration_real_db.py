"""真实数据库集成测试

使用真实数据库连接，验证完整的数据流。
比 mock 测试慢，但能发现更多问题。

注意：原测试中使用的 _add_entities_to_collection_sync 函数已在代码重构中被移除。
相关测试用例已被清理。如需测试实体添加功能，请使用 API 端点测试。
"""

import pytest
from sqlalchemy import text

from src.database.models import Base, Game, SessionLocal, User


class TestRealDatabaseIntegration:
    """真实数据库集成测试"""

    @pytest.fixture(scope="function")
    def db_session(self):
        """提供数据库会话，测试后回滚"""
        Base.metadata.create_all(SessionLocal().bind)
        session = SessionLocal()
        try:
            yield session
        finally:
            session.rollback()
            session.close()

    def test_database_connection(self, db_session):
        """测试数据库连接正常"""
        # 简单的连接测试
        result = db_session.execute(text("SELECT 1")).scalar()
        assert result == 1

    def test_user_table_accessible(self, db_session):
        """测试 User 表可访问"""
        # 验证可以查询 User 表
        count = db_session.query(User).count()
        assert count >= 0  # 只验证查询成功

    def test_game_table_accessible(self, db_session):
        """测试 Game 表可访问"""
        # 验证可以查询 Game 表
        count = db_session.query(Game).count()
        assert count >= 0  # 只验证查询成功
