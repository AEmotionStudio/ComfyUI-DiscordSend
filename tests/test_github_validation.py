
import unittest
import sys
from unittest.mock import MagicMock

# Mock torch and other heavy dependencies
sys.modules["torch"] = MagicMock()
sys.modules["numpy"] = MagicMock()
sys.modules["PIL"] = MagicMock()
sys.modules["cv2"] = MagicMock()
sys.modules["folder_paths"] = MagicMock()
sys.modules["comfy"] = MagicMock()
sys.modules["comfy.cli_args"] = MagicMock()

# Now we can safely import
from discordsend_utils.github_integration import validate_github_repo, validate_file_path, update_github_cdn_urls

class TestGitHubValidation(unittest.TestCase):

    def test_validate_github_repo_valid(self):
        """Test valid GitHub repository formats."""
        valid_repos = [
            "username/repo",
            "user-name/repo-name",
            "user-name/repo.name",  # Dot in repo is valid
            "user-name/repo_name",  # Underscore in repo is valid
            "0123/4567"
        ]
        for repo in valid_repos:
            with self.subTest(repo=repo):
                self.assertTrue(validate_github_repo(repo), f"Failed for {repo}")

    def test_validate_github_repo_invalid(self):
        """Test invalid GitHub repository formats (traversal, injection, invalid chars)."""
        invalid_repos = [
            "username/repo/../other",  # Traversal
            "username/repo?query=1",   # Query injection
            "username",                # Missing slash
            "/repo",                   # Missing username
            "user/",                   # Missing repo
            "user/repo/",              # Trailing slash (strict check)
            "../../user/repo",         # Traversal at start
            "user/repo#fragment",      # Fragment
            "user/repo;rm -rf",        # Command injection style
            "user/repo\nnewline",      # Newline
            "user.name/repo",          # Dot in username (invalid)
            "user_name/repo",          # Underscore in username (invalid)
        ]
        for repo in invalid_repos:
            with self.subTest(repo=repo):
                self.assertFalse(validate_github_repo(repo), f"Should have failed for {repo}")

    def test_validate_file_path_valid(self):
        """Test valid file paths."""
        valid_paths = [
            "file.txt",
            "path/to/file.txt",
            "folder/subfolder/file.md",
            "README.md",
            "docs/image.png"
        ]
        for path in valid_paths:
            with self.subTest(path=path):
                self.assertTrue(validate_file_path(path), f"Failed for {path}")

    def test_validate_file_path_invalid(self):
        """Test invalid file paths (traversal, absolute)."""
        invalid_paths = [
            "../file.txt",             # Traversal
            "path/../file.txt",        # Traversal inside
            "/etc/passwd",             # Absolute path
            "/file.txt",               # Absolute path
            "../../secret",            # Deep traversal
            "",                        # Empty
            None                       # None
        ]
        for path in invalid_paths:
            with self.subTest(path=path):
                self.assertFalse(validate_file_path(path), f"Should have failed for {path}")

    def test_update_github_cdn_urls_rejects_invalid_repo(self):
        """Test that update_github_cdn_urls rejects invalid repo before making requests."""
        repo = "user/repo/../malicious"
        success, message = update_github_cdn_urls(repo, "token", "file.md", [("f", "u")])

        self.assertFalse(success)
        self.assertIn("Invalid GitHub repository format", message)

    def test_update_github_cdn_urls_rejects_invalid_path(self):
        """Test that update_github_cdn_urls rejects invalid path before making requests."""
        path = "../../../secret.txt"
        success, message = update_github_cdn_urls("user/repo", "token", path, [("f", "u")])

        self.assertFalse(success)
        self.assertIn("Invalid file path", message)
        self.assertIn("Path traversal", message)

if __name__ == "__main__":
    unittest.main()
