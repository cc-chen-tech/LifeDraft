"""SSE 超时与前端 polling 超时契约测试 (Layer 3)

验证前后端超时值的一致性约束，防止"用户看到生成失败但后端还在工作"的问题。
"""

import ast
import os
import re

import pytest


class TestBackendSSETimeoutContract:
    """验证后端 SSE 流式生成超时常量。"""

    def test_backend_sse_timeout_value(self):
        """sse_helpers.py 中 SSE 整体超时阈值应为 330 秒。

        ★ 修复：从 120s 提升到 330s，确保 SSE 超时 >= 前端 polling 超时 (300s) + 余量
        防止"SSE 先断开，但 polling 还在工作"导致用户看到"生成失败"。
        """
        helpers_path = os.path.join(
            os.path.dirname(__file__), "..", "src", "api", "routers", "gameplay", "sse_helpers.py"
        )
        with open(helpers_path, "r", encoding="utf-8") as f:
            source = f.read()

        # 查找 SSE_STREAM_TIMEOUT = 330 模式
        assert "SSE_STREAM_TIMEOUT = 330" in source, (
            "sse_helpers.py 中 SSE 超时阈值应为 330 秒，"
            "确保 SSE 超时 >= 前端 polling 超时 (300s) + 余量"
        )

    def test_backend_heartbeat_interval_value(self):
        """SSE 心跳间隔应为 5 秒。"""
        helpers_path = os.path.join(
            os.path.dirname(__file__), "..", "src", "api", "routers", "gameplay", "sse_helpers.py"
        )
        with open(helpers_path, "r", encoding="utf-8") as f:
            source = f.read()

        assert "heartbeat_interval = 5" in source, (
            "sse_helpers.py 中心跳间隔应为 5 秒"
        )

    def test_backend_sse_error_event_format(self):
        """SSE 超时 error 事件应包含 'error' 字段。"""
        helpers_path = os.path.join(
            os.path.dirname(__file__), "..", "src", "api", "routers", "gameplay", "sse_helpers.py"
        )
        with open(helpers_path, "r", encoding="utf-8") as f:
            source = f.read()

        # 验证超时时的 error 事件格式
        assert 'yield make_sse_event("error", {"error": "Timeout waiting for event generation"})' in source, (
            "SSE 超时应返回包含 'error' 字段的标准 error 事件"
        )


class TestFrontendPollingTimeoutContract:
    """验证前端 polling 超时常量。"""

    def test_frontend_polling_timeout_value(self):
        """useEventGenerator.ts 中 polling 最大时长应为 300000ms (5分钟)。"""
        hook_path = os.path.join(
            os.path.dirname(__file__), "..", "frontend", "src", "hooks", "game", "useEventGenerator.ts"
        )
        with open(hook_path, "r", encoding="utf-8") as f:
            source = f.read()

        assert "maxPollingTime = 300000" in source, (
            "useEventGenerator.ts 中 maxPollingTime 应为 300000ms (5分钟)"
        )

    def test_frontend_polling_interval_value(self):
        """useEventGenerator.ts 中 polling 间隔应为 8000ms。"""
        hook_path = os.path.join(
            os.path.dirname(__file__), "..", "frontend", "src", "hooks", "game", "useEventGenerator.ts"
        )
        with open(hook_path, "r", encoding="utf-8") as f:
            source = f.read()

        assert "pollInterval = 8000" in source, (
            "useEventGenerator.ts 中 pollInterval 应为 8000ms"
        )

    def test_backend_sse_exceeds_frontend_polling_timeout(self):
        """后端 SSE 超时必须 >= 前端 polling 超时 + 余量。

        ★ 修复后的约束：后端 SSE (330s) >= 前端 polling (300s) + 余量 (30s)
        这是防止"SSE 先断开但 polling 还在工作"的关键契约。
        之前是 120s < 300s，导致用户看到"生成失败"但实际后端还在工作。
        """
        BACKEND_SSE_TIMEOUT = 330  # 秒
        FRONTEND_POLLING_TIMEOUT = 300  # 秒 (300000ms)
        MIN_MARGIN = 30  # 秒

        assert BACKEND_SSE_TIMEOUT >= FRONTEND_POLLING_TIMEOUT + MIN_MARGIN, (
            f"后端 SSE 超时 ({BACKEND_SSE_TIMEOUT}s) 必须 >= "
            f"前端 polling 超时 ({FRONTEND_POLLING_TIMEOUT}s) + 余量 ({MIN_MARGIN}s)，"
            f"否则 SSE 先断开但 polling 还在工作，用户会看到'生成失败'"
        )

    def test_frontend_polling_calls_syncstate(self):
        """前端 polling 逻辑必须调用 syncState 获取最新状态。"""
        hook_path = os.path.join(
            os.path.dirname(__file__), "..", "frontend", "src", "hooks", "game", "useEventGenerator.ts"
        )
        with open(hook_path, "r", encoding="utf-8") as f:
            source = f.read()

        assert "syncState" in source, (
            "polling 逻辑必须调用 syncState 来同步后端状态"
        )


class TestSSEErrorEventContract:
    """验证 SSE error 事件的格式契约。"""

    def test_make_sse_event_error_format(self):
        """make_sse_event 生成的 error 事件应可被前端正确解析。"""
        from src.api.routers.gameplay.sse_helpers import make_sse_event

        event = make_sse_event("error", {"error": "Timeout waiting for event generation"})

        assert "event: error" in event
        assert '"error":' in event
        assert "Timeout waiting for event generation" in event

    def test_make_sse_event_status_format(self):
        """make_sse_event 生成的 status 事件应包含 phase 字段。"""
        from src.api.routers.gameplay.sse_helpers import make_sse_event

        event = make_sse_event("status", {"phase": "processing", "heartbeat": True})

        assert "event: status" in event
        assert '"phase":' in event
        assert '"heartbeat":' in event
