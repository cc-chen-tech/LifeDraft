"""Tests for images router - simplified version."""

from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

# API tests - image endpoints
pytestmark = pytest.mark.api

from src.api.routers.images import verify_game_ownership  # noqa: E402
from src.api.routers.images import verify_image_ownership
from src.services.image_service import ImageContentError  # noqa: E402
from src.services.image_storage import ImageStorageError  # noqa: E402


@pytest.fixture
def app():
    """Create test app with images router."""
    from src.api.routers.images import router as current_router

    app = FastAPI()
    app.include_router(current_router, prefix="/images")
    return app


@pytest.fixture
def client(app):
    """Create test client."""
    return TestClient(app)


def _current_user_dependency():
    from src.api.routers import images

    return images.get_current_user


def _current_user_optional_dependency():
    from src.api.routers import images

    return images.get_current_user_optional


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
            verify_image_ownership(mock_db, 1, 1)
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
        app.dependency_overrides[_current_user_dependency()] = lambda: 1

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
        app.dependency_overrides[_current_user_dependency()] = lambda: 1

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


# ==================== Path Traversal Security Tests ====================


class TestPathTraversalSecurity:
    """Test path traversal attack prevention."""

    @patch("src.api.routers.images.ImageStorageService")
    def test_path_traversal_rejected_dot_dot(self, mock_storage_class, app, client):
        """Test that path traversal with .. is rejected."""
        from pathlib import Path

        app.dependency_overrides[_current_user_dependency()] = lambda: 1

        mock_storage = MagicMock()
        mock_storage.image_exists.return_value = False
        mock_storage.local_path = Path("/data/images")
        mock_storage_class.return_value = mock_storage

        try:
            with patch("src.api.routers.images.get_session") as mock_session_gen:
                mock_session_gen.return_value = iter([MagicMock()])
                response = client.get("/images/file/1/character/../../../etc/passwd")

            # Should return 400 or 404, not actual file content
            assert response.status_code in (400, 404)
        finally:
            app.dependency_overrides.clear()

    @patch("src.api.routers.images.ImageStorageService")
    def test_path_traversal_rejected_encoded(self, mock_storage_class, app, client):
        """Test that URL-encoded path traversal is rejected."""
        from pathlib import Path

        app.dependency_overrides[_current_user_dependency()] = lambda: 1

        mock_storage = MagicMock()
        mock_storage.image_exists.return_value = False
        mock_storage.local_path = Path("/data/images")
        mock_storage_class.return_value = mock_storage

        try:
            with patch("src.api.routers.images.get_session") as mock_session_gen:
                mock_session_gen.return_value = iter([MagicMock()])
                response = client.get("/images/file/1/character/%2e%2e%2fetc%2fpasswd")

            assert response.status_code in (400, 404)
        finally:
            app.dependency_overrides.clear()


# ==================== POST Generate Image Tests ====================


class TestGenerateImageEndpoint:
    """Test POST /generate endpoint."""

    @patch("src.api.routers.images.ImageService")
    def test_generate_image_unauthorized(self, mock_service_class, app, client):
        """Test that unauthenticated requests return 401."""

        # Don't override auth - should be None
        with patch("src.api.routers.images.get_session") as mock_session_gen:
            mock_session_gen.return_value = iter([MagicMock()])
            response = client.post(
                "/images/generate",
                json={
                    "game_id": 1,
                    "image_type": "character",
                    "entity_name": "Test",
                    "description": "Test description",
                },
            )

        assert response.status_code == 401

    @patch("src.api.routers.images.ImageService")
    @patch("src.api.routers.images.verify_game_ownership")
    def test_generate_image_success(self, mock_verify, mock_service_class, app, client):
        """Test successful image generation."""
        mock_user = MagicMock()
        mock_user.user_id = 1
        app.dependency_overrides[_current_user_optional_dependency()] = (
            lambda: mock_user.user_id
        )

        mock_service = MagicMock()
        mock_image = MagicMock()
        mock_image.image_id = 1
        mock_image.game_id = 1
        mock_image.image_type = "character"
        mock_image.entity_name = "Test"
        mock_image.entity_key = "player"
        mock_image.prompt_text = "test prompt"
        mock_image.version = 1
        mock_image.created_at = None
        mock_service.generate_character_image.return_value = [mock_image]
        mock_service.get_image_url.return_value = "/images/file/1/character/test.png"
        mock_service_class.return_value = mock_service

        mock_verify.return_value = MagicMock()

        try:
            with patch("src.api.routers.images.get_session") as mock_session_gen:
                mock_session_gen.return_value = iter([MagicMock()])
                response = client.post(
                    "/images/generate",
                    json={
                        "game_id": 1,
                        "image_type": "character",
                        "entity_name": "Test",
                        "description": "Test description",
                    },
                )

            assert response.status_code == 200
            data = response.json()
            assert "images" in data
            assert data["total"] >= 0
        finally:
            app.dependency_overrides.clear()

    @patch("src.api.routers.images.ImageService")
    @patch("src.api.routers.images.verify_game_ownership")
    def test_generate_image_invalid_type(
        self, mock_verify, mock_service_class, app, client
    ):
        """Test generating image with invalid type."""
        mock_user = MagicMock()
        mock_user.user_id = 1
        app.dependency_overrides[_current_user_optional_dependency()] = (
            lambda: mock_user.user_id
        )

        mock_verify.return_value = MagicMock()

        try:
            with patch("src.api.routers.images.get_session") as mock_session_gen:
                mock_session_gen.return_value = iter([MagicMock()])
                response = client.post(
                    "/images/generate",
                    json={
                        "game_id": 1,
                        "image_type": "invalid_type",
                        "entity_name": "Test",
                        "description": "Test",
                    },
                )

            # Invalid type should return 400 or 500 (depending on error handling)
            assert response.status_code in (400, 500)
        finally:
            app.dependency_overrides.clear()

    @patch("src.api.routers.images.ImageService")
    @patch("src.api.routers.images.verify_game_ownership")
    def test_generate_image_content_error(
        self, mock_verify, mock_service_class, app, client
    ):
        """Test handling content moderation error."""
        mock_user = MagicMock()
        mock_user.user_id = 1
        app.dependency_overrides[_current_user_optional_dependency()] = (
            lambda: mock_user.user_id
        )

        mock_service = MagicMock()
        mock_service.generate_character_image.side_effect = ImageContentError(
            "Content moderation failed"
        )
        mock_service_class.return_value = mock_service

        mock_verify.return_value = MagicMock()

        try:
            with patch("src.api.routers.images.get_session") as mock_session_gen:
                mock_session_gen.return_value = iter([MagicMock()])
                response = client.post(
                    "/images/generate",
                    json={
                        "game_id": 1,
                        "image_type": "character",
                        "entity_name": "Test",
                        "description": "Test",
                    },
                )

            assert response.status_code == 400
            assert "敏感内容" in response.json()["detail"]
        finally:
            app.dependency_overrides.clear()


# ==================== Image File Not Found Tests ====================


class TestImageFileNotFound:
    """Test image file not found scenarios."""

    @patch("src.api.routers.images.ImageStorageService")
    def test_get_image_file_not_exists(self, mock_storage_class, app, client):
        """Test getting non-existent image file returns 404 or 500."""
        from pathlib import Path

        app.dependency_overrides[_current_user_dependency()] = lambda: 1

        mock_storage = MagicMock()
        mock_storage.image_exists.return_value = False
        mock_storage.local_path = Path("/data/images")
        mock_storage_class.return_value = mock_storage

        try:
            with patch("src.api.routers.images.get_session") as mock_session_gen:
                mock_session_gen.return_value = iter([MagicMock()])
                response = client.get("/images/file/1/character/nonexistent.png")

            # Not found should return 404 or 500 (depending on error handling)
            assert response.status_code in (404, 500)
        finally:
            app.dependency_overrides.clear()


# ==================== Invalid Parameter Tests ====================


class TestInvalidParameters:
    """Test invalid parameter handling."""

    def test_get_image_invalid_id(self, client):
        """Test getting image with invalid ID format."""
        response = client.get("/images/invalid")
        assert response.status_code == 422

    def test_generate_image_missing_fields(self, client):
        """Test generating image with missing required fields."""
        response = client.post("/images/generate", json={})
        assert response.status_code == 422


# ==================== Round Scene Image Tests ====================


class TestRoundSceneImage:
    """Test round scene image endpoint with week parameter."""

    def test_get_round_scene_image_requires_week(self, client):
        """Test that week parameter is required to prevent returning wrong week images.

        This is a regression test for the issue where not passing week parameter
        would return images from other weeks with the same round number.
        """
        # Without week parameter - should fail with 422 validation error
        # because week is now a required parameter
        response = client.get("/images/scene/1/0")
        assert response.status_code == 422, (
            "Week parameter should be required to prevent returning wrong week images. "
            "This prevents the bug where images from different weeks but same round were returned."
        )
