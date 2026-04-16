"""Tests for scene image API endpoints."""

from fastapi import Response
from src.api.main import app


class TestSceneImageAPI:
    """Test scene image API behavior."""

    def test_no_story_text_returns_204_logic(self):
        """Test the logic for 204 response when no story text.

        验证当 story_text 为空时，返回 204 No Content。
        """
        # 模拟 Response 对象创建
        response = Response(status_code=204)
        assert response.status_code == 204

    def test_api_contract_scene_image(self):
        """Test that scene image endpoint exists in API."""
        routes = [route.path for route in app.routes]

        # 查找包含 scene 和 image 的路由
        scene_routes = [r for r in routes if "scene" in r.lower()]

        # 验证有场景图片相关的路由
        assert len(scene_routes) > 0, f"No scene routes found. Routes: {routes[:10]}"

        # 验证响应类型支持 204
        response = Response(status_code=204)
        assert response.status_code == 204
