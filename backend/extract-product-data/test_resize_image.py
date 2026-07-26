"""Unit tests for resize_image function."""
import unittest
from io import BytesIO
from unittest.mock import patch

from PIL import Image

# Patch boto3 client before importing handler to avoid NoRegionError
with patch("boto3.client"):
    from handler import resize_image


class TestResizeImage(unittest.TestCase):
    """Tests for the resize_image helper."""

    def _make_image(self, width: int, height: int, fmt: str = "JPEG") -> bytes:
        img = Image.new("RGB", (width, height), color="red")
        buf = BytesIO()
        img.save(buf, format=fmt)
        return buf.getvalue()

    def test_large_landscape_image_resized(self):
        """A 2048x1536 image should become 1024x768."""
        original = self._make_image(2048, 1536)
        resized = resize_image(original, "jpeg")
        img = Image.open(BytesIO(resized))
        self.assertEqual(img.size, (1024, 768))

    def test_large_portrait_image_resized(self):
        """A 1536x2048 image should become 768x1024."""
        original = self._make_image(1536, 2048)
        resized = resize_image(original, "jpeg")
        img = Image.open(BytesIO(resized))
        self.assertEqual(img.size, (768, 1024))

    def test_small_image_unchanged(self):
        """An image within bounds returns original bytes (no re-encoding)."""
        original = self._make_image(800, 600)
        result = resize_image(original, "jpeg")
        self.assertIs(result, original)

    def test_exact_boundary_unchanged(self):
        """An image exactly at 1024px longest side stays unchanged."""
        original = self._make_image(1024, 768)
        result = resize_image(original, "jpeg")
        self.assertIs(result, original)

    def test_png_format_preserved(self):
        """PNG images are saved back as PNG."""
        original = self._make_image(2000, 1000, fmt="PNG")
        resized = resize_image(original, "png")
        img = Image.open(BytesIO(resized))
        self.assertEqual(img.format, "PNG")
        self.assertEqual(img.size, (1024, 512))

    def test_corrupted_image_returns_original(self):
        """If Pillow can't open the image, return original bytes."""
        garbage = b"not an image at all"
        result = resize_image(garbage, "jpeg")
        self.assertEqual(result, garbage)


if __name__ == "__main__":
    unittest.main()
