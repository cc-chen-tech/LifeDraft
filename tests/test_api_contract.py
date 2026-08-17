"""API 契约测试 - 验证 API 请求/响应格式

轻量级测试，用于发现 API 变更、格式错误等问题。
"""

from fastapi.testclient import TestClient

from src.api.main import app
import pytest

pytestmark = [pytest.mark.api]


client = TestClient(app)


class TestEntityRecognitionAPIContract:
    """测试实体识别 API 契约"""

    def test_recognize_entities_unauthorized(self):
        """测试未授权访问返回 401"""
        response = client.post("/api/collection/1/recognize-entities", json={"min_appearances": 3})
        assert response.status_code == 401
        data = response.json()
        assert "detail" in data

    def test_add_entities_unauthorized(self):
        """测试未授权访问添加实体接口返回 401"""
        response = client.post(
            "/api/collection/1/add-entities", json={"items": [], "landmarks": []}
        )
        assert response.status_code == 401

    def test_get_collection_unauthorized(self):
        """测试未授权访问收集接口返回 401"""
        response = client.get("/api/collection/1")
        assert response.status_code == 401


class TestAPIErrorResponses:
    """测试 API 错误响应格式"""

    def test_error_response_has_detail(self):
        """测试错误响应包含 detail 字段"""
        response = client.post("/api/collection/1/recognize-entities", json={"min_appearances": 3})

        assert response.status_code == 401
        data = response.json()
        assert "detail" in data


class TestAsyncTaskLifecycle:
    """测试异步任务生命周期 API"""

    def test_task_endpoints_exist(self):
        """测试任务相关端点存在"""
        # 验证端点存在（返回 401 表示端点存在但未授权）
        recognize_response = client.post(
            "/api/collection/1/recognize-entities", json={"min_appearances": 3}
        )
        assert recognize_response.status_code in [401, 403, 400, 422, 200]

        add_response = client.post(
            "/api/collection/1/add-entities", json={"items": [], "landmarks": []}
        )
        assert add_response.status_code in [401, 403, 400, 200]


class TestGameplayProbeContract:
    """轻量 API 探测契约，避免端点存在性测试触发错误业务状态。"""

    def test_anonymous_choice_sync_without_current_event_returns_validation_status(self):
        create_response = client.post(
            "/api/games",
            json={
                "player_name": "ContractProbe",
                "life_vision": "保持接口契约稳定",
                "language": "zh",
                "constraint_level": "expert",
                "character_settings": {
                    "era": {"name": "现代", "year": 2026},
                    "gender": "unspecified",
                },
            },
        )
        assert create_response.status_code == 201
        game_id = create_response.json()["game_id"]

        response = client.post(f"/api/games/{game_id}/choice-sync", json={"option_index": 0})

        assert response.status_code == 422
        assert response.json()["detail"] == "No current event. Generate an event first."
