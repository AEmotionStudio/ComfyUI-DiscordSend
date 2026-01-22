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

if __name__ == "__main__":
    unittest.main()
