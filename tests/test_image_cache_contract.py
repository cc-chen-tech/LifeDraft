"""Contract tests for image file cache headers."""

import os
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

os.environ.setdefault("JWT_SECRET", "test-secret-for-image-cache-contract")

from src.api.deps import create_token  # noqa: E402
from src.api.main import app  # noqa: E402

client = TestClient(app)

# Create a valid test token for authentication
TEST_USER_ID = 1
TEST_AUTH_TOKEN = create_token(TEST_USER_ID)
TEST_AUTH_HEADERS = {"Authorization": f"Bearer {TEST_AUTH_TOKEN}"}


class TestImageCacheHeaders:
    """Test that image file responses have proper cache headers."""

    @patch("src.api.routers.images.ImageStorageService")
    def test_image_file_response_has_cache_control(self, mock_storage_class):
        """Image file response must include Cache-Control header."""
        mock_service = MagicMock()
        mock_service.local_path = MagicMock()
        mock_service.local_path.resolve.return_value = MagicMock()
        mock_storage_class.return_value = mock_service

        # Mock image_exists to return True
        mock_service.image_exists.return_value = True

        # Mock get_image_data to return test image data
        mock_service.get_image_data.return_value = b"fake_image_data"

        # Mock path resolution
        with patch("pathlib.Path.resolve"):
            with patch("pathlib.Path.is_relative_to") as mock_relative:
                mock_relative.return_value = True

                response = client.get(
                    "/api/images/file/1/character/test.png",
                    headers=TEST_AUTH_HEADERS,
                )

        assert "cache-control" in response.headers, (
            f"Response missing Cache-Control header. Headers: {dict(response.headers)}"
        )

    @patch("src.api.routers.images.ImageStorageService")
    def test_image_file_cache_control_value(self, mock_storage_class):
        """Cache-Control should allow public caching with 1 hour max-age."""
        mock_service = MagicMock()
        mock_service.local_path = MagicMock()
        mock_service.local_path.resolve.return_value = MagicMock()
        mock_storage_class.return_value = mock_service

        mock_service.image_exists.return_value = True
        mock_service.get_image_data.return_value = b"fake_image_data"

        with patch("pathlib.Path.resolve"):
            with patch("pathlib.Path.is_relative_to") as mock_relative:
                mock_relative.return_value = True

                response = client.get(
                    "/api/images/file/1/character/test.png",
                    headers=TEST_AUTH_HEADERS,
                )

        cache_control = response.headers.get("cache-control", "")
        assert "public" in cache_control, (
            f"Cache-Control should allow public caching: {cache_control}"
        )
        assert "max-age=3600" in cache_control, (
            f"Cache-Control should have 1 hour max-age: {cache_control}"
        )

    @patch("src.api.routers.images.ImageStorageService")
    def test_image_file_no_pragma_no_cache(self, mock_storage_class):
        """Image file response should not have Pragma: no-cache."""
        mock_service = MagicMock()
        mock_service.local_path = MagicMock()
        mock_service.local_path.resolve.return_value = MagicMock()
        mock_storage_class.return_value = mock_service

        mock_service.image_exists.return_value = True
        mock_service.get_image_data.return_value = b"fake_image_data"

        with patch("pathlib.Path.resolve"):
            with patch("pathlib.Path.is_relative_to") as mock_relative:
                mock_relative.return_value = True

                response = client.get(
                    "/api/images/file/1/character/test.png",
                    headers=TEST_AUTH_HEADERS,
                )

        pragma = response.headers.get("pragma", "")
        assert "no-cache" not in pragma.lower(), (
            f"Pragma should not contain no-cache: {pragma}"
        )

    @patch("src.api.routers.images.ImageStorageService")
    def test_image_file_no_expires_zero(self, mock_storage_class):
        """Image file response should not have Expires: 0."""
        mock_service = MagicMock()
        mock_service.local_path = MagicMock()
        mock_service.local_path.resolve.return_value = MagicMock()
        mock_storage_class.return_value = mock_service

        mock_service.image_exists.return_value = True
        mock_service.get_image_data.return_value = b"fake_image_data"

        with patch("pathlib.Path.resolve"):
            with patch("pathlib.Path.is_relative_to") as mock_relative:
                mock_relative.return_value = True

                response = client.get(
                    "/api/images/file/1/character/test.png",
                    headers=TEST_AUTH_HEADERS,
                )

        expires = response.headers.get("expires", "")
        assert expires != "0", (
            f"Expires should not be 0: {expires}"
        )
