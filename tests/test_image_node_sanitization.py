import unittest
import json
import sys
import os
from unittest.mock import MagicMock, patch
import importlib

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Clean up any potential pollution from other tests before we start
if 'PIL' in sys.modules:
    # Check if it's a mock
    if isinstance(sys.modules['PIL'], MagicMock):
        del sys.modules['PIL']
        if 'PIL.PngImagePlugin' in sys.modules:
            del sys.modules['PIL.PngImagePlugin']
        if 'PIL.Image' in sys.modules:
            del sys.modules['PIL.Image']

# Now we can import real modules or mock them as we see fit LOCALLY
# But wait, discord_image_node imports them at module level.
# So we need to ensure environment is set up before importing it.

# Mock comfy modules
sys.modules['comfy'] = MagicMock()
sys.modules['comfy.cli_args'] = MagicMock()
sys.modules['comfy.cli_args'].args = MagicMock()
sys.modules['comfy.cli_args'].args.disable_metadata = False
sys.modules['folder_paths'] = MagicMock()
sys.modules['folder_paths'].get_output_directory = MagicMock(return_value="/tmp")
sys.modules['folder_paths'].get_temp_directory = MagicMock(return_value="/tmp")
sys.modules['folder_paths'].get_save_image_path = MagicMock(return_value=("/tmp", "test", 0, "", "test"))

# We need real PIL for this test to verify PngInfo
try:
    import PIL.PngImagePlugin
except ImportError:
    # If it failed because it was mocked out and we deleted it, reload
    pass

from discord_image_node import DiscordSendSaveImage

class TestDiscordImageNodeOptimization(unittest.TestCase):
    def setUp(self):
        self.node = DiscordSendSaveImage()
        self.webhook_url = "https://discord.com/api/webhooks/12345/abcdef"
        self.github_token = "ghp_sensitive12345"

    def test_save_images_sanitization(self):
        # Create a mock image (needs to be proper shape for the node)
        import torch
        mock_image = torch.zeros((1, 64, 64, 3))

        # Create prompt and extra_pnginfo with sensitive data
        prompt = {
            "3": {
                "inputs": {
                    "webhook_url": self.webhook_url,
                    "seed": 123
                },
                "class_type": "DiscordSendSaveImage"
            }
        }

        extra_pnginfo = {
            "workflow": {
                "nodes": [
                    {
                        "id": 3,
                        "type": "DiscordSendSaveImage",
                        "widgets_values": [self.webhook_url, "message"]
                    }
                ]
            }
        }

        # Mock Image.save to check metadata
        with patch('PIL.Image.Image.save') as mock_save:
            self.node.save_images(
                images=mock_image,
                prompt=prompt,
                extra_pnginfo=extra_pnginfo,
                save_output=True,
                send_to_discord=False # Disable discord sending to focus on save/metadata
            )

            # Check if save was called
            self.assertTrue(mock_save.called)

            # Get the pnginfo passed to save
            args, kwargs = mock_save.call_args
            pnginfo = kwargs.get('pnginfo')
            self.assertIsNotNone(pnginfo)

            found_prompt = False
            found_workflow = False

            # Check chunks - PIL PngInfo internal structure
            for tag_type, data, after_idat in pnginfo.chunks:
                try:
                    # decode data
                    decoded = data.decode('latin-1')
                except Exception:
                    # Skip chunks that can't be decoded
                    continue

                if '\0' in decoded:
                    try:
                        k, v = decoded.split('\0', 1)
                    except ValueError:
                        continue

                    if k == "prompt":
                        found_prompt = True
                        # Verify sensitive data is gone
                        self.assertNotIn("discord.com/api/webhooks", v)
                        self.assertNotIn("ghp_", v)

                    if k == "workflow":
                        found_workflow = True
                        self.assertNotIn("discord.com/api/webhooks", v)
                        self.assertNotIn("ghp_", v)

            self.assertTrue(found_prompt, "Prompt metadata not found")
            self.assertTrue(found_workflow, "Workflow metadata not found")

if __name__ == "__main__":
    unittest.main()
