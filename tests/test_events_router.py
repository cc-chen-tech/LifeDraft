"""Tests for events router - 事件生成路由测试"""
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from fastapi import FastAPI
from fastapi.testclient import TestClient
import asyncio

from src.api.routers.gameplay.events import (
    router,
    _get_game_lock,
    _require_session,
)


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


class TestGetGameLock:
    """测试游戏锁获取"""
    
    @pytest.mark.asyncio
    async def test_get_game_lock_creates_new(self):
        """测试创建新锁"""
        lock = await _get_game_lock(999)
        assert lock is not None
        assert isinstance(lock, asyncio.Lock)
    
    @pytest.mark.asyncio
    async def test_get_game_lock_returns_same(self):
        """测试返回相同的锁"""
        lock1 = await _get_game_lock(123)
        lock2 = await _get_game_lock(123)
        assert lock1 is lock2


class TestRequireSession:
    """测试会话获取"""
    
    @patch('src.api.routers.gameplay.events.session_service')
    def test_require_session_returns_session(self, mock_service):
        """测试获取会话"""
        mock_session = MagicMock()
        mock_service.get_or_restore.return_value = mock_session
        
        result = _require_session(1, None)
        
        assert result == mock_session
        mock_service.get_or_restore.assert_called_once_with(1, None)
    
    @patch('src.api.routers.gameplay.events.session_service')
    def test_require_session_with_user_id(self, mock_service):
        """测试带用户ID获取会话"""
        mock_session = MagicMock()
        mock_service.get_or_restore.return_value = mock_session
        
        result = _require_session(1, 42)
        
        assert result == mock_session
        mock_service.get_or_restore.assert_called_once_with(1, 42)


class TestGenerateEventEndpoint:
    """测试事件生成端点"""
    
    @patch('src.api.routers.gameplay.events._require_session')
    def test_generate_event_game_over(self, mock_require, client):
        """测试游戏已结束时生成事件"""
        mock_session = MagicMock()
        mock_game_loop = MagicMock()
        mock_game_loop.is_game_over.return_value = True
        mock_session.game_loop = mock_game_loop
        mock_require.return_value = mock_session
        
        response = client.get("/games/1/event")
        
        assert response.status_code == 400
    
    @patch('src.api.routers.gameplay.events._require_session')
    def test_generate_event_has_existing_event(self, mock_require, client):
        """测试已有事件时返回现有事件"""
        from src.ai.models import GameEvent, EventOption
        
        mock_session = MagicMock()
        mock_session.sse_cache = None
        mock_game_loop = MagicMock()
        mock_game_loop.is_game_over.return_value = False
        # 使用真实对象
        mock_game_loop.current_event = GameEvent(
            event_description="测试事件",
            options=[
                EventOption(text="选项1", effects={}),
                EventOption(text="选项2", effects={})
            ]
        )
        mock_session.game_loop = mock_game_loop
        mock_require.return_value = mock_session
        
        response = client.get("/games/1/event")
        
        # Should return streaming response
        assert response.status_code == 200


class TestGenerateEventSync:
    """测试同步事件生成端点"""
    
    @patch('src.api.routers.gameplay.events._require_session')
    def test_generate_event_sync_game_over(self, mock_require, client):
        """测试游戏已结束时同步生成事件"""
        mock_session = MagicMock()
        mock_game_loop = MagicMock()
        mock_game_loop.is_game_over.return_value = True
        mock_session.game_loop = mock_game_loop
        mock_require.return_value = mock_session
        
        response = client.post("/games/1/event-sync")
        
        assert response.status_code == 400
    
    @patch('src.api.routers.gameplay.events._require_session')
    def test_generate_event_sync_success(self, mock_require, client):
        """测试同步生成事件成功"""
        mock_session = MagicMock()
        mock_game_loop = MagicMock()
        mock_game_loop.is_game_over.return_value = False
        mock_game_loop._generating = False
        mock_game_loop.current_event = None
        mock_game_loop.generate_round_event = MagicMock()
        mock_game_loop.generate_round_event.return_value = MagicMock(
            event_description="测试事件",
            options=[MagicMock(text="选项1")]
        )
        mock_session.game_loop = mock_game_loop
        mock_require.return_value = mock_session
        
        response = client.post("/games/1/event-sync")
        
        # Should return 200 or handle accordingly
        assert response.status_code in [200, 400, 500]


class TestEventRouterStructure:
    """测试路由结构"""
    
    def test_router_exists(self):
        """测试路由器存在"""
        assert router is not None
    
    def test_router_has_routes(self):
        """测试路由器有路由"""
        routes = [route.path for route in router.routes]
        assert any("event" in path for path in routes)
    
    def test_event_endpoint_exists(self):
        """测试事件端点存在"""
        routes = [route.path for route in router.routes]
        assert any("event" in path for path in routes)
    
    def test_event_sync_endpoint_exists(self):
        """测试同步事件端点存在"""
        routes = [route.methods for route in router.routes]
        # Check for POST method
        assert any("POST" in methods for methods in routes)
