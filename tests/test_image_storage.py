"""Tests for ImageStorageService."""

from pathlib import Path
from unittest.mock import patch

import pytest

from src.services.image_storage import ImageStorageError, ImageStorageService

pytestmark = [pytest.mark.unit]



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
            service = ImageStorageService(storage_type="oss", local_path=Path("/custom/path"))

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
                # ★ 现在返回相对路径
                mock_save.return_value = ("1/character/test.png", "local")
                service = ImageStorageService()

                result = service.save_image(
                    image_data=b"test_data",
                    game_id=1,
                    image_type="character",
                    entity_name="Test",
                )

        assert result == ("1/character/test.png", "local")

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
        """Test successful local save returns relative path."""
        mock_settings.IMAGE_STORAGE_TYPE = "local"
        mock_settings.IMAGE_LOCAL_PATH = tmp_path

        service = ImageStorageService()

        result = service._save_local(image_data=b"test_image_data", filename="1/character/test.png")

        # ★ 现在返回相对路径而非绝对路径
        assert result[0] == "1/character/test.png"
        assert result[1] == "local"
        # 验证文件确实写入到了正确位置
        assert (tmp_path / "1" / "character" / "test.png").exists()

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

        assert result[0] == "999/character/nested/test.png"
        assert result[1] == "local"
        assert (tmp_path / "999" / "character" / "nested").exists()


class TestImageExists:
    """Test image_exists method."""

    @patch("src.services.image_storage.settings")
    def test_image_exists_true_relative(self, mock_settings, tmp_path):
        """Test image exists check with relative path - true."""
        mock_settings.IMAGE_STORAGE_TYPE = "local"
        mock_settings.IMAGE_LOCAL_PATH = tmp_path

        service = ImageStorageService()

        # Create a test file
        (tmp_path / "1" / "character").mkdir(parents=True)
        test_file = tmp_path / "1" / "character" / "test.png"
        test_file.write_bytes(b"test")

        # ★ 使用相对路径检查
        assert service.image_exists("1/character/test.png", "local") is True

    @patch("src.services.image_storage.settings")
    def test_image_exists_false_relative(self, mock_settings, tmp_path):
        """Test image exists check with relative path - false."""
        mock_settings.IMAGE_STORAGE_TYPE = "local"
        mock_settings.IMAGE_LOCAL_PATH = tmp_path

        service = ImageStorageService()

        assert service.image_exists("1/character/nonexistent.png", "local") is False

    @patch("src.services.image_storage.settings")
    def test_image_exists_true_absolute_compat(self, mock_settings, tmp_path):
        """Test image exists check with absolute path (backward compat) - true."""
        mock_settings.IMAGE_STORAGE_TYPE = "local"
        mock_settings.IMAGE_LOCAL_PATH = tmp_path

        service = ImageStorageService()

        # Create a test file
        test_file = tmp_path / "test.png"
        test_file.write_bytes(b"test")

        # ★ 向后兼容：绝对路径仍然可用
        assert service.image_exists(str(test_file), "local") is True


class TestGetImageData:
    """Test get_image_data method."""

    @patch("src.services.image_storage.settings")
    def test_get_image_data_relative_path(self, mock_settings, tmp_path):
        """Test getting image data with relative path."""
        mock_settings.IMAGE_STORAGE_TYPE = "local"
        mock_settings.IMAGE_LOCAL_PATH = tmp_path

        service = ImageStorageService()

        # Create a test file
        (tmp_path / "1" / "character").mkdir(parents=True)
        test_file = tmp_path / "1" / "character" / "test.png"
        test_file.write_bytes(b"test_image_data")

        # ★ 使用相对路径读取
        result = service.get_image_data("1/character/test.png", "local")
        assert result == b"test_image_data"

    @patch("src.services.image_storage.settings")
    def test_get_image_data_absolute_compat(self, mock_settings, tmp_path):
        """Test getting image data with absolute path (backward compat)."""
        mock_settings.IMAGE_STORAGE_TYPE = "local"
        mock_settings.IMAGE_LOCAL_PATH = tmp_path

        service = ImageStorageService()

        # Create a test file
        test_file = tmp_path / "test.png"
        test_file.write_bytes(b"test_image_data")

        # ★ 向后兼容：绝对路径仍然可用
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
            service.get_image_data("1/character/nonexistent.png", "local")


class TestGetImageUrl:
    """Test get_image_url method."""

    @patch("src.services.image_storage.settings")
    def test_get_image_url_relative_path(self, mock_settings):
        """Test getting URL from relative path (new format)."""
        mock_settings.IMAGE_STORAGE_TYPE = "local"
        mock_settings.IMAGE_LOCAL_PATH = Path("/data/images")

        with patch.object(ImageStorageService, "_ensure_local_dir"):
            service = ImageStorageService()

        # ★ 新格式：相对路径直接拼接URL
        url = service.get_image_url("1/character/test.png", "local")
        assert url == "/api/images/file/1/character/test.png"

    @patch("src.services.image_storage.settings")
    def test_get_image_url_local(self, mock_settings):
        """Test getting local image URL."""
        mock_settings.IMAGE_STORAGE_TYPE = "local"
        mock_settings.IMAGE_LOCAL_PATH = Path("/data/images")

        with patch.object(ImageStorageService, "_ensure_local_dir"):
            service = ImageStorageService()

        url = service.get_image_url("/data/images/1/character/test.png", "local")

        assert "/images/file/" in url or "/api/images/file/" in url

    @patch("src.services.image_storage.settings")
    def test_get_image_url_prefix_match(self, mock_settings):
        """Test URL extraction when storage_path starts with current local_path."""
        mock_settings.IMAGE_STORAGE_TYPE = "local"
        mock_settings.IMAGE_LOCAL_PATH = Path("/Users/luicy/AI/story2/data/images")

        with patch.object(ImageStorageService, "_ensure_local_dir"):
            service = ImageStorageService()

        url = service.get_image_url(
            "/Users/luicy/AI/story2/data/images/296/character/test.png", "local"
        )

        assert url == "/api/images/file/296/character/test.png"

    @patch("src.services.image_storage.settings")
    def test_get_image_url_project_migration(self, mock_settings):
        """Test URL extraction after project directory migration via data/images/ marker."""
        mock_settings.IMAGE_STORAGE_TYPE = "local"
        # Current path is the new location
        mock_settings.IMAGE_LOCAL_PATH = Path("/Users/luicy/AI/story2/data/images")

        with patch.object(ImageStorageService, "_ensure_local_dir"):
            service = ImageStorageService()

        # storage_path is from the OLD location (before migration)
        url = service.get_image_url(
            "/Users/luicy/story2/data/images/296/character/xxx.png", "local"
        )

        assert url == "/api/images/file/296/character/xxx.png"

    @patch("src.services.image_storage.settings")
    def test_get_image_url_no_marker(self, mock_settings):
        """Test fallback when path has no data/images/ marker."""
        mock_settings.IMAGE_STORAGE_TYPE = "local"
        mock_settings.IMAGE_LOCAL_PATH = Path("/some/other/path")

        with patch.object(ImageStorageService, "_ensure_local_dir"):
            service = ImageStorageService()

        # Path without data/images/ and not starting with local_path
        url = service.get_image_url("/random/path/to/image.png", "local")

        # Falls back to using the full storage_path as relative_path (/ preserved by quote safe="/")
        assert url == "/api/images/file//random/path/to/image.png"

    @patch("src.services.image_storage.settings")
    def test_get_image_url_chinese_filename(self, mock_settings):
        """Test URL encoding for Chinese characters in filename."""
        mock_settings.IMAGE_STORAGE_TYPE = "local"
        mock_settings.IMAGE_LOCAL_PATH = Path("/data/images")

        with patch.object(ImageStorageService, "_ensure_local_dir"):
            service = ImageStorageService()

        # ★ 新格式：使用相对路径
        url = service.get_image_url("1/character/李逍遥_1.png", "local")

        # Chinese characters should be percent-encoded, slashes preserved
        assert "/api/images/file/1/character/" in url
        assert "%E6%9D%8E%E9%80%8D%E9%81%A5" in url  # 李逍遥 encoded
        assert url.endswith("_1.png")

    @patch("src.services.image_storage.settings")
    def test_get_image_url_multiple_markers(self, mock_settings):
        """Test extraction uses first data/images/ marker when multiple exist."""
        mock_settings.IMAGE_STORAGE_TYPE = "local"
        mock_settings.IMAGE_LOCAL_PATH = Path("/some/other/path")

        with patch.object(ImageStorageService, "_ensure_local_dir"):
            service = ImageStorageService()

        # Path with two data/images/ segments
        url = service.get_image_url(
            "/old/data/images/nested/data/images/1/character/test.png", "local"
        )

        # find() returns the first occurrence, so relative_path starts after the first marker
        assert url == "/api/images/file/nested/data/images/1/character/test.png"


class TestDeleteImage:
    """Test delete_image method."""

    @patch("src.services.image_storage.settings")
    def test_delete_image_relative_path(self, mock_settings, tmp_path):
        """Test deleting local image with relative path."""
        mock_settings.IMAGE_STORAGE_TYPE = "local"
        mock_settings.IMAGE_LOCAL_PATH = tmp_path

        service = ImageStorageService()

        # Create a test file
        (tmp_path / "1" / "character").mkdir(parents=True)
        test_file = tmp_path / "1" / "character" / "test.png"
        test_file.write_bytes(b"test")

        # ★ 使用相对路径删除
        result = service.delete_image("1/character/test.png", "local")

        assert result is True
        assert not test_file.exists()

    @patch("src.services.image_storage.settings")
    def test_delete_image_absolute_compat(self, mock_settings, tmp_path):
        """Test deleting local image with absolute path (backward compat)."""
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

        result = service.delete_image("1/character/nonexistent.png", "local")

        assert result is False


class TestGetFullPath:
    """Test get_full_path method."""

    @patch("src.services.image_storage.settings")
    def test_get_full_path_relative(self, mock_settings, tmp_path):
        """Test get_full_path with relative path."""
        mock_settings.IMAGE_STORAGE_TYPE = "local"
        mock_settings.IMAGE_LOCAL_PATH = tmp_path

        service = ImageStorageService()

        result = service.get_full_path("1/character/test.png")
        assert result == tmp_path / "1" / "character" / "test.png"

    @patch("src.services.image_storage.settings")
    def test_get_full_path_absolute(self, mock_settings, tmp_path):
        """Test get_full_path with absolute path (backward compat)."""
        mock_settings.IMAGE_STORAGE_TYPE = "local"
        mock_settings.IMAGE_LOCAL_PATH = tmp_path

        service = ImageStorageService()

        abs_path = "/Users/luicy/AI/story2/data/images/1/character/test.png"
        result = service.get_full_path(abs_path)
        assert result == Path(abs_path)
