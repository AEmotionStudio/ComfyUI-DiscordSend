"""Tests for shared/media/format_utils.py"""

import sys
import os
import unittest
from unittest.mock import MagicMock
import tempfile

# Mock dependencies before importing project modules
sys.modules["torch"] = MagicMock()
sys.modules["numpy"] = MagicMock()
sys.modules["cv2"] = MagicMock()

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.media.format_utils import (
    parse_format_string,
    normalize_video_extension,
    get_mime_type,
    validate_video_for_discord,
    is_animated_format,
    supports_alpha,
)


class TestParseFormatString(unittest.TestCase):
    """Test parse_format_string function."""

    def test_video_h264_mp4(self):
        """Test parsing video/h264-mp4 format."""
        fmt_type, fmt_ext = parse_format_string("video/h264-mp4")
        self.assertEqual(fmt_type, "video")
        self.assertEqual(fmt_ext, "h264-mp4")

    def test_image_gif(self):
        """Test parsing image/gif format."""
        fmt_type, fmt_ext = parse_format_string("image/gif")
        self.assertEqual(fmt_type, "image")
        self.assertEqual(fmt_ext, "gif")

    def test_simple_format(self):
        """Test parsing simple format string without slash."""
        fmt_type, fmt_ext = parse_format_string("mp4")
        self.assertEqual(fmt_type, "video")
        self.assertEqual(fmt_ext, "mp4")


class TestNormalizeVideoExtension(unittest.TestCase):
    """Test normalize_video_extension function."""

    def test_h264_mp4(self):
        """Test normalizing h264-mp4 to mp4."""
        self.assertEqual(normalize_video_extension("video/h264-mp4"), "mp4")

    def test_h265_mp4(self):
        """Test normalizing h265-mp4 to mp4."""
        self.assertEqual(normalize_video_extension("video/h265-mp4"), "mp4")

    def test_vp9_webm(self):
        """Test normalizing vp9-webm to webm."""
        self.assertEqual(normalize_video_extension("video/vp9-webm"), "webm")

    def test_prores(self):
        """Test normalizing prores to mov."""
        self.assertEqual(normalize_video_extension("video/prores"), "mov")

    def test_gif_passthrough(self):
        """Test gif format passes through unchanged."""
        self.assertEqual(normalize_video_extension("image/gif"), "gif")

    def test_unknown_passthrough(self):
        """Test unknown format passes through unchanged."""
        self.assertEqual(normalize_video_extension("video/custom"), "custom")


class TestGetMimeType(unittest.TestCase):
    """Test get_mime_type function."""

    def test_mp4(self):
        """Test MIME type for mp4."""
        self.assertEqual(get_mime_type("mp4"), "video/mp4")

    def test_webm(self):
        """Test MIME type for webm."""
        self.assertEqual(get_mime_type("webm"), "video/webm")

    def test_gif(self):
        """Test MIME type for gif."""
        self.assertEqual(get_mime_type("gif"), "image/gif")

    def test_mov(self):
        """Test MIME type for mov."""
        self.assertEqual(get_mime_type("mov"), "video/quicktime")

    def test_case_insensitive(self):
        """Test MIME type lookup is case insensitive."""
        self.assertEqual(get_mime_type("MP4"), "video/mp4")

    def test_unknown_format(self):
        """Test unknown format returns octet-stream."""
        self.assertEqual(get_mime_type("xyz"), "application/octet-stream")


class TestValidateVideoForDiscord(unittest.TestCase):
    """Test validate_video_for_discord function."""

    def test_nonexistent_file(self):
        """Test validation of nonexistent file."""
        is_valid, msg = validate_video_for_discord("/nonexistent/file.mp4")
        self.assertFalse(is_valid)
        self.assertIn("does not exist", msg)

    def test_empty_file(self):
        """Test validation of empty file."""
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
            temp_path = f.name
        try:
            is_valid, msg = validate_video_for_discord(temp_path)
            self.assertFalse(is_valid)
            self.assertIn("empty", msg)
        finally:
            os.unlink(temp_path)

    def test_small_file(self):
        """Test validation of suspiciously small file."""
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
            f.write(b"x" * 100)  # 100 bytes
            temp_path = f.name
        try:
            is_valid, msg = validate_video_for_discord(temp_path)
            self.assertFalse(is_valid)
            self.assertIn("small", msg)
        finally:
            os.unlink(temp_path)

    def test_valid_mp4(self):
        """Test validation of valid mp4 file."""
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
            f.write(b"x" * 10000)  # 10KB
            temp_path = f.name
        try:
            is_valid, msg = validate_video_for_discord(temp_path)
            self.assertTrue(is_valid)
            self.assertEqual(msg, "Valid")
        finally:
            os.unlink(temp_path)

    def test_valid_webm(self):
        """Test validation of valid webm file."""
        with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as f:
            f.write(b"x" * 10000)
            temp_path = f.name
        try:
            is_valid, msg = validate_video_for_discord(temp_path)
            self.assertTrue(is_valid)
        finally:
            os.unlink(temp_path)

    def test_mov_needs_conversion(self):
        """Test that MOV files are flagged for conversion."""
        with tempfile.NamedTemporaryFile(suffix=".mov", delete=False) as f:
            f.write(b"x" * 10000)
            temp_path = f.name
        try:
            is_valid, msg = validate_video_for_discord(temp_path)
            self.assertFalse(is_valid)
            self.assertIn("conversion", msg)
        finally:
            os.unlink(temp_path)


class TestIsAnimatedFormat(unittest.TestCase):
    """Test is_animated_format function."""

    def test_animated_formats(self):
        """Test formats that support animation."""
        animated = ["gif", "webp", "mp4", "webm", "mov", "avi", "mkv", "apng"]
        for fmt in animated:
            self.assertTrue(is_animated_format(fmt), f"{fmt} should be animated")

    def test_static_formats(self):
        """Test formats that don't support animation."""
        static = ["png", "jpg", "jpeg", "bmp"]
        for fmt in static:
            self.assertFalse(is_animated_format(fmt), f"{fmt} should not be animated")

    def test_case_insensitive(self):
        """Test case insensitivity."""
        self.assertTrue(is_animated_format("GIF"))
        self.assertTrue(is_animated_format("Mp4"))


class TestSupportsAlpha(unittest.TestCase):
    """Test supports_alpha function."""

    def test_alpha_formats(self):
        """Test formats that support alpha channel."""
        alpha = ["webm", "gif", "webp", "png", "apng", "mov"]
        for fmt in alpha:
            self.assertTrue(supports_alpha(fmt), f"{fmt} should support alpha")

    def test_no_alpha_formats(self):
        """Test formats that don't support alpha."""
        no_alpha = ["mp4", "jpg", "jpeg", "avi"]
        for fmt in no_alpha:
            self.assertFalse(supports_alpha(fmt), f"{fmt} should not support alpha")

    def test_case_insensitive(self):
        """Test case insensitivity."""
        self.assertTrue(supports_alpha("PNG"))
        self.assertTrue(supports_alpha("WebM"))


if __name__ == "__main__":
    unittest.main()
