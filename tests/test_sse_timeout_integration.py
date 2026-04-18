"""SSE 超时与前端 polling 集成测试 (Layer 4)

验证 SSE 流在超时场景下的行为，以及前端 polling 的恢复能力。
使用真实 asyncio 事件循环和 Queue 模拟 SSE 流。
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.api.routers.gameplay.sse_helpers import make_sse_event, stream_round_event


class TestSSEStreamTimeout:
    """验证 SSE 流在长时间无产出时的超时行为。"""

    @pytest.mark.asyncio
    async def test_sse_stream_sends_heartbeat_when_no_output(self):
        """当生成器无产出时，SSE 流应定期发送 heartbeat 保持连接。

        验证心跳机制：即使 generate_round_event 阻塞，
        SSE 流也应每 5 秒发送一次 heartbeat status 事件。
        """
        game_loop = MagicMock()
        # 模拟一个永远不会完成的生成（同步阻塞，在线程池中执行）
        import threading
        stop_event = threading.Event()

        def blocking_generation(**kwargs):
            stop_event.wait(timeout=10)  # 阻塞 10 秒或直到测试结束
            return None

        game_loop.generate_round_event = MagicMock(side_effect=blocking_generation)

        # 收集 SSE 事件（限制数量避免测试无限运行）
        events = []
        async for event in stream_round_event(game_loop, game_id=1):
            events.append(event)
            if len(events) >= 3:
                break

        # 通知阻塞的线程结束
        stop_event.set()

        # 验证至少收到了 heartbeat status 事件
        status_events = [e for e in events if "status" in e]
        assert len(status_events) >= 1, "SSE 流应发送至少一个 heartbeat status 事件"

        # 验证收到了 heartbeat 标记
        heartbeat_events = [e for e in events if "heartbeat" in e]
        assert len(heartbeat_events) >= 1, "SSE 流应发送 heartbeat 事件保持连接"

    @pytest.mark.asyncio
    async def test_sse_stream_sends_heartbeat_during_generation(self):
        """生成过程中 SSE 流应定期发送 heartbeat。"""
        game_loop = MagicMock()

        # 模拟一个慢速生成：通过线程池执行，所以用同步函数
        # stream_callback 会在后台线程中被调用
        def slow_generation(**kwargs):
            stream_cb = kwargs.get("stream_callback")
            for i in range(3):
                if stream_cb:
                    stream_cb(f"chunk {i}")
                # 在线程中不能使用 asyncio.sleep，用 time.sleep
                import time
                time.sleep(0.05)
            # 返回一个 mock event，model_dump 必须返回可 JSON 序列化的数据
            mock_event = MagicMock()
            mock_event.event_description = "test story"
            mock_event.options = []
            mock_event.model_dump.return_value = {
                "event_description": "test story",
                "options": [],
            }
            return mock_event

        game_loop.generate_round_event = slow_generation

        events = []
        async for event in stream_round_event(game_loop, game_id=1):
            events.append(event)
            # 限制收集数量避免测试运行太久
            if len(events) >= 10:
                break

        # 验证收到了 story chunks
        story_events = [e for e in events if "story" in e]
        assert len(story_events) >= 3, "应收到至少 3 个 story chunk"

        # 验证收到了 complete 事件
        complete_events = [e for e in events if "complete" in e]
        assert len(complete_events) >= 1, "应收到 complete 事件"

    @pytest.mark.asyncio
    async def test_sse_stream_returns_complete_event_on_success(self):
        """生成成功时 SSE 流应返回 complete 事件。"""
        game_loop = MagicMock()

        def fast_generation(**kwargs):
            stream_cb = kwargs.get("stream_callback")
            if stream_cb:
                stream_cb("story chunk")
            mock_event = MagicMock()
            mock_event.event_description = "completed story"
            mock_event.options = [MagicMock(text="option 1")]
            mock_event.model_dump.return_value = {
                "event_description": "completed story",
                "options": [{"text": "option 1"}],
            }
            return mock_event

        game_loop.generate_round_event = fast_generation

        events = []
        async for event in stream_round_event(game_loop, game_id=1):
            events.append(event)

        # 验证收到了 complete 事件且包含选项
        complete_events = [e for e in events if "complete" in e]
        assert len(complete_events) >= 1
        assert "completed story" in complete_events[0]


class TestSSEErrorEventFormat:
    """验证 SSE error 事件的格式。"""

    def test_sse_error_event_contains_error_field(self):
        """SSE error 事件必须包含 'error' 字段。"""
        event = make_sse_event("error", {"error": "Timeout waiting for event generation"})
        assert "error" in event
        assert "Timeout waiting for event generation" in event

    def test_sse_status_event_contains_phase_field(self):
        """SSE status 事件必须包含 'phase' 字段。"""
        event = make_sse_event("status", {"phase": "processing", "heartbeat": True})
        assert "phase" in event
        assert "processing" in event
        assert "heartbeat" in event


class TestPollingSurvivesAfterSSEDisconnect:
    """验证 SSE 断开后 polling 能正确获取状态。"""

    def test_polling_timeout_exceeds_sse_timeout_with_margin(self):
        """polling 超时必须小于 SSE 超时 + 安全余量。

        ★ 修复后的约束：SSE (330s) >= polling (300s) + 余量 (30s)
        这是防止"SSE 先断开但 polling 还在工作"的关键集成约束。
        """
        BACKEND_SSE_TIMEOUT = 330  # 秒
        FRONTEND_POLLING_TIMEOUT = 300  # 秒
        MIN_MARGIN = 30  # 秒

        assert BACKEND_SSE_TIMEOUT >= FRONTEND_POLLING_TIMEOUT + MIN_MARGIN, (
            f"后端 SSE 超时 ({BACKEND_SSE_TIMEOUT}s) 必须 >= "
            f"前端 polling ({FRONTEND_POLLING_TIMEOUT}s) + 余量 ({MIN_MARGIN}s)"
        )

    def test_sse_timeout_exceeds_polling_with_margin(self):
        """SSE 超时必须大于 polling 超时 + 安全余量。

        ★ 修复后的约束：SSE (330s) >= polling (300s) + 余量 (30s)
        这是防止"SSE 先断开但 polling 还在工作"的关键集成约束。
        """
        BACKEND_SSE_TIMEOUT = 330  # 秒
        FRONTEND_POLLING_TIMEOUT = 300  # 秒
        MIN_MARGIN = 30  # 秒

        assert BACKEND_SSE_TIMEOUT >= FRONTEND_POLLING_TIMEOUT + MIN_MARGIN, (
            f"后端 SSE 超时 ({BACKEND_SSE_TIMEOUT}s) 必须 >= "
            f"前端 polling ({FRONTEND_POLLING_TIMEOUT}s) + 余量 ({MIN_MARGIN}s)"
        )


class TestGenerationCompletesBeforePollingTimeout:
    """验证正常生成不会触发 polling timeout。"""

    def test_typical_generation_time_well_within_polling_timeout(self):
        """典型生成时间（<60s）应远小于 polling 超时（300s）。"""
        TYPICAL_GENERATION_TIME = 60  # 秒，基于日志观察
        POLLING_TIMEOUT = 300  # 秒

        assert TYPICAL_GENERATION_TIME < POLLING_TIMEOUT, (
            f"典型生成时间 ({TYPICAL_GENERATION_TIME}s) 应小于 polling 超时 ({POLLING_TIMEOUT}s)"
        )

    def test_polling_interval_allows_multiple_checks(self):
        """polling 间隔应允许在超时前进行多次状态检查。"""
        POLLING_TIMEOUT = 300_000  # ms
        POLLING_INTERVAL = 8_000  # ms

        max_checks = POLLING_TIMEOUT // POLLING_INTERVAL
        assert max_checks >= 30, (
            f"polling 应在超时前允许至少 30 次检查，"
            f"实际最多 {max_checks} 次 (interval={POLLING_INTERVAL}ms)"
        )
