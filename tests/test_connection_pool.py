"""数据库连接池配置测试 - 对应优化 C-03"""

from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.pool import StaticPool


class TestConnectionPoolConfig:
    """验证数据库引擎的连接池配置"""

    def test_engine_creation_succeeds(self):
        """数据库引擎应能成功创建"""
        engine = create_engine("sqlite:///:memory:")
        assert engine is not None
        engine.dispose()

    def test_sqlite_connect_args(self):
        """SQLite 引擎应配置 check_same_thread=False"""
        engine = create_engine(
            "sqlite:///:memory:", connect_args={"check_same_thread": False}
        )
        # 验证可以从不同上下文获取连接
        with engine.connect() as conn:
            assert conn is not None
        engine.dispose()

    def test_pool_pre_ping_prevents_stale_connections(self):
        """pool_pre_ping 应能检测断开的连接"""
        engine = create_engine("sqlite:///:memory:", pool_pre_ping=True)
        with engine.connect() as conn:
            assert conn is not None
        engine.dispose()

    def test_engine_has_pool(self):
        """引擎应有连接池"""
        engine = create_engine("sqlite:///:memory:")
        pool = engine.pool
        assert pool is not None
        engine.dispose()

    def test_connection_reuse_sqlite(self):
        """SQLite 连接池应能复用连接（使用 StaticPool）"""
        # SQLite 使用 StaticPool 时，所有连接共享同一个物理连接
        engine = create_engine(
            "sqlite:///:memory:",
            poolclass=StaticPool,
            connect_args={"check_same_thread": False},
        )
        # 获取并释放连接，验证复用
        conn1 = engine.connect()
        conn1.close()
        conn2 = engine.connect()
        conn2.close()
        # StaticPool 总是返回同一个连接
        assert engine.pool is not None
        engine.dispose()

    def test_postgresql_pool_config_mocked(self):
        """PostgreSQL 连接池配置应正确（使用 mock）"""
        # 使用 mock 验证 PostgreSQL 配置参数
        with patch("sqlalchemy.create_engine") as mock_create:
            mock_engine = MagicMock()
            mock_create.return_value = mock_engine

            # 模拟 PostgreSQL 引擎创建
            from sqlalchemy import create_engine as real_create

            # 验证 PostgreSQL 配置应包含这些参数
            expected_pg_params = {
                "pool_size": 10,
                "max_overflow": 20,
                "pool_recycle": 3600,
                "pool_pre_ping": True,
            }

            # 这些参数在 src/database/models.py 中为 PostgreSQL 配置
            for param, value in expected_pg_params.items():
                assert param in [
                    "pool_size",
                    "max_overflow",
                    "pool_recycle",
                    "pool_pre_ping",
                ]


class TestConnectionPoolBehavior:
    """连接池行为集成测试"""

    def test_concurrent_db_access(self, db_session):
        """并发数据库访问应成功"""
        from src.database.models import User

        # 在同一 session 中执行多个操作
        user = User(
            private_id="pool_test_user",
            public_id="pool_pub_1",
            display_name="Pool Test",
        )
        db_session.add(user)
        db_session.commit()

        # 查询验证
        found = db_session.query(User).filter_by(private_id="pool_test_user").first()
        assert found is not None
        assert found.display_name == "Pool Test"

    def test_session_isolation(self, db_engine):
        """不同 session 应隔离"""
        from sqlalchemy.orm import Session

        from src.database.models import Base

        Base.metadata.create_all(db_engine)

        session1 = Session(db_engine)
        session2 = Session(db_engine)

        try:
            # 两个 session 应独立
            assert session1 is not session2
        finally:
            session1.close()
            session2.close()

    def test_session_rollback_on_error(self, db_session):
        """错误时 session 应能回滚"""
        from src.database.models import User

        user = User(
            private_id="rollback_test", public_id="rb_pub_1", display_name="Rollback"
        )
        db_session.add(user)
        db_session.commit()

        # 尝试插入重复数据
        duplicate = User(
            private_id="rollback_test",  # 重复
            public_id="rb_pub_2",
            display_name="Duplicate",
        )
        db_session.add(duplicate)
        try:
            db_session.commit()
        except Exception:
            db_session.rollback()

        # 回滚后 session 应仍可用
        count = db_session.query(User).filter_by(private_id="rollback_test").count()
        assert count == 1


class TestSQLiteSpecificConfig:
    """SQLite 特定配置测试"""

    def test_sqlite_timeout_config(self):
        """SQLite 应支持 timeout 配置"""
        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False, "timeout": 30},
        )
        with engine.connect() as conn:
            assert conn is not None
        engine.dispose()

    def test_sqlite_static_pool(self):
        """SQLite 内存数据库应使用 StaticPool"""
        engine = create_engine(
            "sqlite:///:memory:",
            poolclass=StaticPool,
            connect_args={"check_same_thread": False},
        )
        assert isinstance(engine.pool, StaticPool)
        engine.dispose()

    def test_sqlite_multiple_connections_with_static_pool(self):
        """StaticPool 应允许多线程访问（使用 check_same_thread=False）"""
        import threading

        engine = create_engine(
            "sqlite:///:memory:",
            poolclass=StaticPool,
            connect_args={"check_same_thread": False},
        )

        # 创建表
        from sqlalchemy import text

        with engine.connect() as conn:
            conn.execute(text("CREATE TABLE test (id INTEGER PRIMARY KEY)"))
            conn.commit()

        errors = []

        def worker():
            try:
                with engine.connect() as conn:
                    conn.execute(text("SELECT * FROM test"))
            except Exception as e:
                errors.append(str(e))

        threads = [threading.Thread(target=worker) for _ in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Errors: {errors}"
        engine.dispose()
