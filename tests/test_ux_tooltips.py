import unittest
import sys
import os
from unittest.mock import MagicMock

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Mock comfy modules needed for import
sys.modules['comfy'] = MagicMock()
sys.modules['comfy.cli_args'] = MagicMock()
sys.modules['comfy.cli_args'].args = MagicMock()
sys.modules['comfy.cli_args'].args.disable_metadata = False
sys.modules['comfy.utils'] = MagicMock()
sys.modules['folder_paths'] = MagicMock()
sys.modules['server'] = MagicMock()

# Mock torch if not available (video_node imports it)
if 'torch' not in sys.modules:
    sys.modules['torch'] = MagicMock()

from nodes.image_node import DiscordSendSaveImage
from nodes.video_node import DiscordSendSaveVideo

class TestUXTooltips(unittest.TestCase):
    def test_video_node_add_time_tooltip(self):
        """Test that the add_time tooltip in video node contains the critical warning."""
        input_types = DiscordSendSaveVideo.INPUT_TYPES()
        add_time_config = input_types["optional"]["add_time"]
        tooltip = add_time_config[1]["tooltip"]

        # Verify it HAS the warning
        self.assertIn("CRITICAL", tooltip)
        self.assertIn("single-frame playback", tooltip)
        self.assertIn("Add time", tooltip)

    def test_image_node_add_time_tooltip(self):
        """Test that the add_time tooltip in image node is standard."""
        input_types = DiscordSendSaveImage.INPUT_TYPES()
        add_time_config = input_types["optional"]["add_time"]
        tooltip = add_time_config[1]["tooltip"]

        expected = "Add time (HH-MM-SS) to the filename."
        self.assertEqual(tooltip, expected)

    def test_github_token_tooltip(self):
        """Test that the github_token tooltip contains helpful instructions."""
        # Both nodes inherit from BaseDiscordNode, so check one
        input_types = DiscordSendSaveImage.INPUT_TYPES()
        token_config = input_types["optional"]["github_token"]
        tooltip = token_config[1]["tooltip"]

        self.assertIn("Settings > Developer settings > Tokens", tooltip)
        self.assertIn("Requires 'repo' scope", tooltip)

    def test_resize_method_clarity(self):
        """Test that resize_method tooltip clarifies dependency on resize_to_power_of_2."""
        input_types = DiscordSendSaveImage.INPUT_TYPES()
        resize_config = input_types["optional"]["resize_method"]
        tooltip = resize_config[1]["tooltip"]

        self.assertIn("ONLY when 'resize_to_power_of_2' is enabled", tooltip)
        self.assertIn("Ignored otherwise", tooltip)
        self.assertIn("lanczos: Best for photos", tooltip)

    def test_overwrite_safety_warning(self):
        """Test that overwrite_last tooltip contains safety warning in both nodes."""
        # Test Image Node
        input_types_img = DiscordSendSaveImage.INPUT_TYPES()
        tooltip_img = input_types_img["required"]["overwrite_last"][1]["tooltip"]

        self.assertIn("CAUTION", tooltip_img)
        self.assertIn("REPLACE the previous file", tooltip_img)
        self.assertIn("dangerous for batch production", tooltip_img)
        self.assertIn("disable 'add_time' and 'add_date'", tooltip_img)

        # Test Video Node
        input_types_vid = DiscordSendSaveVideo.INPUT_TYPES()
        tooltip_vid = input_types_vid["required"]["overwrite_last"][1]["tooltip"]

        self.assertIn("CAUTION", tooltip_vid)
        self.assertIn("REPLACE the previous file", tooltip_vid)
        self.assertIn("dangerous for batch production", tooltip_vid)
        self.assertIn("Disabling 'add_time' to overwrite files will cause single-frame playback issues", tooltip_vid)

if __name__ == "__main__":
    unittest.main()
