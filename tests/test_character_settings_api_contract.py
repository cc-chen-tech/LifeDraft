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
        assert saved_state["character_settings"]["wealth"]["initial_wealth"] == "middle"

    def test_update_character_settings_rejects_empty_payload(self) -> None:
        with patch("src.api.deps.decode_token", return_value=1):
            response = client.patch(
                "/api/games/42/character-settings",
                json={"character_settings": {}},
                headers={"Authorization": "Bearer test-token"},
            )

        assert response.status_code == 422
