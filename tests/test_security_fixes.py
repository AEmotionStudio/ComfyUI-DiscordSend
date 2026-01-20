
import sys
import os
import unittest
from unittest.mock import patch, MagicMock
import shutil
import tempfile

# Mock dependencies before importing project modules
sys.modules["torch"] = MagicMock()
sys.modules["numpy"] = MagicMock()
sys.modules["cv2"] = MagicMock()
sys.modules["PIL"] = MagicMock()
sys.modules["PIL.Image"] = MagicMock()
sys.modules["PIL.PngImagePlugin"] = MagicMock()
sys.modules["comfy"] = MagicMock()
sys.modules["comfy.cli_args"] = MagicMock()
sys.modules["comfy.utils"] = MagicMock()
sys.modules["server"] = MagicMock()

# Mock folder_paths
mock_folder_paths = MagicMock()
sys.modules["folder_paths"] = mock_folder_paths

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the node
from nodes.video_node import DiscordSendSaveVideo

class TestTempFileLeak(unittest.TestCase):
    def setUp(self):
        # Create a real temporary directory for our test
        self.test_dir = tempfile.mkdtemp()
        self.output_dir = os.path.join(self.test_dir, "output")
        self.temp_dir = os.path.join(self.test_dir, "temp")
        os.makedirs(self.output_dir)
        os.makedirs(self.temp_dir)

        # Configure folder_paths mock
        mock_folder_paths.get_output_directory.return_value = self.output_dir
        mock_folder_paths.get_temp_directory.return_value = self.temp_dir

        # Mock get_save_image_path to return predictable paths
        # full_output_folder, filename, counter, subfolder, filename_prefix
        mock_folder_paths.get_save_image_path.return_value = (
            self.output_dir, "ComfyUI-Video", 1, "", "ComfyUI-Video"
        )

        # Instantiate the node
        self.node = DiscordSendSaveVideo()

        # Create a dummy image tensor mock
        self.dummy_image = MagicMock()
        self.dummy_image.shape = (512, 512, 3) # height, width, channels

        # Mock tensor_to_numpy_uint8 in discordsend_utils
        self.patcher_numpy = patch("nodes.video_node.tensor_to_numpy_uint8")
        self.mock_numpy_conv = self.patcher_numpy.start()
        # Return a dummy numpy array
        import numpy as np
        self.mock_numpy_conv.return_value = np.zeros((512, 512, 3), dtype=np.uint8)

    def tearDown(self):
        self.patcher_numpy.stop()
        shutil.rmtree(self.test_dir)

    @patch("nodes.video_node.subprocess.Popen")
    @patch("nodes.video_node.subprocess.run")
    @patch("nodes.video_node.send_to_discord_with_retry")
    @patch("nodes.video_node.Image")
    @patch("nodes.video_node.os.path.getsize")
    @patch("nodes.video_node.validate_video_for_discord")
    def test_temp_file_leak(self, mock_validate, mock_getsize, mock_image, mock_send, mock_run, mock_popen):
        # Setup mocks
        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.stdin = MagicMock()
        mock_popen.return_value = mock_process

        mock_send.return_value.status_code = 200
        mock_send.return_value.json.return_value = {}

        mock_getsize.return_value = 1024 * 1024 # 1MB
        mock_validate.return_value = (True, "Valid")

        # Create a fake output file that subprocess would have created
        fake_output_path = os.path.join(self.output_dir, "ComfyUI-Video_00001.mp4")
        with open(fake_output_path, "wb") as f:
            f.write(b"fake video content")

        # Mock subprocess.run to simulate creation of optimized file
        def side_effect_run(args, **kwargs):
            # The last argument is the output file path
            output_file = args[-1]
            if "discord_optimized_" in output_file:
                # Create the file
                with open(output_file, "wb") as f:
                    f.write(b"optimized video content")
            return MagicMock(returncode=0)

        mock_run.side_effect = side_effect_run

        # Run the node
        self.node.save_video(
            images=[self.dummy_image],
            send_to_discord=True,
            webhook_url="https://discord.com/api/webhooks/123/abc",
            format="video/h264-mp4",
            save_output=True
        )

        # Check if any file in temp_dir contains "discord_optimized_"
        temp_files = os.listdir(self.temp_dir)
        optimized_files = [f for f in temp_files if "discord_optimized_" in f]

        print(f"Files remaining in temp dir: {temp_files}")

        # This assertion is expected to FAIL if the leak exists (because we want 0 files)
        # Or pass if we assert > 0 to prove the leak.
        # After fix, we expect 0 files.
        self.assertEqual(len(optimized_files), 0, "Temporary optimized file should have been cleaned up")

if __name__ == "__main__":
    unittest.main()
