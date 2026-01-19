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

        # Use python to echo input to output (cross-platform)
        cmd = [sys.executable, '-c', 'import sys; sys.stdout.buffer.write(sys.stdin.buffer.read())']
        p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE)

        # Write numpy array directly
        p.stdin.write(data)
        out, _ = p.communicate()

        # Verify output matches input data bytes
        self.assertEqual(out, data.tobytes())
        self.assertEqual(len(out), 256)

    def test_run_input_memoryview(self):
        """
        Test passing numpy array as memoryview to subprocess.run input.
        """
        data = np.arange(256, dtype=np.uint8)

        # Use python to echo input to output (cross-platform)
        cmd = [sys.executable, '-c', 'import sys; sys.stdout.buffer.write(sys.stdin.buffer.read())']
        # memoryview works and avoids copy
        res = subprocess.run(cmd, input=memoryview(data), capture_output=True)

        self.assertEqual(res.stdout, data.tobytes())
        self.assertEqual(len(res.stdout), 256)

    def test_run_input_fixed_non_contiguous(self):
        """
        Test that using ascontiguousarray makes the non-contiguous array accepted by subprocess.run
        """
        # Create a 2D array and transpose it to make it non-contiguous
        data = np.zeros((10, 10), dtype=np.uint8)
        # Fill with some data
        for i in range(10):
            for j in range(10):
                data[i, j] = i + j

        # Transpose creates a non-contiguous view
        transposed_data = data.T
        self.assertFalse(transposed_data.flags['C_CONTIGUOUS'])

        # Fix it using ascontiguousarray
        contiguous_data = np.ascontiguousarray(transposed_data)
        self.assertTrue(contiguous_data.flags['C_CONTIGUOUS'])

        # Now pass to subprocess
        mv = memoryview(contiguous_data)
        cmd = [sys.executable, '-c', 'import sys; sys.stdout.buffer.write(sys.stdin.buffer.read())']
        res = subprocess.run(cmd, input=mv, capture_output=True)
        self.assertEqual(res.stdout, contiguous_data.tobytes())

if __name__ == "__main__":
    unittest.main()
