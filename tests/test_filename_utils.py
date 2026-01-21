"""Tests for shared/filename_utils.py"""

import sys
import os
import unittest
from unittest.mock import patch, MagicMock

# Mock dependencies before importing project modules
sys.modules["torch"] = MagicMock()
sys.modules["numpy"] = MagicMock()
sys.modules["cv2"] = MagicMock()

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.filename_utils import build_filename_with_metadata, get_timestamp_string


class TestBuildFilenameWithMetadata(unittest.TestCase):
    """Test build_filename_with_metadata function."""

    def test_prefix_only(self):
        """Test with just a prefix, no metadata."""
        result, info = build_filename_with_metadata("image")
        self.assertEqual(result, "image")
        self.assertEqual(info, {})

    @patch("shared.filename_utils.time")
    def test_with_date(self, mock_time):
        """Test adding date to filename."""
        mock_time.strftime.return_value = "2026-01-20"
        result, info = build_filename_with_metadata("image", add_date=True)
        self.assertEqual(result, "image_2026-01-20")
        self.assertEqual(info["date"], "2026-01-20")

    @patch("shared.filename_utils.time")
    def test_with_time(self, mock_time):
        """Test adding time to filename."""
        mock_time.strftime.return_value = "14-30-00"
        result, info = build_filename_with_metadata("image", add_time=True)
        self.assertEqual(result, "image_14-30-00")
        self.assertEqual(info["time"], "14-30-00")

    def test_with_dimensions(self):
        """Test adding dimensions to filename."""
        result, info = build_filename_with_metadata(
            "image", add_dimensions=True, width=1920, height=1080
        )
        self.assertEqual(result, "image_1920x1080")
        self.assertEqual(info["dimensions"], "1920x1080")

    def test_dimensions_without_values(self):
        """Test that dimensions are not added without width/height."""
        result, info = build_filename_with_metadata("image", add_dimensions=True)
        self.assertEqual(result, "image")
        self.assertNotIn("dimensions", info)

    @patch("shared.filename_utils.time")
    def test_all_metadata(self, mock_time):
        """Test with all metadata options."""
        mock_time.strftime.side_effect = ["2026-01-20", "14-30-00"]
        result, info = build_filename_with_metadata(
            "output",
            add_date=True,
            add_time=True,
            add_dimensions=True,
            width=512,
            height=768,
        )
        self.assertEqual(result, "output_2026-01-20_14-30-00_512x768")
        self.assertEqual(info["date"], "2026-01-20")
        self.assertEqual(info["time"], "14-30-00")
        self.assertEqual(info["dimensions"], "512x768")

    def test_with_existing_info_dict(self):
        """Test that existing info_dict is updated, not replaced."""
        existing_info = {"existing_key": "existing_value"}
        result, info = build_filename_with_metadata(
            "image", add_dimensions=True, width=100, height=100, info_dict=existing_info
        )
        self.assertEqual(info["existing_key"], "existing_value")
        self.assertEqual(info["dimensions"], "100x100")
        self.assertIs(info, existing_info)  # Same dict object


class TestGetTimestampString(unittest.TestCase):
    """Test get_timestamp_string function."""

    @patch("shared.filename_utils.time")
    def test_date_only(self, mock_time):
        """Test timestamp with date only."""
        mock_time.strftime.return_value = "2026-01-20"
        result = get_timestamp_string(include_date=True, include_time=False)
        self.assertEqual(result, "2026-01-20")

    @patch("shared.filename_utils.time")
    def test_time_only(self, mock_time):
        """Test timestamp with time only."""
        mock_time.strftime.return_value = "14-30-00"
        result = get_timestamp_string(include_date=False, include_time=True)
        self.assertEqual(result, "14-30-00")

    @patch("shared.filename_utils.time")
    def test_both(self, mock_time):
        """Test timestamp with both date and time."""
        mock_time.strftime.side_effect = ["2026-01-20", "14-30-00"]
        result = get_timestamp_string(include_date=True, include_time=True)
        self.assertEqual(result, "2026-01-20_14-30-00")

    def test_neither(self):
        """Test timestamp with neither date nor time."""
        result = get_timestamp_string(include_date=False, include_time=False)
        self.assertEqual(result, "")


if __name__ == "__main__":
    unittest.main()
