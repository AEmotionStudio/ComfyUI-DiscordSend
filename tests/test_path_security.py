
import os
import sys
import unittest
from unittest.mock import MagicMock

# Mock dependencies to allow testing in isolation
sys.modules["folder_paths"] = MagicMock()
sys.modules["comfy"] = MagicMock()
sys.modules["server"] = MagicMock()
sys.modules["requests"] = MagicMock()
sys.modules["PIL"] = MagicMock()
sys.modules["numpy"] = MagicMock()
sys.modules["cv2"] = MagicMock()
sys.modules["torch"] = MagicMock()
sys.modules["torch.nn"] = MagicMock()
sys.modules["torch.nn.functional"] = MagicMock()

# Add project root to sys.path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from shared.path_utils import validate_path_is_safe

class TestPathSecurity(unittest.TestCase):
    def setUp(self):
        self.test_dir = os.path.join(os.getcwd(), "test_safe_env")
        os.makedirs(self.test_dir, exist_ok=True)

    def tearDown(self):
        # Clean up would go here, but since we use temp dirs or mocks, it's fine.
        # Ideally use tempfile.TemporaryDirectory but this is simple.
        import shutil
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_absolute_path_blocked_with_base_dir(self):
        # This test checks if validate_path_is_safe blocks writing to /tmp
        # when base_dir is provided.

        base_dir = self.test_dir
        test_path = "/tmp/sentinel_test_file.txt"

        try:
            validate_path_is_safe(test_path, base_dir=base_dir)
            self.fail("Should have raised ValueError")
        except ValueError as e:
            self.assertIn("outside the allowed directory", str(e))

    def test_traversal_blocked_with_base_dir(self):
        # Create a directory structure
        base_dir = self.test_dir
        subdir = os.path.join(base_dir, "subdir")
        os.makedirs(subdir, exist_ok=True)

        # ../ traversal
        # This path resolves to outside base_dir
        test_path = os.path.abspath(os.path.join(subdir, "../../test_safe_escape.txt"))

        try:
            validate_path_is_safe(test_path, base_dir=base_dir)
            self.fail("Should have raised ValueError")
        except ValueError as e:
            self.assertIn("outside the allowed directory", str(e))

    def test_valid_path_allowed_with_base_dir(self):
        base_dir = self.test_dir
        test_path = os.path.join(base_dir, "valid_file.txt")

        # Should not raise
        validate_path_is_safe(test_path, base_dir=base_dir)

if __name__ == "__main__":
    unittest.main()
