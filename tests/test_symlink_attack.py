import unittest
import sys
import os
import tempfile
import shutil
from unittest.mock import MagicMock, patch

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Mock comfy modules
if 'comfy' not in sys.modules:
    sys.modules['comfy'] = MagicMock()
if 'comfy.cli_args' not in sys.modules:
    sys.modules['comfy.cli_args'] = MagicMock()
    sys.modules['comfy.cli_args'].args = MagicMock()
    sys.modules['comfy.cli_args'].args.disable_metadata = False
if 'comfy.utils' not in sys.modules:
    sys.modules['comfy.utils'] = MagicMock()
if 'folder_paths' not in sys.modules:
    sys.modules['folder_paths'] = MagicMock()
if 'server' not in sys.modules:
    sys.modules['server'] = MagicMock()

# Mock heavy/external dependencies
sys.modules['torch'] = MagicMock()
sys.modules['cv2'] = MagicMock()
# We rely on real Pillow and numpy being installed and used

# Import the node
try:
    from nodes.video_node import DiscordSendSaveVideo
except ImportError:
    raise

class TestSymlinkAttack(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.output_dir = os.path.join(self.test_dir, "output")
        self.temp_dir = os.path.join(self.test_dir, "temp")
        os.makedirs(self.output_dir)
        os.makedirs(self.temp_dir)

        self.node = DiscordSendSaveVideo()

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_overwrite_symlink_vulnerability(self):
        # Create a target file
        target_file = os.path.join(self.test_dir, "target.txt")
        with open(target_file, "w") as f:
            f.write("Original Content")

        # Create symlinks in output dir pointing to target file
        # Filename will be ComfyUI-Video_00001.mp4 (default prefix + counter 1 + extension)
        symlink_video = os.path.join(self.output_dir, "ComfyUI-Video_00001.mp4")
        os.symlink(target_file, symlink_video)

        # Create symlink for the PNG preview too, to verify we check ALL output paths
        symlink_png = os.path.join(self.output_dir, "ComfyUI-Video_00001.png")
        os.symlink(target_file, symlink_png)

        # Patch folder_paths on the node module
        with patch('nodes.video_node.folder_paths') as mock_folder_paths:
            mock_folder_paths.get_save_image_path.return_value = (
                self.output_dir,
                "ComfyUI-Video",
                1,
                "",
                "ComfyUI-Video"
            )

            # Mock images input
            mock_images = [MagicMock()]
            mock_images[0].shape = (64, 64, 3)

            # Mock tensor_to_numpy_uint8 to return a real numpy array
            # This is needed in case the code proceeds to image generation
            with patch('nodes.video_node.tensor_to_numpy_uint8') as mock_t2n:
                import numpy as np
                mock_t2n.return_value = np.zeros((64, 64, 3), dtype=np.uint8)

                with patch('nodes.video_node.ffmpeg_path', "ffmpeg"):
                    with patch('subprocess.Popen') as mock_popen:
                        mock_popen.return_value = MagicMock()

                        # Expect ValueError when trying to overwrite symlink
                        with self.assertRaises(ValueError) as context:
                            self.node.save_video(
                                images=mock_images,
                                overwrite_last=True, # Force using counter 1
                                format="video/h264-mp4",
                                save_output=True,
                                frame_rate=1.0
                            )

                        self.assertIn("symlink", str(context.exception))
                        print("SUCCESS: Symlink overwrite prevented by security check.")

                        # Ensure subprocess was NOT called
                        self.assertFalse(mock_popen.called, "Subprocess should not be called if validation fails")
