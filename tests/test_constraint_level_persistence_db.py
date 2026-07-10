"""真实 DB 集成测试：constraint_level 保存→读取链路完整。"""

from unittest.mock import patch

from fastapi.testclient import TestClient


class TestConstraintLevelPersistence:
    def test_create_game_persists_constraint_level(self, client: TestClient):
        """创建游戏时传入 master，读取后仍为 master。"""
        headers = {"Authorization": "Bearer test_token"}
        with patch("src.api.deps.decode_token", return_value=1):
            create_resp = client.post(
                "/api/games",
                headers=headers,
                json={
                    "player_name": "DB测试",
                    "life_vision": "测试持久化",
                    "character_settings": {"era": {"name": "现代"}},
                    "language": "zh",
                    "constraint_level": "master",
                },
            )
        assert create_resp.status_code == 201
        data = create_resp.json()
        game_id = data["game_id"]

        with patch("src.api.deps.decode_token", return_value=1):
            load_resp = client.get(f"/api/games/{game_id}", headers=headers)
        assert load_resp.status_code == 200
        loaded = load_resp.json()
        assert loaded.get("constraint_level") == "master"

    def test_create_game_default_constraint_level(self, client: TestClient):
        """不传 constraint_level 时，默认值应为 expert。"""
        headers = {"Authorization": "Bearer test_token"}
        with patch("src.api.deps.decode_token", return_value=1):
            create_resp = client.post(
                "/api/games",
                headers=headers,
                json={
                    "player_name": "DB测试默认",
                    "life_vision": "测试默认值",
                    "character_settings": {"era": {"name": "现代"}},
                    "language": "zh",
                },
            )
        assert create_resp.status_code == 201
        data = create_resp.json()
        game_id = data["game_id"]

        with patch("src.api.deps.decode_token", return_value=1):
            load_resp = client.get(f"/api/games/{game_id}", headers=headers)
        assert load_resp.status_code == 200
        loaded = load_resp.json()
        assert loaded.get("constraint_level") == "expert"

    def test_patch_settings_updates_constraint_level(self, client: TestClient):
        """PATCH /api/games/{id}/settings 可更新 constraint_level。"""
        headers = {"Authorization": "Bearer test_token"}
        with patch("src.api.deps.decode_token", return_value=1):
            create_resp = client.post(
                "/api/games",
                headers=headers,
                json={
                    "player_name": "DB测试更新",
                    "life_vision": "测试更新",
                    "character_settings": {"era": {"name": "现代"}},
                    "language": "zh",
                },
            )
        assert create_resp.status_code == 201
        game_id = create_resp.json()["game_id"]

        # 初始为 expert
        with patch("src.api.deps.decode_token", return_value=1):
            load_resp = client.get(f"/api/games/{game_id}", headers=headers)
        assert load_resp.json().get("constraint_level") == "expert"

        # 更新为 fast
        with patch("src.api.deps.decode_token", return_value=1):
            patch_resp = client.patch(
                f"/api/games/{game_id}/settings",
                headers=headers,
                json={"constraint_level": "fast"},
            )
        assert patch_resp.status_code == 200

        # 重新加载验证
        with patch("src.api.deps.decode_token", return_value=1):
            load_resp2 = client.get(f"/api/games/{game_id}", headers=headers)
        assert load_resp2.json().get("constraint_level") == "fast"

    def test_patch_settings_updates_session_game_loop(self, client: TestClient):
        """PATCH 后会话中的 GameLoop.quality_level 同步更新。"""
        headers = {"Authorization": "Bearer test_token"}
        with patch("src.api.deps.decode_token", return_value=1):
            create_resp = client.post(
                "/api/games",
                headers=headers,
                json={
                    "player_name": "DB测试会话",
                    "life_vision": "测试会话同步",
                    "character_settings": {"era": {"name": "现代"}},
                    "language": "zh",
                    "constraint_level": "expert",
                },
            )
        assert create_resp.status_code == 201
        game_id = create_resp.json()["game_id"]

        # 先加载游戏建立会话
        with patch("src.api.deps.decode_token", return_value=1):
            client.get(f"/api/games/{game_id}", headers=headers)

        # 更新为 master
        with patch("src.api.deps.decode_token", return_value=1):
            patch_resp = client.patch(
                f"/api/games/{game_id}/settings",
                headers=headers,
                json={"constraint_level": "master"},
            )
        assert patch_resp.status_code == 200

        # 通过内部检查验证
        from src.api.session_store import session_store

        session = session_store.get(game_id, user_id=1)
        assert session is not None
        assert session.game_loop.quality_level == "master"
