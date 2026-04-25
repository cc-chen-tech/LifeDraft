"""事件生成并发控制契约测试 (Layer 3)

验证并发控制相关的接口契约：锁行为、标志位、超时清理等。
"""

import asyncio
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from src.api.routers.gameplay.events import _get_game_lock


class TestGameLockContract:
    """验证 per-game asyncio.Lock 契约。"""

    @pytest.mark.asyncio
    async def test_get_game_lock_creates_new(self):
        """_get_game_lock 应创建新的 asyncio.Lock。"""
        lock = await _get_game_lock(9999)
        assert lock is not None
        assert isinstance(lock, asyncio.Lock)

    @pytest.mark.asyncio
    async def test_get_game_lock_returns_same_instance(self):
        """相同 game_id 应返回同一 lock 实例。"""
        lock1 = await _get_game_lock(8888)
        lock2 = await _get_game_lock(8888)
        assert lock1 is lock2, "相同 game_id 必须返回同一 lock 实例，否则并发控制失效"

    @pytest.mark.asyncio
    async def test_get_game_lock_different_games(self):
        """不同 game_id 应返回不同 lock 实例。"""
        lock1 = await _get_game_lock(7777)
        lock2 = await _get_game_lock(7776)
        assert lock1 is not lock2, "不同 game_id 应使用不同 lock，避免不必要的串行化"

    @pytest.mark.asyncio
    async def test_lock_can_be_acquired_and_released(self):
        """lock 应可正常获取和释放。"""
        lock = await _get_game_lock(6666)
        assert not lock.locked()

        await lock.acquire()
        assert lock.locked()

        lock.release()
        assert not lock.locked()


class TestGameLoopGeneratingFlagContract:
    """验证 game_loop._generating 标志位契约。"""

    def test_game_loop_has_generating_flag(self):
        """game_loop 实例应有 _generating 属性。"""
        from src.game.game_loop import GameLoop

        loop = GameLoop(language="zh")
        assert hasattr(loop, "_generating"), (
            "GameLoop 必须有 _generating 标志位用于并发控制"
        )

    def test_game_loop_has_generating_start_time(self):
        """game_loop 实例应有 _generating_start_time 属性。"""
        from src.game.game_loop import GameLoop

        loop = GameLoop(language="zh")
        assert hasattr(loop, "_generating_start_time"), (
            "GameLoop 必须有 _generating_start_time 用于超时检测"
        )

    def test_generating_flag_defaults_to_false(self):
        """_generating 初始值应为 False。"""
        from src.game.game_loop import GameLoop

        loop = GameLoop(language="zh")
        assert loop._generating is False, (
            "_generating 初始值必须为 False，否则新游戏无法开始生成"
        )


class TestConcurrentRequestHandlingContract:
    """验证并发请求处理契约。"""

    @pytest.fixture
    def _event_client(self):
        """Create a test client with events router mounted at /games."""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from src.api.routers.gameplay.events import router

        app = FastAPI()
        app.include_router(router, prefix="/games")
        return TestClient(app)

    def test_concurrent_request_returns_sse_error(self, _event_client: TestClient):
        """当 generation 正在进行时，第二个请求应返回 SSE error 事件而非 HTTP 409。

        这是关键契约：SSE 端点必须始终返回 SSE 流，即使出错。
        """
        import time

        with patch("src.api.routers.gameplay.events._require_session") as mock_require:
            mock_session = MagicMock()
            mock_game_loop = MagicMock()
            mock_game_loop.is_game_over.return_value = False
            mock_game_loop.current_event = None
            # 模拟 generation 正在进行（刚启动 5 秒，不会触发超时）
            mock_game_loop._generating = True
            mock_game_loop._generating_start_time = time.time() - 5
            mock_session.game_loop = mock_game_loop
            mock_session.sse_cache = []
            mock_require.return_value = mock_session

            response = _event_client.get("/games/1/event")

            # 必须返回 200 StreamingResponse，而不是 409
            assert response.status_code == 200, (
                "SSE 端点在并发情况下必须返回 200 + SSE error 事件，"
                "不能返回 HTTP 409（会破坏前端 SSE 解析逻辑）"
            )
            content = response.content.decode("utf-8")
            assert "event: error" in content, (
                "并发请求的响应中必须包含 'event: error'"
            )

    def test_generating_flag_timeout_reset(self, _event_client: TestClient):
        """_generating 标志超过 60 秒应被强制重置。"""
        import time
        from src.ai.models import GameEvent, EventOption

        with patch("src.api.routers.gameplay.events._require_session") as mock_require:
            mock_session = MagicMock()
            mock_game_loop = MagicMock()
            mock_game_loop.is_game_over.return_value = False
            mock_game_loop.current_event = None
            # 模拟 generation 已卡住 70 秒
            mock_game_loop._generating = True
            mock_game_loop._generating_start_time = time.time() - 70
            mock_session.game_loop = mock_game_loop
            mock_session.sse_cache = []
            mock_require.return_value = mock_session

            # 使用真实的 GameEvent 作为 generate_round_event 的返回值
            # 避免 MagicMock 的 model_dump() 产生不可 JSON 序列化的数据
            real_event = GameEvent(
                event_description="Test story for timeout reset",
                options=[
                    EventOption(text="Option 1", effects={"energy": -5}, likely_choice=False),
                    EventOption(text="Option 2", effects={"energy": -3}, likely_choice=True),
                ],
            )
            mock_game_loop.generate_round_event.return_value = real_event

            response = _event_client.get("/games/1/event")

            # 70s > 60s 阈值，_generating 应被重置，请求应继续（返回 200）
            assert response.status_code == 200
            # 验证 _generating 被重置
            assert mock_game_loop._generating is False, (
                "_generating 超过 60s 必须被强制重置，否则卡死状态无法恢复"
            )


class TestLockReleaseContract:
    """验证锁释放契约。"""

    @pytest.mark.asyncio
    async def test_lock_release_after_streaming(self):
        """StreamingResponse 结束后 lock 必须被释放。

        这是防止死锁的关键契约。
        """
        lock = await _get_game_lock(5555)
        assert not lock.locked()

        await lock.acquire()
        assert lock.locked()

        # 模拟 streaming 结束后的 finally 释放
        lock.release()
        assert not lock.locked(), (
            "lock 必须在 streaming 结束后释放，否则后续请求会永远阻塞"
        )


class TestSSEErrorFormatContract:
    """验证 SSE error 格式契约。"""

    def test_return_sse_error_format(self):
        """return_sse_error 应生成标准 SSE error 事件。"""
        from src.api.routers.gameplay.sse_helpers import return_sse_error

        # 由于 return_sse_error 是 async generator，需要迭代获取
        async def _collect():
            chunks = []
            async for chunk in return_sse_error("Event generation in progress, please wait"):
                chunks.append(chunk)
            return chunks

        chunks = asyncio.run(_collect())
        assert len(chunks) == 1
        assert "event: error" in chunks[0]
        assert "Event generation in progress, please wait" in chunks[0]
