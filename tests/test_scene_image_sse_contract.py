"""契约测试 — 场景插画 SSE 推送事件格式

验证 /api/images/scene/events/{game_id} SSE 端点返回的事件格式正确，
前端能正确解析场景图片生成完成/失败通知。

测试层: 契约测试 (Layer 3)
目标: 验证 SSE 事件字段名和格式与前端期望一致
可防止: 前端无法解析 SSE 事件导致图片不刷新
"""

import json
import os
from datetime import datetime, timedelta

from fastapi.testclient import TestClient
from jose import jwt

os.environ.setdefault("JWT_SECRET", "test-secret-for-sse-contract")

from src.api.main import app  # noqa: E402

client = TestClient(app)


def _auth_headers(user_id: int = 1) -> dict:
    """生成有效的认证请求头"""
    token = jwt.encode(
        {"sub": str(user_id), "exp": datetime.utcnow() + timedelta(hours=1)},
        os.environ["JWT_SECRET"],
        algorithm="HS256",
    )
    return {"Authorization": f"Bearer {token}"}


class TestSceneImageSSEContract:
    """契约测试：场景插画 SSE 事件格式"""

    def test_sse_event_format_ready(self):
        """场景图片生成完成时，SSE 事件应包含所有必要字段"""
        # 预置一个生成完成事件到缓存
        from src.api.routers.images import _scene_image_latest

        game_id = 999999  # 使用不存在的 game_id 避免冲突
        event = {
            "type": "scene_image_ready",
            "game_id": game_id,
            "round_number": 1,
            "week": 0,
            "stage": "result",
            "image_url": "/api/images/file/test.jpg",
            "scene_description": "测试场景",
            "timestamp": "2026-04-19T10:00:00",
        }
        _scene_image_latest[f"{game_id}:0:1:result"] = event

        try:
            with client.get(f"/api/images/scene/events/{game_id}", headers=_auth_headers()) as response:
                assert response.status_code == 200
                # 读取第一行（应该是缓存事件）
                line = response.iter_lines().__next__()
                assert line.startswith(b"data: ")
                data = json.loads(line[6:].decode())

                assert data["type"] == "scene_image_ready"
                assert "game_id" in data
                assert "round_number" in data
                assert "week" in data
                assert "stage" in data
                assert "image_url" in data
                assert "scene_description" in data
                assert "timestamp" in data
        finally:
            _scene_image_latest.pop(f"{game_id}:0:1:result", None)

    def test_sse_event_format_failed(self):
        """场景图片生成失败时，SSE 事件应包含错误信息"""
        from src.api.routers.images import _scene_image_latest

        game_id = 999998
        event = {
            "type": "scene_image_failed",
            "game_id": game_id,
            "round_number": 2,
            "week": 1,
            "stage": "event",
            "error": "Image generation timeout",
            "timestamp": "2026-04-19T10:00:00",
        }
        _scene_image_latest[f"{game_id}:1:2:event"] = event

        try:
            with client.get(f"/api/images/scene/events/{game_id}", headers=_auth_headers()) as response:
                line = response.iter_lines().__next__()
                data = json.loads(line[6:].decode())

                assert data["type"] == "scene_image_failed"
                assert "error" in data
                assert "round_number" in data
        finally:
            _scene_image_latest.pop(f"{game_id}:1:2:event", None)

    def test_sse_event_type_values(self):
        """SSE 事件 type 字段只能是预定义值"""
        from src.api.routers.images import _scene_image_latest

        game_id = 999997
        # 只测试 type 字段的约束
        valid_types = ["scene_image_ready", "scene_image_failed", "heartbeat"]

        for event_type in valid_types:
            event = {
                "type": event_type,
                "game_id": game_id,
                "round_number": 0,
                "week": 0,
                "stage": "result",
                "timestamp": "2026-04-19T10:00:00",
            }
            _scene_image_latest[f"{game_id}:0:0:result:{event_type}"] = event

        try:
            with client.get(f"/api/images/scene/events/{game_id}", headers=_auth_headers()) as response:
                line = response.iter_lines().__next__()
                data = json.loads(line[6:].decode())
                assert data["type"] in valid_types
        finally:
            for event_type in valid_types:
                _scene_image_latest.pop(f"{game_id}:0:0:result:{event_type}", None)

    def test_sse_requires_auth(self):
        """SSE 端点应需要认证"""
        # 未认证访问应返回 401
        response = client.get("/api/images/scene/events/1")
        assert response.status_code == 401, (
            f"未认证访问 SSE 端点应返回 401，但返回了 {response.status_code}"
        )
