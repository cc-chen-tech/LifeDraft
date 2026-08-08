"""API contract tests for PATCH /api/games/{game_id}/character-settings."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from src.api.main import app


client = TestClient(app)


class TestCharacterSettingsUpdateAPIContract:
    """PATCH /api/games/{game_id}/character-settings should persist late settings."""

    def test_update_character_settings_requires_auth(self) -> None:
        response = client.patch(
            "/api/games/1/character-settings",
            json={"character_settings": {"family": {"family_background": "test"}}},
        )

        assert response.status_code == 401

    def test_update_character_settings_returns_404_for_wrong_owner(self) -> None:
        db = MagicMock()
        db.load_saved_game.return_value = None

        with patch("src.api.deps.decode_token", return_value=1), patch(
            "src.api.routers.games.get_db", return_value=db
        ):
            response = client.patch(
                "/api/games/999/character-settings",
                json={"character_settings": {"family": {"family_background": "test"}}},
                headers={"Authorization": "Bearer test-token"},
            )

        assert response.status_code == 404
        assert response.json()["detail"] == "Game not found or not owned by user"
        db.save_game_progress.assert_not_called()

    def test_update_character_settings_merges_and_saves_state(self) -> None:
        db = MagicMock()
        existing_state = {
            "player_name": "陆昊然",
            "life_vision": "成为优秀产品经理",
            "age": 26,
            "week": 0,
            "character_settings": {
                "era": {"era_name": "2020年代中国互联网"},
                "age": {"age": 26, "birth_year": 1998},
                "relationships": {
                    "key_people": [
                        {"name": "陈晓雨", "relationship": "朋友", "affinity": 72}
                    ]
                },
            },
        }
        db.load_saved_game.return_value = existing_state
        db.save_game_progress.return_value = True

        late_settings = {
            "family": {
                "family_background": "普通城市家庭",
                "family_members": ["父亲", "母亲"],
            },
            "relationships": {
                "relationships_description": "产品团队和老朋友是核心关系",
                "key_people": [
                    {"name": "陈晓雨", "relationship": "朋友", "affinity": 72},
                    {"name": "林一凡", "relationship": "同事", "affinity": 55},
                ],
            },
            "traits": {"personality": ["谨慎", "有责任感"]},
            "wealth": {"initial_wealth": "middle"},
        }

        with patch("src.api.deps.decode_token", return_value=1), patch(
            "src.api.routers.games.get_db", return_value=db
        ):
            response = client.patch(
                "/api/games/42/character-settings",
                json={"character_settings": late_settings},
                headers={"Authorization": "Bearer test-token"},
            )

        assert response.status_code == 200
        assert response.json()["success"] is True
        assert response.json()["message"] == "Character settings updated"

        db.load_saved_game.assert_called_once_with(42, 1)
        db.save_game_progress.assert_called_once()
        saved_game_id, saved_player_state = db.save_game_progress.call_args.args
        saved_state = saved_player_state.to_dict()
        assert saved_game_id == 42
        assert saved_state["player_name"] == "陆昊然"
        assert saved_state["character_settings"]["era"]["era_name"] == "2020年代中国互联网"
        assert saved_state["character_settings"]["age"]["birth_year"] == 1998
        assert saved_state["character_settings"]["family"]["family_background"] == "普通城市家庭"
        assert len(saved_state["character_settings"]["relationships"]["key_people"]) == 2
        assert "wealth" not in saved_state["character_settings"]

    def test_update_character_settings_drops_legacy_generated_wealth(self) -> None:
        db = MagicMock()
        existing_state = {
            "player_name": "苏清岚",
            "life_vision": "做现代上海独立游戏",
            "age": 30,
            "week": 0,
            "current_round": 0,
            "wealth": 10000,
            "character_settings": {
                "era": {"era_name": "2024年上海"},
                "age": {"age": 30, "birth_year": 1994},
            },
        }
        db.load_saved_game.return_value = existing_state
        db.save_game_progress.return_value = True

        late_settings = {
            "wealth": {
                "wealth": 60000,
                "wealth_description": "大厂积蓄、父母支持和天使预付款共计六万元。",
            }
        }

        with patch("src.api.deps.decode_token", return_value=1), patch(
            "src.api.routers.games.get_db", return_value=db
        ):
            response = client.patch(
                "/api/games/109/character-settings",
                json={"character_settings": late_settings},
                headers={"Authorization": "Bearer test-token"},
            )

        assert response.status_code == 200
        saved_state = db.save_game_progress.call_args.args[1].to_dict()
        assert "wealth" not in saved_state["character_settings"]
        assert "wealth" not in saved_state

    def test_update_character_settings_drops_legacy_starting_wealth(self) -> None:
        """Legacy starting_wealth payloads are accepted but retired state is discarded."""
        db = MagicMock()
        existing_state = {
            "player_name": "张若虚",
            "life_vision": "成为可靠的产品经理",
            "age": 28,
            "week": 0,
            "current_round": 0,
            "wealth": 10000,
            "character_settings": {
                "era": {"era_name": "2024年上海"},
                "age": {"age": 28, "birth_year": 1996},
            },
        }
        db.load_saved_game.return_value = existing_state
        db.save_game_progress.return_value = True

        late_settings = {
            "wealth": {
                "wealth_level": "中等",
                "starting_wealth": 50000,
                "currency": "¥",
                "currency_name": "元",
            }
        }

        with patch("src.api.deps.decode_token", return_value=1), patch(
            "src.api.routers.games.get_db", return_value=db
        ):
            response = client.patch(
                "/api/games/109/character-settings",
                json={"character_settings": late_settings},
                headers={"Authorization": "Bearer test-token"},
            )

        assert response.status_code == 200
        saved_state = db.save_game_progress.call_args.args[1].to_dict()
        assert "wealth" not in saved_state["character_settings"]
        assert "wealth" not in saved_state

    def test_update_character_settings_drops_legacy_currency_wealth_before_play(
        self,
    ) -> None:
        """Formatted legacy currency payloads are also discarded."""
        db = MagicMock()
        existing_state = {
            "player_name": "张若虚",
            "life_vision": "成为可靠的产品经理",
            "age": 28,
            "week": 0,
            "current_round": 0,
            "wealth": 10000,
            "character_settings": {
                "era": {"era_name": "2024年上海"},
                "age": {"age": 28, "birth_year": 1996},
            },
        }
        db.load_saved_game.return_value = existing_state
        db.save_game_progress.return_value = True

        late_settings = {
            "wealth": {
                "wealth_level": "中等",
                "initial_wealth": "50,000元",
                "currency": "¥",
                "currency_name": "元",
            }
        }

        with patch("src.api.deps.decode_token", return_value=1), patch(
            "src.api.routers.games.get_db", return_value=db
        ):
            response = client.patch(
                "/api/games/109/character-settings",
                json={"character_settings": late_settings},
                headers={"Authorization": "Bearer test-token"},
            )

        assert response.status_code == 200
        saved_state = db.save_game_progress.call_args.args[1].to_dict()
        assert "wealth" not in saved_state["character_settings"]
        assert "wealth" not in saved_state

    def test_update_character_settings_can_replace_stale_identity_before_play(self) -> None:
        """已有 gameId 继续创建新角色时，应同步覆盖旧 player_name/life_vision。"""
        db = MagicMock()
        existing_state = {
            "player_name": "苏清岚",
            "life_vision": "2024年上海，女性独立游戏制作人",
            "age": 30,
            "week": 0,
            "current_round": 0,
            "wealth": 60000,
            "character_settings": {
                "era": {"era_description": "2024年的上海"},
            },
        }
        db.load_saved_game.return_value = existing_state
        db.save_game_progress.return_value = True

        late_settings = {
            "era": {"era_description": "2026年的深圳"},
            "age": {"age": 32, "birth_year": 1994},
            "wealth": {"wealth": 80000},
        }

        with patch("src.api.deps.decode_token", return_value=1), patch(
            "src.api.routers.games.get_db", return_value=db
        ):
            response = client.patch(
                "/api/games/109/character-settings",
                json={
                    "character_settings": late_settings,
                    "player_name": "沈若澜",
                    "life_vision": "2026年的深圳，女性AI教育产品创始人",
                },
                headers={"Authorization": "Bearer test-token"},
            )

        assert response.status_code == 200
        saved_state = db.save_game_progress.call_args.args[1].to_dict()
        assert saved_state["player_name"] == "沈若澜"
        assert saved_state["life_vision"] == "2026年的深圳，女性AI教育产品创始人"
        assert saved_state["character_settings"]["era"]["era_description"] == "2026年的深圳"

    def test_update_character_settings_rejects_empty_payload(self) -> None:
        with patch("src.api.deps.decode_token", return_value=1):
            response = client.patch(
                "/api/games/42/character-settings",
                json={"character_settings": {}},
                headers={"Authorization": "Bearer test-token"},
            )

        assert response.status_code == 422
