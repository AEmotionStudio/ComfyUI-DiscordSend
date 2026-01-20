"""Tests for shared/path_utils.py"""

import sys
import os
import unittest
from unittest.mock import patch, MagicMock
import tempfile
import shutil

# Mock dependencies before importing project modules
sys.modules["torch"] = MagicMock()
sys.modules["numpy"] = MagicMock()
sys.modules["cv2"] = MagicMock()

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.path_utils import (
    get_output_directory,
    ensure_directory_exists,
    get_unique_filepath,
)


class TestGetOutputDirectory(unittest.TestCase):
    """Test get_output_directory function."""

    def setUp(self):
        """Create temporary directories for testing."""
        self.test_dir = tempfile.mkdtemp()
        self.output_dir = os.path.join(self.test_dir, "output")
        self.temp_dir = os.path.join(self.test_dir, "temp")
        os.makedirs(self.output_dir)
        os.makedirs(self.temp_dir)

    def tearDown(self):
        """Clean up temporary directories."""
        shutil.rmtree(self.test_dir)

    def test_save_output_true(self):
        """Test output directory when saving is enabled."""
        result = get_output_directory(
            save_output=True,
            comfy_output_dir=self.output_dir,
            temp_dir=self.temp_dir,
        )
        expected = os.path.join(self.output_dir, "discord_output")
        self.assertEqual(result, expected)
        self.assertTrue(os.path.exists(result))

    def test_save_output_false(self):
        """Test temp directory when saving is disabled."""
        result = get_output_directory(
            save_output=False,
            comfy_output_dir=self.output_dir,
            temp_dir=self.temp_dir,
        )
        self.assertEqual(result, self.temp_dir)

    def test_custom_subfolder(self):
        """Test with custom subfolder name."""
        result = get_output_directory(
            save_output=True,
            comfy_output_dir=self.output_dir,
            temp_dir=self.temp_dir,
            subfolder="custom_folder",
        )
        expected = os.path.join(self.output_dir, "custom_folder")
        self.assertEqual(result, expected)
        self.assertTrue(os.path.exists(result))


class TestEnsureDirectoryExists(unittest.TestCase):
    """Test ensure_directory_exists function."""

    def setUp(self):
        """Create temporary directory for testing."""
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        """Clean up temporary directories."""
        shutil.rmtree(self.test_dir)

    def test_creates_directory(self):
        """Test that directory is created if it doesn't exist."""
        new_dir = os.path.join(self.test_dir, "new_directory")
        self.assertFalse(os.path.exists(new_dir))
        result = ensure_directory_exists(new_dir)
        self.assertTrue(os.path.exists(new_dir))
        self.assertEqual(result, new_dir)

    def test_existing_directory(self):
        """Test that existing directory is not affected."""
        result = ensure_directory_exists(self.test_dir)
        self.assertTrue(os.path.exists(self.test_dir))
        self.assertEqual(result, self.test_dir)

    def test_nested_directories(self):
        """Test creating nested directories."""
        nested = os.path.join(self.test_dir, "a", "b", "c")
        result = ensure_directory_exists(nested)
        self.assertTrue(os.path.exists(nested))
        self.assertEqual(result, nested)


class TestGetUniqueFilepath(unittest.TestCase):
    """Test get_unique_filepath function."""

    def test_basic_filepath(self):
        """Test basic filepath generation."""
        result = get_unique_filepath("/output", "image", ".png")
        self.assertEqual(result, "/output/image.png")

    def test_with_counter(self):
        """Test filepath with counter."""
        result = get_unique_filepath("/output", "image", ".png", counter=5)
        self.assertEqual(result, "/output/image_00005.png")

    def test_counter_formatting(self):
        """Test counter is formatted with leading zeros."""
        result = get_unique_filepath("/output", "image", ".jpg", counter=123)
        self.assertEqual(result, "/output/image_00123.jpg")

    def test_extension_without_dot(self):
        """Test extension is normalized if dot is missing."""
        result = get_unique_filepath("/output", "video", "mp4")
        self.assertEqual(result, "/output/video.mp4")

    def test_extension_with_dot(self):
        """Test extension with dot works correctly."""
        result = get_unique_filepath("/output", "video", ".mp4")
        self.assertEqual(result, "/output/video.mp4")

    def test_counter_zero(self):
        """Test counter value of zero."""
        result = get_unique_filepath("/output", "frame", ".png", counter=0)
        self.assertEqual(result, "/output/frame_00000.png")


if __name__ == "__main__":
    unittest.main()
