"""Contract tests for image file cache headers."""

from unittest.mock import MagicMock, patch

import pytest

from fastapi.testclient import TestClient

from src.api.deps import create_token
from src.api.main import app
from src.api.routers.images import get_session

client = TestClient(app)


@pytest.fixture(autouse=True)
def _mock_db_session():
    """让文件端点独立于真实文件 DB 状态（此前依赖其他测试先建表/造 game，属顺序污染）。"""
    mock_db = MagicMock()
    mock_game = MagicMock()
    mock_game.user_id = 1
    mock_db.query.return_value.filter.return_value.first.return_value = mock_game

    def override_get_session():
        yield mock_db

    app.dependency_overrides[get_session] = override_get_session
    yield
    app.dependency_overrides.pop(get_session, None)

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

        assert (
            "cache-control" in response.headers
        ), f"Response missing Cache-Control header. Headers: {dict(response.headers)}"

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
        assert (
            "public" in cache_control
        ), f"Cache-Control should allow public caching: {cache_control}"
        assert (
            "max-age=3600" in cache_control
        ), f"Cache-Control should have 1 hour max-age: {cache_control}"

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
        assert "no-cache" not in pragma.lower(), f"Pragma should not contain no-cache: {pragma}"

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
        assert expires != "0", f"Expires should not be 0: {expires}"
