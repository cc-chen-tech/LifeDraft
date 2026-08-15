"""Image compression utility.

Compresses images to reduce file size for faster loading on mobile devices.
"""

import io
import logging
from typing import Optional

from PIL import Image
from PIL.Image import Image as ImageType

logger = logging.getLogger(__name__)


def compress_image(
    image_data: bytes,
    max_dimension: int = 1024,
    quality: int = 85,
    output_format: str = "JPEG",
) -> bytes:
    """Compress an image to reduce file size.

    Args:
        image_data: Original image binary data.
        max_dimension: Maximum width or height in pixels.
            Images larger than this will be resized while maintaining aspect ratio.
        quality: JPEG compression quality (1-100). Higher = better quality but larger file.
        output_format: Output image format. "JPEG" or "PNG".

    Returns:
        Compressed image binary data.

    Raises:
        ValueError: If image_data is not a valid image.
    """
    opened: Optional[ImageType] = None
    try:
        img: ImageType = Image.open(io.BytesIO(image_data))
        opened = img
    except Exception as e:
        raise ValueError(f"Invalid image data: {e}")

    # Convert to RGB if necessary (e.g., RGBA -> RGB for JPEG)
    if output_format.upper() == "JPEG" and img.mode in ("RGBA", "P"):
        # Create white background for transparency
        background = Image.new("RGB", img.size, (255, 255, 255))
        if img.mode == "P":
            img = img.convert("RGBA")
        background.paste(img, mask=img.split()[-1] if img.mode == "RGBA" else None)
        img = background

    # Resize if larger than max_dimension
    width, height = img.size
    if max(width, height) > max_dimension:
        ratio = max_dimension / max(width, height)
        new_width = int(width * ratio)
        new_height = int(height * ratio)
        img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)  # type: ignore[assignment]
        logger.debug(f"Resized image from {width}x{height} to {new_width}x{new_height}")

    # Save to buffer with compression
    buffer = io.BytesIO()
    if output_format.upper() == "JPEG":
        img.save(buffer, format="JPEG", quality=quality, optimize=True)
    else:
        img.save(buffer, format="PNG", optimize=True)

    compressed_data = buffer.getvalue()

    original_size = len(image_data)
    compressed_size = len(compressed_data)
    reduction = (1 - compressed_size / original_size) * 100

    logger.info(
        f"Image compressed: {original_size} bytes -> {compressed_size} bytes "
        f"({reduction:.1f}% reduction)"
    )

    # P-修复：显式关闭原始打开的图像，避免句柄泄漏。
    if opened is not None:
        opened.close()
    return compressed_data
