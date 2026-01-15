"""
Unit tests for ComfyUI-DiscordSend utilities.

Run tests with: python -m pytest tests/test_utils.py -v
Or without pytest: python tests/test_utils.py
"""

import sys
import os
import unittest

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.sanitizer import sanitize_json_for_export
from utils.discord_api import validate_webhook_url, sanitize_webhook_for_logging, send_to_discord_with_retry
from unittest.mock import patch, MagicMock


class TestSanitizer(unittest.TestCase):
    """Tests for the sanitize_json_for_export function."""
    
    def test_sanitize_none(self):
        """Should handle None input."""
        self.assertIsNone(sanitize_json_for_export(None))
    
    def test_sanitize_webhook_url_in_string(self):
        """Should remove webhook URLs from strings."""
        test_url = "https://discord.com/api/webhooks/123456789/abcdefg"
        result = sanitize_json_for_export(test_url)
        self.assertEqual(result, "")
    
    def test_sanitize_github_token_in_string(self):
        """Should remove GitHub tokens from strings."""
        test_token = "ghp_1234567890abcdefghijklmnopqrstuvwxyz"
        result = sanitize_json_for_export(test_token)
        self.assertEqual(result, "")
    
    def test_sanitize_dict_with_webhook_key(self):
        """Should remove values for webhook-related keys."""
        test_data = {
            "webhook_url": "https://discord.com/api/webhooks/123/abc",
            "message": "Hello world"
        }
        result = sanitize_json_for_export(test_data)
        self.assertEqual(result["webhook_url"], "")
        self.assertEqual(result["message"], "Hello world")
    
    def test_sanitize_dict_with_github_token_key(self):
        """Should remove values for github_token keys."""
        test_data = {
            "github_token": "ghp_secret123",
            "repo": "user/repo"
        }
        result = sanitize_json_for_export(test_data)
        self.assertEqual(result["github_token"], "")
        self.assertEqual(result["repo"], "user/repo")
    
    def test_sanitize_nested_dict(self):
        """Should sanitize nested dictionaries."""
        test_data = {
            "level1": {
                "webhook_url": "https://discord.com/api/webhooks/123/abc",
                "level2": {
                    "github_token": "ghp_secret"
                }
            }
        }
        result = sanitize_json_for_export(test_data)
        self.assertEqual(result["level1"]["webhook_url"], "")
        self.assertEqual(result["level1"]["level2"]["github_token"], "")
    
    def test_sanitize_list(self):
        """Should sanitize lists."""
        test_data = [
            "normal string",
            "https://discord.com/api/webhooks/123/abc",
            {"webhook_url": "secret"}
        ]
        result = sanitize_json_for_export(test_data)
        self.assertEqual(result[0], "normal string")
        self.assertEqual(result[1], "")
        self.assertEqual(result[2]["webhook_url"], "")
    
    def test_preserve_normal_data(self):
        """Should preserve non-sensitive data."""
        test_data = {
            "prompt": "a beautiful sunset",
            "seed": 12345,
            "steps": 20,
            "cfg": 7.5
        }
        result = sanitize_json_for_export(test_data)
        self.assertEqual(result, test_data)


class TestWebhookValidation(unittest.TestCase):
    """Tests for webhook URL validation."""
    
    def test_valid_webhook_url(self):
        """Should accept valid Discord webhook URLs."""
        valid_url = "https://discord.com/api/webhooks/1234567890/abcdefghijklmnop"
        is_valid, message = validate_webhook_url(valid_url)
        self.assertTrue(is_valid)
    
    def test_valid_discordapp_url(self):
        """Should accept discordapp.com URLs."""
        valid_url = "https://discordapp.com/api/webhooks/1234567890/abcdefghijklmnop"
        is_valid, message = validate_webhook_url(valid_url)
        self.assertTrue(is_valid)
    
    def test_empty_url(self):
        """Should reject empty URLs."""
        is_valid, message = validate_webhook_url("")
        self.assertFalse(is_valid)
    
    def test_invalid_url(self):
        """Should reject non-webhook URLs."""
        is_valid, message = validate_webhook_url("https://example.com")
        self.assertFalse(is_valid)

    def test_bypass_attempt_url(self):
        """Should reject URLs that attempt to bypass validation."""
        # This URL contains 'discord' and 'webhook' but is not hosted on discord.com
        bypass_url = "http://evil-site.com/discord/webhook"
        is_valid, message = validate_webhook_url(bypass_url)
        self.assertFalse(is_valid)

    def test_localhost_url(self):
        """Should reject localhost URLs (SSRF protection)."""
        is_valid, message = validate_webhook_url("http://localhost:8080/admin")
        self.assertFalse(is_valid)


class TestSSRFPrevention(unittest.TestCase):
    """Tests for SSRF prevention mechanisms."""

    def test_send_to_discord_validates_url(self):
        """Should raise ValueError for invalid URLs before sending request."""
        malicious_url = "http://localhost:8080/admin/delete"

        # We don't need to mock requests.post because it should fail before calling it
        with self.assertRaises(ValueError) as cm:
            send_to_discord_with_retry(malicious_url, data={"content": "test"})

        self.assertIn("Invalid webhook URL", str(cm.exception))

    @patch('requests.post')
    def test_send_to_discord_allows_valid_url(self, mock_post):
        """Should allow valid Discord URLs."""
        valid_url = "https://discord.com/api/webhooks/123/abc"

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        send_to_discord_with_retry(valid_url, data={"content": "test"})

        mock_post.assert_called_once()


class TestWebhookSanitization(unittest.TestCase):
    """Tests for webhook URL sanitization for logging."""
    
    def test_sanitize_webhook_for_logging(self):
        """Should redact the token portion of webhook URLs."""
        url = "https://discord.com/api/webhooks/123456789/secrettoken"
        result = sanitize_webhook_for_logging(url)
        self.assertIn("[REDACTED]", result)
        self.assertIn("123456789", result)
        self.assertNotIn("secrettoken", result)
    
    def test_sanitize_empty_url(self):
        """Should handle empty URLs."""
        result = sanitize_webhook_for_logging("")
        self.assertEqual(result, "")


if __name__ == "__main__":
    # Run tests
    print("Running ComfyUI-DiscordSend utility tests...\n")
    unittest.main(verbosity=2)
