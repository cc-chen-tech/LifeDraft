"""DB integration tests for image compression."""

import io
import os

from PIL import Image

from src.services.image_storage import ImageStorageService


class TestImageCompressionDB:
    """Test image compression with real file system operations."""

    def _create_large_test_image(self) -> bytes:
        """Create a large test image (~2MB)."""
        img = Image.new("RGB", (2000, 2000), color=(100, 150, 200))
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        return buffer.getvalue()

    def test_save_compressed_image_reduces_size(self, tmp_path):
        """Saving compressed image should reduce file size by >50%."""
        service = ImageStorageService(
            storage_type="local",
            local_path=tmp_path,
        )

        original_data = self._create_large_test_image()
        original_size = len(original_data)

        # Save with compression enabled
        storage_path, storage_type = service.save_image(
            image_data=original_data,
            game_id=1,
            image_type="character",
            entity_name="TestHero",
            extension="png",
        )

        # Read the saved file
        full_path = service.get_full_path(storage_path)
        saved_size = os.path.getsize(full_path)

        assert saved_size < original_size * 0.5, (
            f"Compressed image not small enough: "
            f"original={original_size}, saved={saved_size}"
        )

    def test_save_compressed_image_is_valid(self, tmp_path):
        """Saved compressed image should be a valid image file."""
        service = ImageStorageService(
            storage_type="local",
            local_path=tmp_path,
        )

        original_data = self._create_large_test_image()

        storage_path, _ = service.save_image(
            image_data=original_data,
            game_id=1,
            image_type="character",
            entity_name="TestHero",
            extension="png",
        )

        # Read back and verify it's a valid image
        image_data = service.get_image_data(storage_path)
        img = Image.open(io.BytesIO(image_data))

        assert img.size[0] > 0 and img.size[1] > 0
        assert img.mode in ("RGB", "RGBA", "L")

    def test_save_compressed_image_dimensions(self, tmp_path):
        """Large images should be resized to max 1024px."""
        service = ImageStorageService(
            storage_type="local",
            local_path=tmp_path,
        )

        original_data = self._create_large_test_image()

        storage_path, _ = service.save_image(
            image_data=original_data,
            game_id=1,
            image_type="character",
            entity_name="TestHero",
            extension="png",
        )

        image_data = service.get_image_data(storage_path)
        img = Image.open(io.BytesIO(image_data))

        assert (
            max(img.size) <= 1024
        ), f"Image should be resized to max 1024px: {img.size}"

    def test_save_small_image_untouched(self, tmp_path):
        """Small images should not be resized."""
        service = ImageStorageService(
            storage_type="local",
            local_path=tmp_path,
        )

        # Create a small image
        img = Image.new("RGB", (500, 500), color=(100, 150, 200))
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        small_data = buffer.getvalue()

        storage_path, _ = service.save_image(
            image_data=small_data,
            game_id=1,
            image_type="character",
            entity_name="TestHero",
            extension="png",
        )

        image_data = service.get_image_data(storage_path)
        saved_img = Image.open(io.BytesIO(image_data))

        assert saved_img.size == (
            500,
            500,
        ), f"Small image should not be resized: {saved_img.size}"

    def test_image_url_after_compression(self, tmp_path):
        """Compressed image should have a valid URL."""
        service = ImageStorageService(
            storage_type="local",
            local_path=tmp_path,
        )

        original_data = self._create_large_test_image()

        storage_path, storage_type = service.save_image(
            image_data=original_data,
            game_id=1,
            image_type="character",
            entity_name="TestHero",
            extension="png",
        )

        url = service.get_image_url(storage_path, storage_type)

        assert url.startswith("/api/images/file/"), f"URL format incorrect: {url}"
        assert (
            "TestHero" in url or "1/character" in url
        ), f"URL should contain path info: {url}"
