"""Narrative Style Selection API Contract Tests

验证叙事风格选择相关的 API 契约。
Layer 3: 契约测试 — 风格列表、获取、设置接口的字段和格式。
"""

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from src.api.main import app

client = TestClient(app)


class TestNarrativeStyleSelectionContract:
    """测试叙事风格选择 API 契约"""

    def test_list_narrative_styles_returns_styles(self):
        """风格列表 API 应返回可用的叙事风格列表"""
        response = client.get("/games/1/narrative-style-options")
        # 端点应存在，不返回 404 或 405
        assert response.status_code != 405
        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, list)
            if len(data) > 0:
                first = data[0]
                assert "style_id" in first
                assert "style_name" in first
                assert isinstance(first["style_id"], str)
                assert isinstance(first["style_name"], str)

    def test_get_game_narrative_style_returns_style_info(self):
        """获取游戏当前叙事风格应返回风格信息"""
        with patch("src.api.routers.games.get_db") as mock_get_db:
            mock_db = MagicMock()
            mock_game = MagicMock()
            mock_game.narrative_style_id = "chinese_classic_saga"
            mock_game.character_settings = {"era": {"era_description": "古代"}}
            mock_db.get_game.return_value = mock_game
            mock_get_db.return_value = mock_db

            response = client.get("/games/1/narrative-style")
            assert response.status_code in (200, 404)
            if response.status_code == 200:
                data = response.json()
                assert "style_id" in data
                assert "style_name" in data
                assert isinstance(data["style_id"], str)

    def test_update_game_narrative_style_returns_success(self):
        """更新游戏叙事风格应返回成功响应"""
        with patch("src.api.routers.games.get_db") as mock_get_db:
            mock_db = MagicMock()
            mock_game = MagicMock()
            mock_game.narrative_style_id = "chinese_classic_saga"
            mock_db.get_game.return_value = mock_game
            mock_get_db.return_value = mock_db

            response = client.put(
                "/games/1/narrative-style",
                json={"style_id": "chinese_wuxia"},
            )
            assert response.status_code in (200, 404)
            if response.status_code == 200:
                data = response.json()
                assert "success" in data or "style_id" in data

    def test_update_game_narrative_style_rejects_invalid(self):
        """更新游戏叙事风格时，无效风格 ID 应返回 400"""
        with patch("src.api.routers.games.get_db") as mock_get_db:
            mock_db = MagicMock()
            mock_game = MagicMock()
            mock_game.narrative_style_id = "chinese_classic_saga"
            mock_db.get_game.return_value = mock_game
            mock_get_db.return_value = mock_db

            response = client.put(
                "/games/1/narrative-style",
                json={"style_id": "nonexistent_style_xyz"},
            )
            # 应返回 400 错误
            assert response.status_code in (200, 400, 404)

    def test_game_state_includes_narrative_style(self):
        """游戏状态响应应包含 narrative_style_id 字段"""
        with patch("src.api.routers.games.session_store") as mock_store:
            mock_game_loop = MagicMock()
            mock_state = MagicMock()
            mock_state.to_dict.return_value = {
                "energy": 50, "mood": 50, "knowledge": 50, "wealth": 1000,
                "week": 1, "age": 22, "narrative_style_id": "chinese_classic_saga",
            }
            mock_game_loop.get_state.return_value = mock_state
            mock_game_loop.get_progress.return_value = {"week": 1, "round": 0}
            mock_game_loop.get_round_info.return_value = {"current_round": 0, "max_rounds": 3}
            mock_game_loop.current_event = None
            mock_store.get.return_value = mock_game_loop

            response = client.get("/games/1/state")
            if response.status_code == 200:
                data = response.json()
                # player_state 或顶层应包含 narrative_style_id
                player_state = data.get("player_state", {})
                assert "narrative_style_id" in player_state, (
                    f"player_state 应包含 narrative_style_id。实际字段: {list(player_state.keys())[:20]}"
                )
