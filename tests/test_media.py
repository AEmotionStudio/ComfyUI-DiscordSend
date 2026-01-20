# Mock dependencies before imports
import sys
import unittest
from unittest.mock import MagicMock, patch

# Create a dummy torch module
mock_torch = MagicMock()
sys.modules["torch"] = mock_torch
sys.modules["folder_paths"] = MagicMock()
sys.modules["comfy"] = MagicMock()
sys.modules["comfy.cli_args"] = MagicMock()
sys.modules["comfy.utils"] = MagicMock()
sys.modules["PIL"] = MagicMock()
sys.modules["PIL.Image"] = MagicMock()
sys.modules["PIL.PngImagePlugin"] = MagicMock()
sys.modules["cv2"] = MagicMock()
sys.modules["server"] = MagicMock()

# Add parent directory to path for imports
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from nodes.video_node import validate_video_for_discord

class TestPathLogic(unittest.TestCase):
    """Tests for path and file validation logic."""
    
    @patch('os.path.exists')
    @patch('os.path.getsize')
    def test_validate_video_discord_limits(self, mock_getsize, mock_exists):
        """Should correctly identify if a video is within Discord limits."""
        mock_exists.return_value = True
        
        # Test 10MB file (OK)
        mock_getsize.return_value = 10 * 1024 * 1024
        is_valid, msg = validate_video_for_discord("test.mp4")
        self.assertTrue(is_valid)
        
        # Test 100MB file (Too large)
        mock_getsize.return_value = 100 * 1024 * 1024
        is_valid, msg = validate_video_for_discord("test.mp4")
        self.assertFalse(is_valid)
        self.assertIn("exceeds Discord's size limit", msg)

    def test_validate_video_formats(self):
        """Should validate supported video formats."""
        with patch('os.path.exists', return_value=True), \
             patch('os.path.getsize', return_value=1024 * 1024):
            
            self.assertTrue(validate_video_for_discord("test.mp4")[0])
            self.assertTrue(validate_video_for_discord("test.webm")[0])
            self.assertTrue(validate_video_for_discord("test.gif")[0])
            
            # MOV usually marked as needing conversion
            is_valid, msg = validate_video_for_discord("test.mov")
            self.assertFalse(is_valid)
            self.assertIn("need conversion", msg.lower())

class TestImageResizing(unittest.TestCase):
    """
    Tests for image resizing logic. 
    Note: The actual resizing logic is inside the Node class. 
    We are testing the mathematical logic that would be used.
    """
    
    def test_power_of_two_math(self):
        """Verify the power-of-two calculation logic used in the node."""
        import numpy as np
        
        def calculate_nearest_pow2(dim):
            return 2 ** int(np.log2(dim) + 0.5)
            
        self.assertEqual(calculate_nearest_pow2(500), 512)
        self.assertEqual(calculate_nearest_pow2(700), 512) # log2(700) = 9.45, +0.5 = 9.95, int=9, 2^9=512
        self.assertEqual(calculate_nearest_pow2(800), 1024) # log2(800) = 9.64, +0.5 = 10.14, int=10, 2^10=1024
        self.assertEqual(calculate_nearest_pow2(256), 256)

if __name__ == "__main__":
    unittest.main()
