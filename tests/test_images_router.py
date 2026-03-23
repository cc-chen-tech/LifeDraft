"""Tests for images router - simplified version."""

from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.deps import get_current_user
from src.api.routers.images import router, verify_game_ownership, verify_image_ownership
from src.services.image_service import ImageContentError, ImageServiceError
from src.services.image_storage import ImageStorageError


@pytest.fixture
def app():
    """Create test app with images router."""
    app = FastAPI()
    app.include_router(router, prefix="/images")
    return app


@pytest.fixture
def client(app):
    """Create test client."""
    return TestClient(app)


class TestVerifyGameOwnership:
    """Test verify_game_ownership function."""

    def test_verify_game_ownership_success(self):
        """Test successful game ownership verification."""
        mock_db = MagicMock()
        mock_game = MagicMock()
        mock_game.user_id = 1
        mock_db.query.return_value.filter.return_value.first.return_value = mock_game

        result = verify_game_ownership(mock_db, 1, 1)
        assert result == mock_game

    def test_verify_game_ownership_game_not_found(self):
        """Test when game is not found."""
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None

        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc:
            verify_game_ownership(mock_db, 999, 1)
        assert exc.value.status_code == 404

    def test_verify_game_ownership_wrong_user(self):
        """Test when game belongs to different user."""
        mock_db = MagicMock()
        mock_game = MagicMock()
        mock_game.user_id = 2
        mock_db.query.return_value.filter.return_value.first.return_value = mock_game

        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc:
            verify_game_ownership(mock_db, 1, 1)
        assert exc.value.status_code == 404

    def test_verify_game_ownership_no_user_id_backward_compat(self):
        """Test backward compatibility when game has no user_id."""
        mock_db = MagicMock()
        mock_game = MagicMock()
        mock_game.user_id = None
        mock_db.query.return_value.filter.return_value.first.return_value = mock_game

        result = verify_game_ownership(mock_db, 1, 1)
        assert result == mock_game


class TestVerifyImageOwnership:
    """Test verify_image_ownership function."""

    def test_verify_image_ownership_success(self):
        """Test successful image ownership verification."""
        mock_db = MagicMock()
        mock_image = MagicMock()
        mock_image.game_id = 1
        mock_image.image_id = 1
        mock_db.query.return_value.filter.return_value.first.return_value = mock_image

        with patch("src.api.routers.images.verify_game_ownership") as mock_verify:
            result = verify_image_ownership(mock_db, 1, 1)
            mock_verify.assert_called_once()

    def test_verify_image_ownership_not_found(self):
        """Test when image is not found."""
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None

        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc:
            verify_image_ownership(mock_db, 999, 1)
        assert exc.value.status_code == 404


class TestGetImageFileEndpoint:
    """Test /file/{game_id}/{image_type}/{filename} endpoint."""

    @patch("src.api.routers.images.ImageStorageService")
    def test_get_image_file_success(self, mock_storage_class, app, client):
        """Test getting image file."""
        from pathlib import Path

        # Mock auth dependency
        app.dependency_overrides[get_current_user] = lambda: 1

        mock_storage = MagicMock()
        mock_storage.image_exists.return_value = True
        mock_storage.get_image_data.return_value = b"fake_image_data"
        mock_storage.local_path = Path("/data/images")
        mock_storage_class.return_value = mock_storage

        try:
            with patch("src.api.routers.images.get_session") as mock_session_gen:
                mock_session_gen.return_value = iter([MagicMock()])
                response = client.get("/images/file/1/character/test.png")

            assert response.status_code == 200
            assert response.content == b"fake_image_data"
        finally:
            app.dependency_overrides.clear()

    @patch("src.api.routers.images.ImageStorageService")
    def test_get_image_file_storage_error(self, mock_storage_class, app, client):
        """Test handling storage error."""
        from pathlib import Path

        # Mock auth dependency
        app.dependency_overrides[get_current_user] = lambda: 1

        mock_storage = MagicMock()
        mock_storage.image_exists.return_value = True
        mock_storage.get_image_data.side_effect = ImageStorageError("Storage error")
        mock_storage.local_path = Path("/data/images")
        mock_storage_class.return_value = mock_storage

        try:
            with patch("src.api.routers.images.get_session") as mock_session_gen:
                mock_session_gen.return_value = iter([MagicMock()])
                response = client.get("/images/file/1/character/test.png")

            assert response.status_code == 500
        finally:
            app.dependency_overrides.clear()


class TestGetImageEndpoint:
    """Test /{image_id} endpoint."""

    @patch("src.api.routers.images.ImageService")
    def test_get_image_success(self, mock_service_class, client):
        """Test getting image by ID."""
        mock_service = MagicMock()
        mock_image = MagicMock()
        mock_image.image_id = 1
        mock_image.game_id = 1
        mock_image.image_type = "character"
        mock_image.entity_name = "Test"
        mock_image.entity_key = "player"
        mock_image.prompt_text = "prompt"
        mock_image.version = 1
        mock_image.created_at = None
        mock_service.get_image.return_value = mock_image
        mock_service.get_image_url.return_value = "/images/file/1/character/test.png"
        mock_service_class.return_value = mock_service

        with patch("src.api.routers.images.get_session") as mock_session_gen:
            mock_session_gen.return_value = iter([MagicMock()])
            response = client.get("/images/1")

        assert response.status_code == 200
        data = response.json()
        assert data["image_id"] == 1

    @patch("src.api.routers.images.ImageService")
    def test_get_image_not_found(self, mock_service_class, client):
        """Test getting non-existent image."""
        mock_service = MagicMock()
        mock_service.get_image.return_value = None
        mock_service_class.return_value = mock_service

        with patch("src.api.routers.images.get_session") as mock_session_gen:
            mock_session_gen.return_value = iter([MagicMock()])
            response = client.get("/images/999")

        assert response.status_code == 404


class TestDeleteImageEndpoint:
    """Test DELETE /{image_id} endpoint."""

    @patch("src.api.routers.images.ImageService")
    def test_delete_image_not_found(self, mock_service_class, client):
        """Test deleting non-existent image."""
        mock_service = MagicMock()
        mock_service.get_image.return_value = None
        mock_service_class.return_value = mock_service

        with patch("src.api.routers.images.get_session") as mock_session_gen:
            mock_session_gen.return_value = iter([MagicMock()])
            response = client.delete("/images/999")

        assert response.status_code == 404
