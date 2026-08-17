"""Tests for image compression utility."""

import io

import pytest
from PIL import Image

pytestmark = [pytest.mark.unit]



class TestImageCompressor:
    """Test image compression functionality."""

    def _create_test_image(
        self,
        width: int = 2000,
        height: int = 2000,
        mode: str = "RGB",
        format: str = "PNG",
    ) -> bytes:
        """Create a test image in memory."""
        img = Image.new(mode, (width, height), color=(100, 150, 200))
        buffer = io.BytesIO()
        img.save(buffer, format=format)
        return buffer.getvalue()

    def test_compress_png_reduces_size(self):
        """PNG compression should reduce file size by >50%."""
        from src.utils.image_compressor import compress_image

        original_data = self._create_test_image(2000, 2000, "RGB", "PNG")
        original_size = len(original_data)

        compressed = compress_image(original_data)
        compressed_size = len(compressed)

        assert compressed_size < original_size * 0.5, (
            f"Compression did not reduce size enough: " f"{original_size} -> {compressed_size}"
        )

    def test_compress_jpeg_reduces_size(self):
        """JPEG compression should reduce file size by >50%."""
        from src.utils.image_compressor import compress_image

        original_data = self._create_test_image(2000, 2000, "RGB", "JPEG")
        original_size = len(original_data)

        compressed = compress_image(original_data)
        compressed_size = len(compressed)

        assert compressed_size < original_size * 0.5, (
            f"Compression did not reduce size enough: " f"{original_size} -> {compressed_size}"
        )

    def test_compress_max_dimension(self):
        """Large images should be resized to max_dimension."""
        from src.utils.image_compressor import compress_image

        original_data = self._create_test_image(3000, 2000, "RGB", "PNG")
        compressed = compress_image(original_data, max_dimension=1024)

        # Verify the compressed image dimensions
        img = Image.open(io.BytesIO(compressed))
        assert max(img.size) <= 1024, f"Image not resized correctly: {img.size}"

    def test_compress_small_image_unchanged(self):
        """Small images (< max_dimension) should keep original dimensions."""
        from src.utils.image_compressor import compress_image

        original_data = self._create_test_image(500, 500, "RGB", "PNG")
        compressed = compress_image(original_data, max_dimension=1024)

        img = Image.open(io.BytesIO(compressed))
        assert img.size == (500, 500), f"Small image should not be resized: {img.size}"

    def test_compress_invalid_data_raises(self):
        """Invalid image data should raise ValueError."""
        from src.utils.image_compressor import compress_image

        with pytest.raises(ValueError):
            compress_image(b"not an image")

    def test_compress_quality_setting(self):
        """Quality parameter should affect output size."""
        from src.utils.image_compressor import compress_image

        original_data = self._create_test_image(2000, 2000, "RGB", "PNG")

        low_quality = compress_image(original_data, quality=30)
        high_quality = compress_image(original_data, quality=95)

        assert len(low_quality) < len(high_quality), "Lower quality should produce smaller file"

    def test_compress_returns_bytes(self):
        """compress_image should return bytes."""
        from src.utils.image_compressor import compress_image

        original_data = self._create_test_image(1000, 1000, "RGB", "PNG")
        compressed = compress_image(original_data)

        assert isinstance(compressed, bytes)

    def test_compress_preserves_image_content(self):
        """Compressed image should still be a valid image."""
        from src.utils.image_compressor import compress_image

        original_data = self._create_test_image(1000, 1000, "RGB", "PNG")
        compressed = compress_image(original_data)

        # Should be able to open it as an image
        img = Image.open(io.BytesIO(compressed))
        assert img.mode in ("RGB", "RGBA", "L")
        assert img.size[0] > 0 and img.size[1] > 0
