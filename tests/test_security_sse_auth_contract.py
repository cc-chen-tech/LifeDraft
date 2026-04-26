"""SSE Endpoint Authentication Contract Tests

验证 SSE 端点需要认证才能访问。
Layer 3: 契约测试 — 敏感数据的 SSE 流必须要求认证。
"""

import os
from fastapi.testclient import TestClient

os.environ.setdefault("JWT_SECRET", "test-secret-for-sse-auth-contract")

from src.api.main import app  # noqa: E402

client = TestClient(app)


class TestSSEAuthenticationContract:
    """测试 SSE 端点认证契约"""

    def test_scene_events_sse_requires_authentication(self):
        """未认证的请求访问 /scene/events/{game_id} 应返回 401"""
        response = client.get("/api/images/scene/events/1")
        assert response.status_code == 401, (
            f"SSE 端点应要求认证，但返回了 {response.status_code}"
        )

    def test_scene_events_sse_rejects_invalid_token(self):
        """无效的 token 访问 SSE 端点应返回 401"""
        response = client.get(
            "/api/images/scene/events/1",
            headers={"Authorization": "Bearer invalid-token"},
        )
        assert response.status_code == 401, (
            f"无效 token 应返回 401，但返回了 {response.status_code}"
        )
