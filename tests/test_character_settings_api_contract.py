"""API 契约测试 - PATCH /api/games/{game_id}/character-settings

该端点已被移除。character_settings 现在在游戏创建时一次性提交，
不再支持 PATCH 增量更新。
"""

from fastapi.testclient import TestClient

from src.api.main import app

client = TestClient(app)


class TestCharacterSettingsUpdateAPIContract:
    """契约测试：PATCH /api/games/{game_id}/character-settings（已移除）"""

    def test_update_character_settings_endpoint_removed(self):
        """端点已移除，应返回 404"""
        response = client.patch(
            "/api/games/1/character-settings",
            json={"character_settings": {"family": {"background": "test"}}},
        )
        assert response.status_code == 404

    def test_update_character_settings_unauthorized_removed(self):
        """未认证请求同样返回 404（端点不存在，不检查认证）"""
        response = client.patch(
            "/api/games/1/character-settings",
            json={"character_settings": {"family": {"background": "test"}}},
        )
        assert response.status_code == 404

    def test_update_character_settings_game_not_found(self):
        """不存在的游戏返回 404（端点本身不存在）"""
        response = client.patch(
            "/api/games/999/character-settings",
            json={"character_settings": {"family": {"background": "test"}}},
        )
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
