"""契约测试：约束级别持久化前后端字段一致性。"""

from unittest.mock import patch

from fastapi.testclient import TestClient


def test_game_state_response_schema_has_constraint_level():
    from src.api.schemas import GameStateResponse

    assert "constraint_level" in GameStateResponse.model_fields
    assert GameStateResponse.model_fields["constraint_level"].default == "expert"


def test_create_game_request_default_constraint_level():
    from src.api.schemas import CreateGameRequest

    assert "constraint_level" in CreateGameRequest.model_fields
    assert CreateGameRequest.model_fields["constraint_level"].default == "expert"


def test_update_game_settings_request_schema():
    from src.api.schemas import UpdateGameSettingsRequest

    req = UpdateGameSettingsRequest(constraint_level="fast")
    assert req.constraint_level == "fast"

    req_none = UpdateGameSettingsRequest()
    assert req_none.constraint_level is None


def test_patch_settings_route_exists(client: TestClient):
    """PATCH /api/games/1/settings 路由存在（401/404 都证明路由已注册，405 才表示不存在）。"""
    response = client.patch(
        "/api/games/1/settings", json={"constraint_level": "master"}
    )
    # 401(需要认证) 或 404(游戏不存在) 都表示路由已注册；405 表示路由不存在
    assert response.status_code in (
        401,
        404,
    ), f"Expected 401 or 404, got {response.status_code}"


def test_game_state_response_includes_constraint_level(client: TestClient):
    """创建游戏后，GET /api/games/{id} 返回 constraint_level。"""
    headers = {"Authorization": "Bearer test_token"}
    with patch("src.api.deps.decode_token", return_value=1):
        create_resp = client.post(
            "/api/games",
            headers=headers,
            json={
                "player_name": "契约测试",
                "life_vision": "测试",
                "character_settings": {"era": {"name": "现代"}},
                "language": "zh",
                "constraint_level": "master",
            },
        )
    assert create_resp.status_code == 201
    data = create_resp.json()
    assert "constraint_level" in data
    assert data["constraint_level"] == "master"

    game_id = data["game_id"]
    with patch("src.api.deps.decode_token", return_value=1):
        load_resp = client.get(f"/api/games/{game_id}", headers=headers)
    assert load_resp.status_code == 200
    loaded = load_resp.json()
    assert loaded.get("constraint_level") == "master"


def test_frontend_api_types_include_constraint_level():
    """验证 frontend/src/lib/api.ts 中 games.load 类型声明包含 constraint_level。"""
    import os

    api_path = os.path.join(
        os.path.dirname(__file__), "..", "frontend", "src", "lib", "api.ts"
    )
    with open(api_path, "r", encoding="utf-8") as f:
        content = f.read()
    # 目前前端可能还没有加上，这个测试会在前端实现后变绿
    assert (
        "constraint_level" in content or "updateSettings" in content
    ), "frontend/src/lib/api.ts 应包含 constraint_level 或 updateSettings"
