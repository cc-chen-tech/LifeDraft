"""Integration tests for narrative style auto-matching in update_character_settings."""

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from src.api.main import app

client = TestClient(app)


class TestStyleAutoMatch:
    """Test that update_character_settings triggers style matching."""

    def _setup_mocks(self):
        """Helper to set up common DB/session mocks."""
        mock_db = MagicMock()
        mock_db.load_saved_game.return_value = {
            "player_name": "TestPlayer",
            "character_settings": {
                "era": {"year": 1990, "era_description": "现代中国"},
            },
        }

        mock_sess = MagicMock()
        mock_game = MagicMock()
        mock_game.initial_state = {
            "player_name": "TestPlayer",
            "character_settings": {
                "era": {"year": 1990, "era_description": "现代中国"},
            },
        }
        mock_sess.query.return_value.filter.return_value.first.return_value = mock_game

        return mock_db, mock_sess, mock_game

    def test_complete_settings_triggers_style_match(self, mock_auth):
        """When family_members is present, narrative_style_id should be auto-matched."""
        mock_db, mock_sess, mock_game = self._setup_mocks()

        with (
            patch("src.api.routers.games.get_db", return_value=mock_db),
            patch("src.api.routers.games.SessionLocal", return_value=mock_sess),
            patch("src.api.routers.games.session_store") as mock_session_store,
            patch("src.api.routers.games.auto_match_style") as mock_match,
        ):
            mock_session_store.get.return_value = None
            mock_match.return_value.confidence = 0.75
            mock_match.return_value.style_id = "chinese_classic_saga"

            resp = client.patch(
                "/api/games/1/character-settings",
                json={
                    "character_settings": {
                        "era": {"year": 1990, "era_description": "现代中国"},
                        "family_members": [{"name": "父亲", "role": "父亲"}],
                        "world": {"description": "一个普通家庭"},
                    }
                },
                headers={"Authorization": "Bearer test_token"},
            )
            assert resp.status_code == 200
            mock_match.assert_called_once()

        # Verify narrative_style_id was persisted
        assert mock_game.initial_state.get("narrative_style_id") == "chinese_classic_saga"

    def test_incomplete_settings_skips_style_match(self, mock_auth):
        """When family_members is absent, style matching should be skipped."""
        mock_db, mock_sess, mock_game = self._setup_mocks()

        with (
            patch("src.api.routers.games.get_db", return_value=mock_db),
            patch("src.api.routers.games.SessionLocal", return_value=mock_sess),
            patch("src.api.routers.games.session_store") as mock_session_store,
            patch("src.api.routers.games.auto_match_style") as mock_match,
        ):
            mock_session_store.get.return_value = None

            resp = client.patch(
                "/api/games/1/character-settings",
                json={
                    "character_settings": {
                        "era": {"year": 1990, "era_description": "现代中国"},
                    }
                },
                headers={"Authorization": "Bearer test_token"},
            )
            assert resp.status_code == 200
            mock_match.assert_not_called()

    def test_low_confidence_skips_persistence(self, mock_auth):
        """When confidence < 0.3, narrative_style_id should NOT be written."""
        mock_db, mock_sess, mock_game = self._setup_mocks()

        with (
            patch("src.api.routers.games.get_db", return_value=mock_db),
            patch("src.api.routers.games.SessionLocal", return_value=mock_sess),
            patch("src.api.routers.games.session_store") as mock_session_store,
            patch("src.api.routers.games.auto_match_style") as mock_match,
        ):
            mock_session_store.get.return_value = None
            mock_match.return_value.confidence = 0.15
            mock_match.return_value.style_id = "some_style"

            resp = client.patch(
                "/api/games/1/character-settings",
                json={
                    "character_settings": {
                        "family_members": [{"name": "父亲"}],
                    }
                },
                headers={"Authorization": "Bearer test_token"},
            )
            assert resp.status_code == 200

        assert mock_game.initial_state.get("narrative_style_id") is None

    def test_match_exception_is_non_blocking(self, mock_auth):
        """When auto_match_style raises, the API should still return 200."""
        mock_db, mock_sess, mock_game = self._setup_mocks()

        with (
            patch("src.api.routers.games.get_db", return_value=mock_db),
            patch("src.api.routers.games.SessionLocal", return_value=mock_sess),
            patch("src.api.routers.games.session_store") as mock_session_store,
            patch("src.api.routers.games.auto_match_style") as mock_match,
        ):
            mock_session_store.get.return_value = None
            mock_match.side_effect = RuntimeError("matching failed")

            resp = client.patch(
                "/api/games/1/character-settings",
                json={
                    "character_settings": {
                        "family_members": [{"name": "父亲"}],
                    }
                },
                headers={"Authorization": "Bearer test_token"},
            )
            assert resp.status_code == 200
