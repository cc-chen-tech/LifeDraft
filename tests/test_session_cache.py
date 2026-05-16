"""Tests for session caching behavior."""

import time
from unittest.mock import MagicMock

from src.api.session_store import SESSION_TIMEOUT, SessionStore
from src.game.game_loop import GameLoop


class TestSessionCache:
    """Test session store caching behavior."""

    def test_session_created_and_retrieved(self):
        """Test that sessions can be created and retrieved."""
        store = SessionStore()

        # 创建 mock game_loop
        mock_game_loop = MagicMock(spec=GameLoop)

        # 创建 session
        store.put(game_id=1, game_loop=mock_game_loop, user_id=1)

        # 验证可以获取
        retrieved = store.get(game_id=1, user_id=1)
        assert retrieved is not None
        assert retrieved.game_id == 1
        assert retrieved.user_id == 1

    def test_session_not_found_returns_none(self):
        """Test that non-existent session returns None."""
        store = SessionStore()

        # 获取不存在的 session
        result = store.get(game_id=999, user_id=999)
        assert result is None

    def test_session_preserves_options_cache_on_update(self):
        """Test that options cache is preserved when session is updated."""
        store = SessionStore()

        # 创建初始 session
        mock_game_loop = MagicMock(spec=GameLoop)
        session = store.put(game_id=1, game_loop=mock_game_loop, user_id=1)

        # 设置缓存选项
        session.set_cached_options(week=1, round_num=0, options=[{"id": 1, "text": "Test"}])

        # 更新 session（模拟新的 game_loop）
        new_mock_game_loop = MagicMock(spec=GameLoop)
        updated_session = store.put(game_id=1, game_loop=new_mock_game_loop, user_id=1)

        # 验证缓存仍然可用
        cached = updated_session.get_cached_options(week=1, round_num=0)
        assert cached is not None
        assert len(cached) == 1
        assert cached[0]["text"] == "Test"

    def test_session_cleanup_removes_expired(self):
        """Test that expired sessions are cleaned up."""
        store = SessionStore()
        store._cleanup_interval = 0  # 立即清理

        # 创建 session
        mock_game_loop = MagicMock(spec=GameLoop)
        session = store.put(game_id=1, game_loop=mock_game_loop, user_id=1)

        # 手动设置过期
        session.last_access = time.time() - SESSION_TIMEOUT - 1

        # 获取应该触发清理并返回 None
        result = store.get(game_id=1, user_id=1)
        assert result is None

    def test_session_different_users_isolated(self):
        """Test that different users have isolated sessions."""
        store = SessionStore()

        # 为 user1 创建 session
        mock_game_loop_1 = MagicMock(spec=GameLoop)
        store.put(game_id=1, game_loop=mock_game_loop_1, user_id=1)

        # 为 user2 创建同名游戏
        mock_game_loop_2 = MagicMock(spec=GameLoop)
        store.put(game_id=1, game_loop=mock_game_loop_2, user_id=2)

        # 验证隔离
        session1 = store.get(game_id=1, user_id=1)
        session2 = store.get(game_id=1, user_id=2)

        assert session1 is not None
        assert session2 is not None
        assert session1.user_id == 1
        assert session2.user_id == 2

    def test_session_timeout_is_extended(self):
        """Test that session timeout is at least 4 hours."""
        # 验证超时时间 >= 4 小时 (14400 秒)
        assert (
            SESSION_TIMEOUT >= 4 * 60 * 60
        ), f"SESSION_TIMEOUT should be >= 4 hours, got {SESSION_TIMEOUT}"

    def test_session_not_expired_after_3_hours(self):
        """Test that session is still valid after 3 hours."""
        store = SessionStore()

        # 创建 session
        mock_game_loop = MagicMock(spec=GameLoop)
        session = store.put(game_id=1, game_loop=mock_game_loop, user_id=1)

        # 模拟 3 小时后访问（不是 4 小时）
        session.last_access = time.time() - 3 * 60 * 60

        # 应该仍然有效
        result = store.get(game_id=1, user_id=1)
        assert result is not None, "Session should not expire after 3 hours"
