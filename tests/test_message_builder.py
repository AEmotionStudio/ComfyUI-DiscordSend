"""Tests for shared/discord/message_builder.py"""

import sys
import os
import unittest
from unittest.mock import MagicMock

# Mock dependencies before importing project modules
sys.modules["torch"] = MagicMock()
sys.modules["numpy"] = MagicMock()
sys.modules["cv2"] = MagicMock()

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.discord.message_builder import (
    build_metadata_section,
    build_prompt_section,
    build_discord_message,
    validate_message_content,
    format_file_info,
    format_file_size,
)


class TestBuildMetadataSection(unittest.TestCase):
    """Test build_metadata_section function."""

    def test_empty_dict(self):
        """Test with empty info dict returns empty string."""
        result = build_metadata_section({})
        self.assertEqual(result, "")

    def test_with_date(self):
        """Test metadata with date."""
        result = build_metadata_section({"date": "2026-01-20"})
        self.assertIn("**Date:** 2026-01-20", result)
        self.assertIn("**Information:**", result)

    def test_with_time(self):
        """Test metadata with time."""
        result = build_metadata_section({"time": "14-30-00"})
        self.assertIn("**Time:** 14-30-00", result)

    def test_with_dimensions(self):
        """Test metadata with dimensions."""
        result = build_metadata_section({"dimensions": "1920x1080"})
        self.assertIn("**Dimensions:** 1920x1080", result)

    def test_with_format(self):
        """Test metadata with file format."""
        result = build_metadata_section({}, file_format="png")
        self.assertIn("**Format:** PNG", result)

    def test_with_frame_rate(self):
        """Test metadata with frame rate."""
        result = build_metadata_section({}, frame_rate=30.0)
        self.assertIn("**Frame Rate:** 30.0 fps", result)

    def test_custom_section_title(self):
        """Test custom section title."""
        result = build_metadata_section({"date": "2026-01-20"}, section_title="Video Info")
        self.assertIn("**Video Info:**", result)

    def test_exclude_options(self):
        """Test excluding certain metadata."""
        info = {"date": "2026-01-20", "time": "14-30-00", "dimensions": "512x512"}
        result = build_metadata_section(info, include_date=False, include_time=False)
        self.assertNotIn("Date", result)
        self.assertNotIn("Time", result)
        self.assertIn("Dimensions", result)

    def test_trailing_newline(self):
        """Test that section ends with newline."""
        result = build_metadata_section({"date": "2026-01-20"})
        self.assertTrue(result.endswith("\n"))


class TestBuildPromptSection(unittest.TestCase):
    """Test build_prompt_section function."""

    def test_no_prompts(self):
        """Test with no prompts returns empty string."""
        result = build_prompt_section(None, None)
        self.assertEqual(result, "")

    def test_empty_prompts(self):
        """Test with empty prompts returns empty string."""
        result = build_prompt_section("", "")
        self.assertEqual(result, "")

    def test_whitespace_prompts(self):
        """Test with whitespace-only prompts returns empty string."""
        result = build_prompt_section("   ", "  \n  ")
        self.assertEqual(result, "")

    def test_positive_only(self):
        """Test with only positive prompt."""
        result = build_prompt_section("a beautiful sunset", None)
        self.assertIn("**Positive:**", result)
        self.assertIn("a beautiful sunset", result)
        self.assertNotIn("**Negative:**", result)

    def test_negative_only(self):
        """Test with only negative prompt."""
        result = build_prompt_section(None, "blurry, low quality")
        self.assertIn("**Negative:**", result)
        self.assertIn("blurry, low quality", result)
        self.assertNotIn("**Positive:**", result)

    def test_both_prompts(self):
        """Test with both prompts."""
        result = build_prompt_section("a cat", "dog")
        self.assertIn("**Positive:**", result)
        self.assertIn("a cat", result)
        self.assertIn("**Negative:**", result)
        self.assertIn("dog", result)

    def test_custom_section_title(self):
        """Test custom section title."""
        result = build_prompt_section("test", None, section_title="Custom Prompts")
        self.assertIn("**Custom Prompts:**", result)

    def test_code_block_formatting(self):
        """Test prompts are wrapped in code blocks."""
        result = build_prompt_section("test prompt", None)
        self.assertIn("```\ntest prompt\n```", result)

    def test_non_string_conversion(self):
        """Test that non-string prompts are converted."""
        result = build_prompt_section(12345, None)
        self.assertIn("12345", result)


class TestBuildDiscordMessage(unittest.TestCase):
    """Test build_discord_message function."""

    def test_empty_message(self):
        """Test building empty message."""
        result = build_discord_message()
        self.assertEqual(result, "")

    def test_base_message_only(self):
        """Test with just base message."""
        result = build_discord_message(base_message="Hello!")
        self.assertEqual(result, "Hello!")

    def test_with_metadata(self):
        """Test with metadata section."""
        result = build_discord_message(
            base_message="Image generated",
            metadata_section="\n**Info:** test"
        )
        self.assertIn("Image generated", result)
        self.assertIn("**Info:** test", result)

    def test_with_all_sections(self):
        """Test with all sections."""
        result = build_discord_message(
            base_message="Base",
            metadata_section="\nMeta",
            prompt_section="\nPrompt",
            additional_sections=["\nExtra1", "\nExtra2"]
        )
        self.assertIn("Base", result)
        self.assertIn("Meta", result)
        self.assertIn("Prompt", result)
        self.assertIn("Extra1", result)
        self.assertIn("Extra2", result)

    def test_truncation(self):
        """Test message truncation at max length."""
        long_message = "x" * 2500
        result = build_discord_message(base_message=long_message, max_length=2000)
        self.assertLessEqual(len(result), 2000)
        self.assertIn("[Message truncated]", result)

    def test_no_truncation_under_limit(self):
        """Test message not truncated when under limit."""
        message = "x" * 100
        result = build_discord_message(base_message=message)
        self.assertNotIn("truncated", result)


class TestValidateMessageContent(unittest.TestCase):
    """Test validate_message_content function."""

    def test_empty_message(self):
        """Test empty message is valid."""
        is_valid, msg = validate_message_content("")
        self.assertTrue(is_valid)
        self.assertIn("Empty message", msg)

    def test_normal_message(self):
        """Test normal message is valid."""
        is_valid, msg = validate_message_content("Hello world")
        self.assertTrue(is_valid)

    def test_too_long_message(self):
        """Test message over 2000 chars is invalid."""
        is_valid, msg = validate_message_content("x" * 2001)
        self.assertFalse(is_valid)
        self.assertIn("2000 character limit", msg)

    def test_message_with_prompts_section(self):
        """Test message with Generation Prompts section."""
        message = "Test\n**Generation Prompts:**\nContent"
        is_valid, msg = validate_message_content(message)
        self.assertTrue(is_valid)
        self.assertNotIn("WARNING", msg)

    def test_message_without_prompts_section(self):
        """Test message without Generation Prompts section shows warning."""
        is_valid, msg = validate_message_content("Test message")
        self.assertTrue(is_valid)
        self.assertIn("WARNING", msg)


class TestFormatFileSize(unittest.TestCase):
    """Test format_file_size function."""

    def test_bytes(self):
        """Test formatting bytes."""
        self.assertEqual(format_file_size(500), "500 bytes")

    def test_kilobytes(self):
        """Test formatting kilobytes."""
        self.assertEqual(format_file_size(2048), "2.0 KB")

    def test_megabytes(self):
        """Test formatting megabytes."""
        self.assertEqual(format_file_size(5 * 1024 * 1024), "5.0 MB")

    def test_gigabytes(self):
        """Test formatting gigabytes."""
        self.assertEqual(format_file_size(2 * 1024 * 1024 * 1024), "2.00 GB")

    def test_zero(self):
        """Test formatting zero bytes."""
        self.assertEqual(format_file_size(0), "0 bytes")


class TestFormatFileInfo(unittest.TestCase):
    """Test format_file_info function."""

    def test_basic_info(self):
        """Test basic file info formatting."""
        result = format_file_info("image.png", 1024)
        self.assertIn("image.png", result)
        self.assertIn("1.0 KB", result)

    def test_with_mime_type(self):
        """Test file info with MIME type."""
        result = format_file_info("video.mp4", 1024 * 1024, "video/mp4")
        self.assertIn("video.mp4", result)
        self.assertIn("1.0 MB", result)
        self.assertIn("[video/mp4]", result)


if __name__ == "__main__":
    unittest.main()
