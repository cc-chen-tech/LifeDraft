"""真实 DB 集成测试 — 场景插画 SSE 推送事件

验证后台线程生成场景插画后，SSE 端点能正确推送事件到前端。

测试层: 真实 DB 集成测试 (Layer 4)
目标: 验证 后台生成→事件发布→SSE推送 链路完整
可防止: 图片生成完成但前端收不到通知，或事件格式错误
"""

import json

import pytest
from fastapi.testclient import TestClient

from src.api.main import app


@pytest.mark.integration
class TestSceneImageSSEIntegration:
    """DB 集成测试：场景插画 SSE 推送链路"""

    def test_publish_event_updates_latest_cache(self):
        """_publish_scene_image_event 应将事件写入 _scene_image_latest 缓存"""
        from src.api.routers.images import _publish_scene_image_event, _scene_image_latest

        game_id = 999990
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
        _publish_scene_image_event(event)

        key = f"{game_id}:0:1:result"
        try:
            assert key in _scene_image_latest
            cached = _scene_image_latest[key]
            assert cached["type"] == "scene_image_ready"
            assert cached["game_id"] == game_id
            assert cached["image_url"] == "/api/images/file/test.jpg"
        finally:
            _scene_image_latest.pop(key, None)

    def test_sse_endpoint_returns_cached_event(self):
        """SSE 端点应返回 _scene_image_latest 中的缓存事件"""
        from src.api.routers.images import _scene_image_latest

        game_id = 999989
        event = {
            "type": "scene_image_ready",
            "game_id": game_id,
            "round_number": 2,
            "week": 1,
            "stage": "event",
            "image_url": "/api/images/file/event.jpg",
            "scene_description": "事件场景",
            "timestamp": "2026-04-19T10:00:00",
        }
        _scene_image_latest[f"{game_id}:1:2:event"] = event

        try:
            with TestClient(app) as client:
                with client.get(f"/api/images/scene/events/{game_id}") as response:
                    assert response.status_code == 200
                    line = response.iter_lines().__next__()
                    data = json.loads(line[6:].decode())
                    assert data["type"] == "scene_image_ready"
                    assert data["game_id"] == game_id
                    assert data["round_number"] == 2
                    assert data["week"] == 1
                    assert data["stage"] == "event"
        finally:
            _scene_image_latest.pop(f"{game_id}:1:2:event", None)

    def test_failed_event_cached_and_fetchable(self):
        """失败事件也应被缓存并能通过 SSE 获取"""
        from src.api.routers.images import _publish_scene_image_event, _scene_image_latest

        game_id = 999988
        event = {
            "type": "scene_image_failed",
            "game_id": game_id,
            "round_number": 0,
            "week": 0,
            "stage": "result",
            "error": "Image generation timeout after 180s",
            "timestamp": "2026-04-19T10:00:00",
        }
        _publish_scene_image_event(event)

        key = f"{game_id}:0:0:result"
        try:
            assert key in _scene_image_latest
            assert _scene_image_latest[key]["error"] == "Image generation timeout after 180s"

            with TestClient(app) as client:
                with client.get(f"/api/images/scene/events/{game_id}") as response:
                    line = response.iter_lines().__next__()
                    data = json.loads(line[6:].decode())
                    assert data["type"] == "scene_image_failed"
                    assert "error" in data
        finally:
            _scene_image_latest.pop(key, None)

    def test_publish_from_thread_reaches_sse(self):
        """模拟后台线程发布事件，验证 SSE 端点能获取到"""
        from src.api.routers.images import _publish_scene_image_event, _scene_image_latest

        game_id = 999987
        # 模拟后台线程发布成功事件（与 _trigger_scene_generation_in_background 中调用一致）
        _publish_scene_image_event({
            "type": "scene_image_ready",
            "game_id": game_id,
            "round_number": 0,
            "week": 0,
            "stage": "result",
            "image_url": "/api/images/file/generated.jpg",
            "scene_description": "后台生成的场景",
            "timestamp": "2026-04-19T10:00:00",
        })

        key = f"{game_id}:0:0:result"
        try:
            assert key in _scene_image_latest

            with TestClient(app) as client:
                with client.get(f"/api/images/scene/events/{game_id}") as response:
                    line = response.iter_lines().__next__()
                    data = json.loads(line[6:].decode())
                    assert data["type"] == "scene_image_ready"
                    assert data["image_url"] == "/api/images/file/generated.jpg"
        finally:
            _scene_image_latest.pop(key, None)

    def test_event_key_format_consistency(self):
        """事件缓存键应使用统一格式 {game_id}:{week}:{round_number}:{stage}"""
        from src.api.routers.images import _get_event_key, _publish_scene_image_event, _scene_image_latest

        game_id = 999987
        event = {
            "type": "scene_image_ready",
            "game_id": game_id,
            "round_number": 3,
            "week": 2,
            "stage": "result",
            "image_url": "/test.jpg",
            "scene_description": "测试",
            "timestamp": "2026-04-19T10:00:00",
        }
        _publish_scene_image_event(event)

        expected_key = _get_event_key(game_id, 2, 3, "result")
        try:
            assert expected_key in _scene_image_latest
            assert expected_key == f"{game_id}:2:3:result"
        finally:
            _scene_image_latest.pop(expected_key, None)
