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
        """Test overwriting a direct symlink file."""
        # Create a target file
        target_file = os.path.join(self.test_dir, "target.txt")
        with open(target_file, "w") as f:
            f.write("Original Content")

        # Create symlinks in output dir pointing to target file
        symlink_video = os.path.join(self.output_dir, "ComfyUI-Video_00001.mp4")
        os.symlink(target_file, symlink_video)

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
                                overwrite_last=True,
                                format="video/h264-mp4",
                                save_output=True,
                                frame_rate=1.0
                            )

                        self.assertIn("symlink", str(context.exception))
                        print("SUCCESS: Direct symlink overwrite prevented.")

    def test_parent_directory_symlink_vulnerability(self):
        """Test writing to a path where a parent directory is a symlink."""
        # Create a real directory outside the intended output
        secret_dir = os.path.join(self.test_dir, "secret")
        os.makedirs(secret_dir)

        # Create a symlink inside output_dir pointing to secret_dir
        # /test_dir/output/evil_link -> /test_dir/secret
        evil_link = os.path.join(self.output_dir, "evil_link")
        os.symlink(secret_dir, evil_link)

        # We want to write to /test_dir/output/evil_link/file.mp4
        # which resolves to /test_dir/secret/file.mp4

        # Patch folder_paths to return the evil_link as the directory
        with patch('nodes.video_node.folder_paths') as mock_folder_paths:
            mock_folder_paths.get_save_image_path.return_value = (
                evil_link,
                "ComfyUI-Video",
                1,
                "",
                "ComfyUI-Video"
            )

            mock_images = [MagicMock()]
            mock_images[0].shape = (64, 64, 3)

            with patch('nodes.video_node.tensor_to_numpy_uint8') as mock_t2n:
                import numpy as np
                mock_t2n.return_value = np.zeros((64, 64, 3), dtype=np.uint8)

                with patch('nodes.video_node.ffmpeg_path', "ffmpeg"):
                    with patch('subprocess.Popen') as mock_popen:

                        with self.assertRaises(ValueError) as context:
                            self.node.save_video(
                                images=mock_images,
                                overwrite_last=True,
                                format="video/h264-mp4",
                                save_output=True,
                                frame_rate=1.0
                            )

                        # Check for either the parent dir message or the generic mismatch message
                        error_msg = str(context.exception)
                        self.assertTrue(
                            "Writing through directory symlinks is not allowed" in error_msg or
                            "Symlinks in output paths are not allowed" in error_msg,
                            f"Unexpected error message: {error_msg}"
                        )
                        print("SUCCESS: Parent directory symlink prevented.")

    def test_vhs_format_bypass(self):
        """Test that VHS format path recalculation is also validated."""
        # This test tries to exploit the path where 'is_vhs_format' is True
        # which changes the file extension and potentially bypasses early checks

        target_file = os.path.join(self.test_dir, "target.mkv")
        with open(target_file, "w") as f:
            f.write("Original Content")

        # Create symlink with different extension (mkv) that VHS might use
        symlink_video = os.path.join(self.output_dir, "ComfyUI-Video_00001.mkv")
        os.symlink(target_file, symlink_video)

        with patch('nodes.video_node.folder_paths') as mock_folder_paths:
            mock_folder_paths.get_save_image_path.return_value = (
                self.output_dir,
                "ComfyUI-Video",
                1,
                "",
                "ComfyUI-Video"
            )

            mock_images = [MagicMock()]
            mock_images[0].shape = (64, 64, 3)

            with patch('nodes.video_node.tensor_to_numpy_uint8') as mock_t2n:
                import numpy as np
                mock_t2n.return_value = np.zeros((64, 64, 3), dtype=np.uint8)

                with patch('nodes.video_node.ffmpeg_path', "ffmpeg"):
                    # Mock has_vhs_formats to be True
                    with patch('nodes.video_node.has_vhs_formats', True):
                         with patch('subprocess.Popen') as mock_popen:

                            # We need to trigger the VHS path.
                            # The code checks: is_vhs_format = has_vhs_formats and format not in ["video/mp4", "video/webm", "video/gif"]
                            # So pass a custom format string "video/mkv" (which splits to type=video, ext=mkv)
                            # The code then does: vhs_format_name = format.split("/")[-1] -> "mkv"

                            # We need to ensure basic_formats.get("mkv") returns something or we hit exception
                            # But wait, the code defines basic_formats inside the method.
                            # And it only has mp4, webm, gif keys.
                            # So "mkv" will use default empty dict.
                            # extension becomes "mkv".

                            with self.assertRaises(ValueError) as context:
                                self.node.save_video(
                                    images=mock_images,
                                    overwrite_last=True,
                                    format="video/mkv", # Custom format triggers VHS path
                                    save_output=True,
                                    frame_rate=1.0
                                )

                            self.assertIn("symlink", str(context.exception))
                            print("SUCCESS: VHS format path bypass prevented.")
