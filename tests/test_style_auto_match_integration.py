"""Integration tests for narrative style auto-matching.

The update_character_settings endpoint (which triggered style auto-matching)
has been removed. Narrative style is now set once at game creation.
"""

from fastapi.testclient import TestClient

from src.api.main import app

client = TestClient(app)


class TestStyleAutoMatchRemoved:
    """The character-settings endpoint no longer exists — returns 404."""

    def test_character_settings_endpoint_removed(self):
        """PATCH /games/{id}/character-settings returns 404."""
        resp = client.patch(
            "/api/games/1/character-settings",
            json={
                "character_settings": {
                    "era": {"year": 1990, "era_description": "modern"},
                    "family_members": [{"name": "father", "role": "father"}],
                }
            },
            headers={"Authorization": "Bearer test_token"},
        )
        assert resp.status_code == 404

    def test_character_settings_endpoint_removed_no_auth(self):
        """Unauthenticated also returns 404 (endpoint gone)."""
        resp = client.patch(
            "/api/games/1/character-settings",
            json={"character_settings": {"era": {"year": 1990}}},
        )
        assert resp.status_code == 404
