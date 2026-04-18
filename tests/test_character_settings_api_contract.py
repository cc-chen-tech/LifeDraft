"""API 契约测试 - PATCH /api/games/{game_id}/character-settings

验证新端点的请求/响应格式，确保前端和后端对字段名的理解一致。
这些测试在实现代码之前编写，定义了生产者和消费者之间的契约。
"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from src.api.main import app

client = TestClient(app)


class TestCharacterSettingsUpdateAPIContract:
    """契约测试：PATCH /api/games/{game_id}/character-settings"""

    def test_update_character_settings_unauthorized(self):
        """未认证请求应返回 401"""
        response = client.patch(
            "/api/games/1/character-settings",
            json={"character_settings": {"family": {"background": "test"}}},
        )
        assert response.status_code == 401
        data = response.json()
        assert "detail" in data

    def test_update_character_settings_schema_valid(self, mock_auth):
        """正确 schema 应返回 200，且响应包含 success 和 message"""
        with (
            patch("src.api.routers.games.get_db") as mock_get_db,
            patch("src.api.routers.games.SessionLocal") as mock_session_local,
            patch("src.api.routers.games.session_store") as mock_session_store,
        ):
            # Mock DB: load_saved_game returns state with partial settings
            mock_db = MagicMock()
            mock_db.load_saved_game.return_value = {
                "player_name": "TestPlayer",
                "character_settings": {
                    "era": {"era_name": "现代"},
                    "age": {"start_age": 25},
                    "gender": {"gender": "male"},
                    "world": {"world_name": "现代都市"},
                },
            }
            mock_get_db.return_value = mock_db

            # Mock DB session for Game query
            mock_sess = MagicMock()
            mock_game = MagicMock()
            mock_game.initial_state = {
                "player_name": "TestPlayer",
                "character_settings": {
                    "era": {"era_name": "现代"},
                },
            }
            mock_sess.query.return_value.filter.return_value.first.return_value = mock_game
            mock_session_local.return_value = mock_sess

            # Mock session_store (no active session)
            mock_session_store.get.return_value = None

            response = client.patch(
                "/api/games/1/character-settings",
                json={
                    "character_settings": {
                        "family": {"family_background": "中产家庭"},
                        "relationships": {
                            "key_people": [{"name": "李明", "relationship": "好友"}],
                        },
                        "traits": {"personality": ["好奇", "有野心"]},
                        "wealth": {"initial_wealth": "middle"},
                    }
                },
                headers={"Authorization": "Bearer test_token"},
            )

            assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
            data = response.json()
            assert "success" in data
            assert "message" in data
            assert data["success"] is True

    def test_update_preserves_existing_fields(self, mock_auth):
        """PATCH 应合并而非覆盖：原有 era/age/gender/world 保留，新增 family/relationships/traits/wealth"""
        with (
            patch("src.api.routers.games.get_db") as mock_get_db,
            patch("src.api.routers.games.SessionLocal") as mock_session_local,
            patch("src.api.routers.games.session_store") as mock_session_store,
        ):
            mock_db = MagicMock()
            mock_db.load_saved_game.return_value = {
                "player_name": "TestPlayer",
                "character_settings": {
                    "era": {"era_name": "现代"},
                    "age": {"start_age": 25},
                    "gender": {"gender": "male"},
                    "world": {"world_name": "现代都市"},
                },
            }
            mock_get_db.return_value = mock_db

            mock_sess = MagicMock()
            mock_game = MagicMock()
            mock_game.initial_state = {
                "player_name": "TestPlayer",
                "character_settings": {
                    "era": {"era_name": "现代"},
                    "age": {"start_age": 25},
                    "gender": {"gender": "male"},
                    "world": {"world_name": "现代都市"},
                },
            }
            mock_sess.query.return_value.filter.return_value.first.return_value = mock_game
            mock_session_local.return_value = mock_sess
            mock_session_store.get.return_value = None

            client.patch(
                "/api/games/1/character-settings",
                json={
                    "character_settings": {
                        "family": {"family_background": "中产家庭"},
                        "traits": {"personality": ["好奇"]},
                    }
                },
                headers={"Authorization": "Bearer test_token"},
            )

            updated_cs = mock_game.initial_state["character_settings"]
            # 原有字段必须保留
            assert "era" in updated_cs, "era 不应被覆盖"
            assert "age" in updated_cs, "age 不应被覆盖"
            assert "gender" in updated_cs, "gender 不应被覆盖"
            assert "world" in updated_cs, "world 不应被覆盖"
            # 新增字段必须存在
            assert "family" in updated_cs, "family 应被添加"
            assert "traits" in updated_cs, "traits 应被添加"

    def test_update_character_settings_persists_all_fields(self, mock_auth):
        """PATCH 后 Game.initial_state.character_settings 应包含所有 8+ 个 setting key"""
        with (
            patch("src.api.routers.games.get_db") as mock_get_db,
            patch("src.api.routers.games.SessionLocal") as mock_session_local,
            patch("src.api.routers.games.session_store") as mock_session_store,
        ):
            mock_db = MagicMock()
            mock_db.load_saved_game.return_value = {
                "player_name": "TestPlayer",
                "character_settings": {
                    "era": {"era_name": "现代"},
                    "age": {"start_age": 25},
                    "gender": {"gender": "male"},
                    "world": {"world_name": "现代都市"},
                },
            }
            mock_get_db.return_value = mock_db

            mock_sess = MagicMock()
            mock_game = MagicMock()
            mock_game.initial_state = {
                "player_name": "TestPlayer",
                "character_settings": {
                    "era": {"era_name": "现代"},
                    "age": {"start_age": 25},
                    "gender": {"gender": "male"},
                    "world": {"world_name": "现代都市"},
                },
            }
            mock_sess.query.return_value.filter.return_value.first.return_value = mock_game
            mock_session_local.return_value = mock_sess
            mock_session_store.get.return_value = None

            response = client.patch(
                "/api/games/1/character-settings",
                json={
                    "character_settings": {
                        "family": {"family_background": "中产家庭"},
                        "relationships": {
                            "key_people": [
                                {"name": "李明", "relationship": "好友"},
                                {"name": "王芳", "relationship": "同事"},
                            ],
                        },
                        "traits": {"personality": ["好奇", "有野心"], "strengths": ["学习能力强"]},
                        "wealth": {"initial_wealth": "middle", "description": "小康水平"},
                    }
                },
                headers={"Authorization": "Bearer test_token"},
            )

            assert response.status_code == 200
            updated_cs = mock_game.initial_state["character_settings"]
            required_keys = ["era", "age", "gender", "world", "family", "relationships", "traits", "wealth"]
            for key in required_keys:
                assert key in updated_cs, f"character_settings 必须包含 {key}"

    def test_update_character_settings_game_not_found(self, mock_auth):
        """游戏不存在时应返回 404"""
        with patch("src.api.routers.games.get_db") as mock_get_db:
            mock_db = MagicMock()
            mock_db.load_saved_game.return_value = None
            mock_get_db.return_value = mock_db

            response = client.patch(
                "/api/games/999/character-settings",
                json={"character_settings": {"family": {"background": "test"}}},
                headers={"Authorization": "Bearer test_token"},
            )

            assert response.status_code == 404
            data = response.json()
            assert "detail" in data

    def test_update_character_settings_session_sync(self, mock_auth):
        """PATCH 后 session_store 中的 game_loop.player_state.character_settings 应同步更新"""
        with (
            patch("src.api.routers.games.get_db") as mock_get_db,
            patch("src.api.routers.games.SessionLocal") as mock_session_local,
            patch("src.api.routers.games.session_store") as mock_session_store,
        ):
            mock_db = MagicMock()
            mock_db.load_saved_game.return_value = {
                "player_name": "TestPlayer",
                "character_settings": {"era": {"era_name": "现代"}},
            }
            mock_get_db.return_value = mock_db

            mock_sess = MagicMock()
            mock_game = MagicMock()
            mock_game.initial_state = {
                "player_name": "TestPlayer",
                "character_settings": {"era": {"era_name": "现代"}},
            }
            mock_sess.query.return_value.filter.return_value.first.return_value = mock_game
            mock_session_local.return_value = mock_sess

            # Mock active session with player_state
            mock_player_state = MagicMock()
            mock_player_state.character_settings = {"era": {"era_name": "现代"}}
            mock_game_loop = MagicMock()
            mock_game_loop.player_state = mock_player_state
            mock_session = MagicMock()
            mock_session.game_loop = mock_game_loop
            mock_session_store.get.return_value = mock_session

            response = client.patch(
                "/api/games/1/character-settings",
                json={
                    "character_settings": {
                        "family": {"family_background": "中产家庭"},
                        "traits": {"personality": ["好奇"]},
                    }
                },
                headers={"Authorization": "Bearer test_token"},
            )

            assert response.status_code == 200
            # Verify session player_state was updated
            assert "family" in mock_player_state.character_settings
            assert "traits" in mock_player_state.character_settings
            assert "era" in mock_player_state.character_settings
