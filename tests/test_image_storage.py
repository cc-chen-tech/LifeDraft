"""Tests for ImageStorageService."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.services.image_storage import ImageStorageError, ImageStorageService


class TestImageStorageServiceInit:
    """Test ImageStorageService initialization."""

    @patch("src.services.image_storage.settings")
    def test_init_default_settings(self, mock_settings):
        """Test initialization with default settings."""
        mock_settings.IMAGE_STORAGE_TYPE = "local"
        mock_settings.IMAGE_LOCAL_PATH = Path("/tmp/images")

        with patch.object(ImageStorageService, "_ensure_local_dir"):
            service = ImageStorageService()

        assert service.storage_type == "local"
        assert service.local_path == Path("/tmp/images")

    @patch("src.services.image_storage.settings")
    def test_init_custom_settings(self, mock_settings):
        """Test initialization with custom settings."""
        mock_settings.IMAGE_STORAGE_TYPE = "local"

        with patch.object(ImageStorageService, "_ensure_local_dir"):
            service = ImageStorageService(
                storage_type="oss", local_path=Path("/custom/path")
            )

        assert service.storage_type == "oss"
        assert service.local_path == Path("/custom/path")


class TestEnsureLocalDir:
    """Test _ensure_local_dir method."""

    @patch("src.services.image_storage.settings")
    def test_ensure_local_dir_success(self, mock_settings, tmp_path):
        """Test successful directory creation."""
        mock_settings.IMAGE_STORAGE_TYPE = "local"
        mock_settings.IMAGE_LOCAL_PATH = tmp_path

        # Directory should be created during init
        service = ImageStorageService()

        assert service.local_path == tmp_path


class TestGenerateFilename:
    """Test _generate_filename method."""

    @patch("src.services.image_storage.settings")
    def test_generate_filename(self, mock_settings):
        """Test filename generation."""
        mock_settings.IMAGE_STORAGE_TYPE = "local"
        mock_settings.IMAGE_LOCAL_PATH = Path("/tmp")

        with patch.object(ImageStorageService, "_ensure_local_dir"):
            service = ImageStorageService()

        filename = service._generate_filename(
            game_id=1,
            image_type="character",
            entity_name="Test Player",
            extension="png",
        )

        assert "1/character/" in filename
        assert filename.endswith(".png")
        # Space is preserved, not converted to underscore
        assert "Test Player" in filename

    @patch("src.services.image_storage.settings")
    def test_generate_filename_special_chars(self, mock_settings):
        """Test filename generation with special characters."""
        mock_settings.IMAGE_STORAGE_TYPE = "local"
        mock_settings.IMAGE_LOCAL_PATH = Path("/tmp")

        with patch.object(ImageStorageService, "_ensure_local_dir"):
            service = ImageStorageService()

        filename = service._generate_filename(
            game_id=1,
            image_type="character",
            entity_name="Test@Player#123!!!",
            extension="png",
        )

        # Special characters should be removed
        assert "@" not in filename
        assert "#" not in filename
        assert "!" not in filename


class TestSaveImage:
    """Test save_image method."""

    @patch("src.services.image_storage.settings")
    def test_save_image_local(self, mock_settings):
        """Test saving image locally."""
        mock_settings.IMAGE_STORAGE_TYPE = "local"
        mock_settings.IMAGE_LOCAL_PATH = Path("/tmp/images")

        with patch.object(ImageStorageService, "_ensure_local_dir"):
            with patch.object(ImageStorageService, "_save_local") as mock_save:
                mock_save.return_value = ("/tmp/images/test.png", "local")
                service = ImageStorageService()

                result = service.save_image(
                    image_data=b"test_data",
                    game_id=1,
                    image_type="character",
                    entity_name="Test",
                )

        assert result == ("/tmp/images/test.png", "local")

    @patch("src.services.image_storage.settings")
    def test_save_image_unsupported_type(self, mock_settings):
        """Test saving image with unsupported storage type."""
        mock_settings.IMAGE_STORAGE_TYPE = "invalid"
        mock_settings.IMAGE_LOCAL_PATH = Path("/tmp/images")

        with patch.object(ImageStorageService, "_ensure_local_dir"):
            service = ImageStorageService()

        with pytest.raises(ImageStorageError) as exc:
            service.save_image(
                image_data=b"test_data",
                game_id=1,
                image_type="character",
                entity_name="Test",
            )

        assert "不支持的存储类型" in str(exc.value)


class TestSaveLocal:
    """Test _save_local method."""

    @patch("src.services.image_storage.settings")
    def test_save_local_success(self, mock_settings, tmp_path):
        """Test successful local save."""
        mock_settings.IMAGE_STORAGE_TYPE = "local"
        mock_settings.IMAGE_LOCAL_PATH = tmp_path

        service = ImageStorageService()

        result = service._save_local(
            image_data=b"test_image_data", filename="1/character/test.png"
        )

        assert result[1] == "local"
        assert "1/character/test.png" in result[0]

    @patch("src.services.image_storage.settings")
    def test_save_local_creates_directory(self, mock_settings, tmp_path):
        """Test that save creates nested directories."""
        mock_settings.IMAGE_STORAGE_TYPE = "local"
        mock_settings.IMAGE_LOCAL_PATH = tmp_path

        service = ImageStorageService()

        # Save to a nested path that doesn't exist
        result = service._save_local(
            image_data=b"test_image_data", filename="999/character/nested/test.png"
        )

        assert result[1] == "local"
        assert (tmp_path / "999" / "character" / "nested").exists()


class TestImageExists:
    """Test image_exists method."""

    @patch("src.services.image_storage.settings")
    def test_image_exists_true(self, mock_settings, tmp_path):
        """Test image exists check - true."""
        mock_settings.IMAGE_STORAGE_TYPE = "local"
        mock_settings.IMAGE_LOCAL_PATH = tmp_path

        service = ImageStorageService()

        # Create a test file
        test_file = tmp_path / "test.png"
        test_file.write_bytes(b"test")

        assert service.image_exists(str(test_file), "local") is True

    @patch("src.services.image_storage.settings")
    def test_image_exists_false(self, mock_settings, tmp_path):
        """Test image exists check - false."""
        mock_settings.IMAGE_STORAGE_TYPE = "local"
        mock_settings.IMAGE_LOCAL_PATH = tmp_path

        service = ImageStorageService()

        assert service.image_exists(str(tmp_path / "nonexistent.png"), "local") is False


class TestGetImageData:
    """Test get_image_data method."""

    @patch("src.services.image_storage.settings")
    def test_get_image_data_success(self, mock_settings, tmp_path):
        """Test getting image data successfully."""
        mock_settings.IMAGE_STORAGE_TYPE = "local"
        mock_settings.IMAGE_LOCAL_PATH = tmp_path

        service = ImageStorageService()

        # Create a test file
        test_file = tmp_path / "test.png"
        test_file.write_bytes(b"test_image_data")

        result = service.get_image_data(str(test_file), "local")

        assert result == b"test_image_data"

    @patch("src.services.image_storage.settings")
    def test_get_image_data_not_found(self, mock_settings, tmp_path):
        """Test getting image data when file not found."""
        mock_settings.IMAGE_STORAGE_TYPE = "local"
        mock_settings.IMAGE_LOCAL_PATH = tmp_path

        service = ImageStorageService()

        # Should raise ImageStorageError for non-existent file
        with pytest.raises(ImageStorageError):
            service.get_image_data(str(tmp_path / "nonexistent.png"), "local")


class TestGetImageUrl:
    """Test get_image_url method."""

    @patch("src.services.image_storage.settings")
    def test_get_image_url_local(self, mock_settings):
        """Test getting local image URL."""
        mock_settings.IMAGE_STORAGE_TYPE = "local"
        mock_settings.IMAGE_LOCAL_PATH = Path("/data/images")

        with patch.object(ImageStorageService, "_ensure_local_dir"):
            service = ImageStorageService()

        url = service.get_image_url("/data/images/1/character/test.png", "local")

        assert "/images/file/" in url or "/api/images/file/" in url


class TestDeleteImage:
    """Test delete_image method."""

    @patch("src.services.image_storage.settings")
    def test_delete_image_local(self, mock_settings, tmp_path):
        """Test deleting local image."""
        mock_settings.IMAGE_STORAGE_TYPE = "local"
        mock_settings.IMAGE_LOCAL_PATH = tmp_path

        service = ImageStorageService()

        # Create a test file
        test_file = tmp_path / "test.png"
        test_file.write_bytes(b"test")

        result = service.delete_image(str(test_file), "local")

        assert result is True
        assert not test_file.exists()

    @patch("src.services.image_storage.settings")
    def test_delete_image_not_found(self, mock_settings, tmp_path):
        """Test deleting non-existent image."""
        mock_settings.IMAGE_STORAGE_TYPE = "local"
        mock_settings.IMAGE_LOCAL_PATH = tmp_path

        service = ImageStorageService()

        result = service.delete_image(str(tmp_path / "nonexistent.png"), "local")

        assert result is False
