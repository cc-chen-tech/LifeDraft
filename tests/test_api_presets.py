"""Tests for presets API routes."""
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from src.api.main import app


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def mock_db():
    """Mock GameDatabase."""
    with patch("src.api.routers.presets.get_db") as mock:
        db = MagicMock()
        mock.return_value = db
        yield db


@pytest.fixture
def auth_headers():
    """Create auth headers."""
    return {"Authorization": "Bearer test_token"}


@pytest.fixture
def mock_auth():
    """Mock authentication."""
    with patch("src.api.deps.decode_token") as mock:
        mock.return_value = 1
        yield mock


class TestCreatePreset:
    """Tests for POST /api/presets."""

    def test_create_preset_success(self, client, mock_db, mock_auth, auth_headers):
        """Test creating a new preset."""
        mock_db.save_character_preset.return_value = 1

        response = client.post("/api/presets", json={
            "preset_name": "My Hero",
            "player_name": "Hero",
            "life_vision": "Be a hero",
            "character_settings": {"era": {"era_name": "现代"}}
        }, headers=auth_headers)

        assert response.status_code == 201
        data = response.json()
        assert data["preset_id"] == 1
        assert data["preset_name"] == "My Hero"
        assert data["player_name"] == "Hero"

    def test_create_preset_without_auth(self, client, mock_db):
        """Test creating preset without auth (anonymous)."""
        mock_db.save_character_preset.return_value = 2

        response = client.post("/api/presets", json={
            "preset_name": "Anonymous Preset",
            "player_name": "Anon",
            "life_vision": "",
            "character_settings": {}
        })

        assert response.status_code == 201

    def test_create_preset_empty_name(self, client, mock_auth, auth_headers):
        """Test creating preset with empty name."""
        response = client.post("/api/presets", json={
            "preset_name": "",
            "player_name": "Test",
            "life_vision": "",
            "character_settings": {}
        }, headers=auth_headers)

        assert response.status_code == 422

    def test_create_preset_name_too_long(self, client, mock_auth, auth_headers):
        """Test creating preset with name exceeding max length."""
        long_name = "x" * 101
        response = client.post("/api/presets", json={
            "preset_name": long_name,
            "player_name": "Test",
            "life_vision": "",
            "character_settings": {}
        }, headers=auth_headers)

        assert response.status_code == 422

    def test_create_preset_db_error(self, client, mock_db, mock_auth, auth_headers):
        """Test preset creation database error."""
        mock_db.save_character_preset.side_effect = Exception("DB error")

        response = client.post("/api/presets", json={
            "preset_name": "Test",
            "player_name": "Test",
            "life_vision": "",
            "character_settings": {}
        }, headers=auth_headers)

        assert response.status_code == 500


class TestListPresets:
    """Tests for GET /api/presets."""

    def test_list_presets_success(self, client, mock_db, mock_auth, auth_headers):
        """Test listing presets."""
        from datetime import datetime
        mock_preset = MagicMock()
        mock_preset.preset_id = 1
        mock_preset.preset_name = "My Preset"
        mock_preset.player_name = "Hero"
        mock_preset.life_vision = "Be great"
        mock_preset.character_settings = {"era": {}}
        mock_preset.created_at = datetime(2024, 1, 1, 12, 0, 0)
        
        mock_db.list_character_presets.return_value = [mock_preset]

        response = client.get("/api/presets", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["preset_name"] == "My Preset"

    def test_list_presets_empty(self, client, mock_db, mock_auth, auth_headers):
        """Test listing presets when none exist."""
        mock_db.list_character_presets.return_value = []

        response = client.get("/api/presets", headers=auth_headers)

        assert response.status_code == 200
        assert response.json() == []

    def test_list_presets_with_limit(self, client, mock_db, mock_auth, auth_headers):
        """Test listing presets with limit."""
        mock_db.list_character_presets.return_value = []

        response = client.get("/api/presets?limit=5", headers=auth_headers)

        assert response.status_code == 200
        mock_db.list_character_presets.assert_called_with(limit=5, user_id=1)

    def test_list_presets_without_auth(self, client, mock_db):
        """Test listing presets without auth."""
        mock_db.list_character_presets.return_value = []

        response = client.get("/api/presets")

        assert response.status_code == 200


class TestGetPreset:
    """Tests for GET /api/presets/{preset_id}."""

    def test_get_preset_success(self, client, mock_db, mock_auth, auth_headers):
        """Test getting a single preset."""
        mock_db.load_character_preset.return_value = {
            "preset_id": 1,
            "preset_name": "My Preset",
            "player_name": "Hero",
            "life_vision": "Be great",
            "character_settings": {"era": {}},
            "created_at": "2024-01-01T12:00:00"
        }

        response = client.get("/api/presets/1", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["preset_id"] == 1
        assert data["preset_name"] == "My Preset"

    def test_get_preset_not_found(self, client, mock_db, mock_auth, auth_headers):
        """Test getting non-existent preset."""
        mock_db.load_character_preset.return_value = None

        response = client.get("/api/presets/999", headers=auth_headers)

        assert response.status_code == 404

    def test_get_preset_without_auth(self, client, mock_db):
        """Test getting preset without auth."""
        mock_db.load_character_preset.return_value = {
            "preset_id": 1,
            "preset_name": "Public Preset",
            "player_name": "Test",
            "life_vision": "",
            "character_settings": {}
        }

        response = client.get("/api/presets/1")

        assert response.status_code == 200


class TestDeletePreset:
    """Tests for DELETE /api/presets/{preset_id}."""

    def test_delete_preset_success(self, client, mock_db, mock_auth, auth_headers):
        """Test deleting a preset."""
        mock_db.delete_character_preset.return_value = True

        response = client.delete("/api/presets/1", headers=auth_headers)

        assert response.status_code == 200
        assert "deleted" in response.json()["message"].lower()

    def test_delete_preset_not_found(self, client, mock_db, mock_auth, auth_headers):
        """Test deleting non-existent preset."""
        mock_db.delete_character_preset.return_value = False

        response = client.delete("/api/presets/999", headers=auth_headers)

        assert response.status_code == 404

    def test_delete_preset_without_auth(self, client, mock_db):
        """Test deleting preset without auth."""
        mock_db.delete_character_preset.return_value = True

        response = client.delete("/api/presets/1")

        # Should work (anonymous deletion)
        assert response.status_code == 200
