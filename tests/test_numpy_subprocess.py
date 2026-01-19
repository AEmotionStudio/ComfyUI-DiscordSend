import unittest
import numpy as np
import subprocess
import sys
import os

class TestNumpyToSubprocess(unittest.TestCase):
    """
    Verify that subprocess.Popen.stdin.write accepts numpy arrays directly.
    For subprocess.run(input=...), we need to be careful with numpy arrays due to ambiguity check in subprocess module.
    """

    def test_popen_stdin_write_numpy(self):
        """Test writing numpy array to Popen.stdin"""
        # Create a small numpy array
        data = np.arange(256, dtype=np.uint8)

        # Use 'cat' to echo input to output
        p = subprocess.Popen(['cat'], stdin=subprocess.PIPE, stdout=subprocess.PIPE)

        # Write numpy array directly
        p.stdin.write(data)
        out, _ = p.communicate()

        # Verify output matches input data bytes
        self.assertEqual(out, data.tobytes())
        self.assertEqual(len(out), 256)

    def test_run_input_memoryview(self):
        """
        Test passing numpy array as memoryview to subprocess.run input.
        subprocess.run checks truthiness of input which fails for numpy arrays.
        So for subprocess.run we should use memoryview(array) or array.tobytes().
        However, in discord_video_node.py we use subprocess.run for audio.
        """
        data = np.arange(256, dtype=np.uint8)

        # Use 'cat' to echo input to output
        # memoryview works and avoids copy
        res = subprocess.run(['cat'], input=memoryview(data), capture_output=True)

        self.assertEqual(res.stdout, data.tobytes())
        self.assertEqual(len(res.stdout), 256)

if __name__ == "__main__":
    unittest.main()
