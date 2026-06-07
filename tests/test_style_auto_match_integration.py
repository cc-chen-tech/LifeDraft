"""Integration tests for character-settings patch and narrative style separation."""

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from src.api.main import app

client = TestClient(app)


class TestCharacterSettingsPatchStyleBoundary:
    """Character-settings patch exists but does not auto-match narrative style."""

    def test_character_settings_endpoint_persists_without_auto_matching_style(self):
        """PATCH saves character settings; narrative style remains a separate endpoint."""
        db = MagicMock()
        db.load_saved_game.return_value = {
            "player_name": "StyleBoundary",
            "week": 0,
            "age": 25,
            "character_settings": {"era": {"year": 1990, "era_description": "modern"}},
            "narrative_style_id": "chinese_classic_saga",
        }
        db.save_game_progress.return_value = True

        with patch("src.api.deps.decode_token", return_value=1), patch(
            "src.api.routers.games.get_db", return_value=db
        ):
            resp = client.patch(
                "/api/games/1/character-settings",
                json={
                    "character_settings": {
                        "family": {
                            "family_members": [{"name": "father", "role": "father"}],
                        }
                    }
                },
                headers={"Authorization": "Bearer test_token"},
            )

        assert resp.status_code == 200
        saved_state = db.save_game_progress.call_args.args[1].to_dict()
        assert saved_state["character_settings"]["family"]["family_members"][0]["name"] == "father"
        assert "narrative_style_id" not in saved_state["character_settings"]

    def test_character_settings_endpoint_no_auth_returns_401(self):
        """Unauthenticated requests fail at auth instead of silently no-oping."""
        resp = client.patch(
            "/api/games/1/character-settings",
            json={"character_settings": {"era": {"year": 1990}}},
        )
        assert resp.status_code == 401
