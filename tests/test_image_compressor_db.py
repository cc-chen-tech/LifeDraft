"""Image compression DB integration tests.

No mocks. Uses real PIL and temporary bytes.
"""

import io

import pytest
from PIL import Image

from src.utils.image_compressor import compress_image


def _create_test_image(mode="RGB", size=(100, 100), format="PNG"):
    """Create a test image in memory."""
    img = Image.new(mode, size, color=(255, 0, 0))
    buffer = io.BytesIO()
    img.save(buffer, format=format)
    return buffer.getvalue()


class TestImageCompressorContract:
    """Contract tests for image compression utility."""

    def test_compress_png_to_jpeg(self):
        """Compress PNG to JPEG should reduce size."""
        original = _create_test_image(mode="RGB", size=(2000, 2000), format="PNG")
        compressed = compress_image(original, max_dimension=1024, quality=85, output_format="JPEG")

        assert len(compressed) < len(original)

    def test_compress_resizes_large_image(self):
        """Image larger than max_dimension should be resized."""
        original = _create_test_image(mode="RGB", size=(2000, 2000), format="PNG")
        compressed = compress_image(original, max_dimension=500, quality=85, output_format="PNG")

        # Verify dimensions by loading the compressed image
        img = Image.open(io.BytesIO(compressed))
        assert max(img.size) <= 500

    def test_compress_preserves_small_image(self):
        """Image smaller than max_dimension should not be resized."""
        original = _create_test_image(mode="RGB", size=(100, 100), format="PNG")
        compressed = compress_image(original, max_dimension=1024, quality=85, output_format="PNG")

        img = Image.open(io.BytesIO(compressed))
        assert img.size == (100, 100)

    def test_compress_rgba_to_jpeg(self):
        """RGBA PNG should be converted to RGB for JPEG output."""
        original = _create_test_image(mode="RGBA", size=(100, 100), format="PNG")
        compressed = compress_image(original, max_dimension=1024, quality=85, output_format="JPEG")

        img = Image.open(io.BytesIO(compressed))
        assert img.mode == "RGB"

    def test_compress_palette_to_jpeg(self):
        """Palette mode (P) should be converted to RGB for JPEG."""
        img = Image.new("P", (100, 100), color=1)
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        original = buffer.getvalue()

        compressed = compress_image(original, max_dimension=1024, quality=85, output_format="JPEG")

        result = Image.open(io.BytesIO(compressed))
        assert result.mode == "RGB"

    def test_compress_maintains_aspect_ratio(self):
        """Resizing should maintain aspect ratio."""
        original = _create_test_image(mode="RGB", size=(1600, 800), format="PNG")
        compressed = compress_image(original, max_dimension=400, quality=85, output_format="PNG")

        img = Image.open(io.BytesIO(compressed))
        width, height = img.size
        assert width == 400
        assert height == 200

    def test_compress_invalid_data_raises(self):
        """Invalid image data should raise ValueError."""
        with pytest.raises(ValueError):
            compress_image(b"not an image")

    def test_compress_empty_data_raises(self):
        """Empty data should raise ValueError."""
        with pytest.raises(ValueError):
            compress_image(b"")

    def test_compress_png_output(self):
        """PNG output should work."""
        original = _create_test_image(mode="RGB", size=(500, 500), format="PNG")
        compressed = compress_image(original, max_dimension=1024, quality=85, output_format="PNG")

        img = Image.open(io.BytesIO(compressed))
        assert img.format == "PNG"

    def test_compress_jpeg_output(self):
        """JPEG output should work."""
        original = _create_test_image(mode="RGB", size=(500, 500), format="PNG")
        compressed = compress_image(original, max_dimension=1024, quality=85, output_format="JPEG")

        img = Image.open(io.BytesIO(compressed))
        assert img.format == "JPEG"

    def test_compress_quality_affects_size(self):
        """Lower quality should produce smaller files."""
        original = _create_test_image(mode="RGB", size=(1000, 1000), format="PNG")
        high_q = compress_image(original, max_dimension=1024, quality=95, output_format="JPEG")
        low_q = compress_image(original, max_dimension=1024, quality=30, output_format="JPEG")

        assert len(low_q) < len(high_q)
