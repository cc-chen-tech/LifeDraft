"""Tests for choices router - 选择处理路由测试"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from src.api.routers.gameplay.choices import (_require_session,
                                              _restore_current_event_if_needed,
                                              router)


@pytest.fixture
def app():
    """Create test FastAPI app"""
    app = FastAPI()
    app.include_router(router, prefix="/games")
    return app


@pytest.fixture
def client(app):
    """Create test client"""
    return TestClient(app)


class TestRequireSession:
    """测试会话获取"""

    @patch("src.api.routers.gameplay.choices.session_service")
    def test_require_session_returns_session(self, mock_service):
        """测试获取会话"""
        mock_session = MagicMock()
        mock_service.get_or_restore.return_value = mock_session

        result = _require_session(1, None)

        assert result == mock_session
        mock_service.get_or_restore.assert_called_once_with(1, None)

    @patch("src.api.routers.gameplay.choices.session_service")
    def test_require_session_with_user_id(self, mock_service):
        """测试带用户ID获取会话"""
        mock_session = MagicMock()
        mock_service.get_or_restore.return_value = mock_session

        result = _require_session(1, 42)

        assert result == mock_session
        mock_service.get_or_restore.assert_called_once_with(1, 42)


class TestRestoreCurrentEventIfNeeded:
    """测试恢复当前事件"""

    def test_returns_true_if_event_exists(self):
        """测试事件已存在时返回True"""
        mock_game_loop = MagicMock()
        mock_game_loop.current_event = MagicMock()

        result = _restore_current_event_if_needed(mock_game_loop, 1, None)

        assert result is True

    @patch("src.api.routers.gameplay.choices.get_db")
    def test_raises_if_no_event_and_no_history(self, mock_get_db):
        """测试无事件且无历史时抛出异常"""
        mock_game_loop = MagicMock()
        mock_game_loop.current_event = None

        mock_db = MagicMock()
        mock_db.load_saved_game.return_value = None
        mock_get_db.return_value = mock_db

        with pytest.raises(HTTPException) as exc_info:
            _restore_current_event_if_needed(mock_game_loop, 1, None)

        assert exc_info.value.status_code == 400

    @patch("src.api.routers.gameplay.choices.get_db")
    def test_raises_choice_already_processed(self, mock_get_db):
        """测试选择已处理时抛出异常"""
        mock_game_loop = MagicMock()
        mock_game_loop.current_event = None

        mock_db = MagicMock()
        mock_db.load_saved_game.return_value = {"round_history": [{"round": 1}]}  # 有历史记录
        mock_get_db.return_value = mock_db

        with pytest.raises(HTTPException) as exc_info:
            _restore_current_event_if_needed(mock_game_loop, 1, None)

        assert exc_info.value.status_code == 400
        assert "choice_already_processed" in str(exc_info.value.detail)


class TestMakeChoiceEndpoint:
    """测试选择端点"""

    @patch("src.api.routers.gameplay.choices._require_session")
    def test_make_choice_game_over(self, mock_require, client):
        """测试游戏已结束时做选择"""
        mock_session = MagicMock()
        mock_game_loop = MagicMock()
        mock_game_loop.is_game_over.return_value = True
        mock_session.game_loop = mock_game_loop
        mock_require.return_value = mock_session

        response = client.post("/games/1/choice", json={"option_index": 0})

        assert response.status_code == 400

    @patch("src.api.routers.gameplay.choices._require_session")
    @patch("src.api.routers.gameplay.choices._restore_current_event_if_needed")
    def test_make_choice_no_current_event(self, mock_restore, mock_require, client):
        """测试无当前事件时做选择"""
        mock_session = MagicMock()
        mock_game_loop = MagicMock()
        mock_game_loop.is_game_over.return_value = False
        mock_session.game_loop = mock_game_loop
        mock_require.return_value = mock_session

        mock_restore.side_effect = HTTPException(status_code=400, detail="No current event")

        response = client.post("/games/1/choice", json={"option_index": 0})

        assert response.status_code == 400


class TestCustomChoiceEndpoint:
    """测试自定义选择端点"""

    def test_custom_choice_endpoint_exists(self):
        """测试自定义选择端点存在"""
        from src.api.routers.gameplay.choices import router

        routes = [route.path for route in router.routes]
        assert any("custom-choice" in path for path in routes)


class TestChoiceRouterStructure:
    """测试路由结构"""

    def test_router_exists(self):
        """测试路由器存在"""
        assert router is not None

    def test_router_has_routes(self):
        """测试路由器有路由"""
        routes = [route.path for route in router.routes]
        assert any("choice" in path for path in routes)

    def test_custom_choice_endpoint_exists(self):
        """测试自定义选择端点存在"""
        routes = [route.path for route in router.routes]
        assert any("custom-choice" in path for path in routes)
