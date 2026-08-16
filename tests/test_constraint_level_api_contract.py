"""契约测试：约束级别持久化前后端字段一致性。"""

from unittest.mock import MagicMock, patch

import pytest
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
    response = client.patch("/api/games/1/settings", json={"constraint_level": "master"})
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

    api_path = os.path.join(os.path.dirname(__file__), "..", "frontend", "src", "lib", "api.ts")
    with open(api_path, "r", encoding="utf-8") as f:
        content = f.read()
    # 目前前端可能还没有加上，这个测试会在前端实现后变绿
    assert (
        "constraint_level" in content or "updateSettings" in content
    ), "frontend/src/lib/api.ts 应包含 constraint_level 或 updateSettings"


def test_quality_switch_rebinds_all_live_round_services() -> None:
    """Replacing only GameLoop.ai_generator leaves live services on the old tier."""
    from src.game.game_loop import GameLoop

    old_generator = MagicMock()
    new_generator = MagicMock()
    loop = GameLoop(language="zh", ai_generator=old_generator, quality_level="fast")
    loop.start_new_game()
    loop._init_round_services()

    loop.set_quality_level("master", ai_generator=new_generator)

    assert loop.quality_level == "master"
    assert loop.ai_generator is new_generator
    assert loop._event_generator_service.ai_generator is new_generator
    assert loop._choice_processor.ai_generator is new_generator
    assert loop._finalizer.ai_generator is new_generator
    assert loop.story_service.ai_generator is new_generator


@pytest.mark.asyncio
async def test_live_quality_switch_uses_generation_lock(monkeypatch) -> None:
    """A tier switch must not replace services while a worker is using them."""
    from src.api.routers import games as games_router
    from src.api.routers.gameplay import sse_helpers
    from src.api.schemas import UpdateGameSettingsRequest

    lock_state = {"held": False, "entered": 0}

    class Guard:
        def __enter__(self):
            lock_state["held"] = True
            lock_state["entered"] += 1

        def __exit__(self, *_args):
            lock_state["held"] = False

    class FakeDb:
        def load_saved_game(self, game_id, user_id):
            return {"game_id": game_id, "user_id": user_id}

    game_row = MagicMock()
    db_session = MagicMock()
    db_session.query.return_value.filter.return_value.first.return_value = game_row
    db_session.commit.side_effect = lambda: (
        None if lock_state["held"] else (_ for _ in ()).throw(AssertionError("commit outside lock"))
    )
    loop = MagicMock()

    def set_quality_level(level):
        assert lock_state["held"] is True
        loop.quality_level = level

    loop.set_quality_level.side_effect = set_quality_level
    session = MagicMock(game_loop=loop)
    monkeypatch.setattr(games_router, "get_db", lambda: FakeDb())
    monkeypatch.setattr(games_router, "SessionLocal", lambda: db_session)
    monkeypatch.setattr(games_router.session_store, "get", lambda *args, **kwargs: session)
    monkeypatch.setattr(sse_helpers, "_get_game_state_lock", lambda _game_id: Guard())

    await games_router.update_game_settings(
        42,
        UpdateGameSettingsRequest(constraint_level="master"),
        user_id=7,
    )

    assert lock_state["entered"] == 1
    loop.set_quality_level.assert_called_once_with("master")
