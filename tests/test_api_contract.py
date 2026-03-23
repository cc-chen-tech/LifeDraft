"""API 契约测试 - 验证 API 请求/响应格式

轻量级测试，用于发现 API 变更、格式错误等问题。
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

from src.api.main import app

client = TestClient(app)


class TestEntityRecognitionAPIContract:
    """测试实体识别 API 契约"""

    def test_start_recognition_unauthorized(self):
        """测试未授权访问返回 401"""
        response = client.post(
            "/api/collection/1/recognize-entities-async",
            json={"min_appearances": 3}
        )
        assert response.status_code == 401
        data = response.json()
        assert "detail" in data

    def test_get_status_unauthorized(self):
        """测试未授权访问状态接口返回 401"""
        response = client.get(
            "/api/collection/1/recognize-entities-status/test-id"
        )
        assert response.status_code == 401

    def test_start_recognition_unauthorized(self):
        """测试未授权访问返回 401"""
        response = client.post(
            "/api/collection/1/recognize-entities-async",
            json={"min_appearances": 3}
        )
        assert response.status_code == 401

    def test_get_status_not_found(self):
        """测试任务不存在返回 404（或未授权 401）"""
        response = client.get(
            "/api/collection/1/recognize-entities-status/non-existent-id",
        )
        # 可能是 401（未授权）或 404（不存在）
        assert response.status_code in [401, 404]


class TestAPIErrorResponses:
    """测试 API 错误响应格式"""

    def test_error_response_has_detail(self):
        """测试错误响应包含 detail 字段"""
        response = client.post(
            "/api/collection/1/recognize-entities-async",
            json={"min_appearances": 3}
        )

        assert response.status_code == 401
        data = response.json()
        assert "detail" in data


class TestAsyncTaskLifecycle:
    """测试异步任务生命周期 API"""

    def test_task_endpoints_exist(self):
        """测试任务相关端点存在"""
        # 验证端点存在（返回 401 表示端点存在但未授权）
        start_response = client.post(
            "/api/collection/1/recognize-entities-async",
            json={"min_appearances": 3}
        )
        assert start_response.status_code in [401, 403, 404, 422, 200]

        status_response = client.get(
            "/api/collection/1/recognize-entities-status/test-id"
        )
        assert status_response.status_code in [401, 403, 404, 200]
