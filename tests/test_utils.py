"""
Unit tests for ComfyUI-DiscordSend utilities.

Run tests with: python -m pytest tests/test_utils.py -v
Or without pytest: python tests/test_utils.py
"""

import sys
import os
import unittest
from unittest.mock import patch, MagicMock
import requests

# Mock dependencies before importing project modules
sys.modules["torch"] = MagicMock()
sys.modules["numpy"] = MagicMock()
sys.modules["cv2"] = MagicMock()
# sys.modules["PIL"] = MagicMock() # PIL might be installed, so maybe not mock it if not needed, but safer to mock if we don't rely on it for these tests

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.workflow.sanitizer import sanitize_json_for_export
from shared.discord.webhook_client import validate_webhook_url, sanitize_webhook_for_logging, send_to_discord_with_retry, DiscordWebhookClient
from shared.github_integration import update_github_cdn_urls


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

    def test_http_url_rejected(self):
        """Should reject HTTP URLs (must be HTTPS)."""
        is_valid, message = validate_webhook_url("http://discord.com/api/webhooks/123/abc")
        self.assertFalse(is_valid)
        self.assertIn("must start with https://", message)

    def test_ip_encoding_urls(self):
        """Should reject alternate IP encodings."""
        self.assertFalse(validate_webhook_url("http://127.0.0.1")[0])
        self.assertFalse(validate_webhook_url("http://0177.0.0.1")[0]) # Octal
        self.assertFalse(validate_webhook_url("http://0x7f.0.0.1")[0]) # Hex
        self.assertFalse(validate_webhook_url("http://[::1]")[0]) # IPv6

    def test_domain_spoofing_urls(self):
        """Should reject domains that contain 'discord' but aren't Discord."""
        self.assertFalse(validate_webhook_url("https://discord.com.evil.co/api/webhooks/123/abc")[0])
        self.assertFalse(validate_webhook_url("https://evil-discord.com/api/webhooks/123/abc")[0])

    def test_path_traversal_urls(self):
        """Should reject path traversal attempts."""
        self.assertFalse(validate_webhook_url("https://discord.com/api/webhooks/123/abc/../../admin")[0])
        self.assertFalse(validate_webhook_url("https://discord.com/api/webhooks/123/abc%2f..%2f..%2fadmin")[0])


class TestSSRFPrevention(unittest.TestCase):
    """Tests for SSRF prevention mechanisms."""

    def test_send_to_discord_validates_url(self):
        """Should raise ValueError for invalid URLs before sending request."""
        malicious_url = "http://localhost:8080/admin/delete"

        # We don't need to mock requests.post because it should fail before calling it
        with self.assertRaises(ValueError) as cm:
            send_to_discord_with_retry(malicious_url, data={"content": "test"})

        self.assertIn("Invalid webhook URL", str(cm.exception))

    @patch('shared.discord.webhook_client.requests.post')
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


class TestDiscordWebhookClient(unittest.TestCase):
    """Tests for DiscordWebhookClient security features."""

    @patch('shared.discord.webhook_client.requests.post')
    def test_exception_token_leakage(self, mock_post):
        """Should redact tokens from exception messages in last_error."""
        token = "SUPER_SECRET_TOKEN"
        url = f"https://discord.com/api/webhooks/123456/{token}"
        client = DiscordWebhookClient(url)

        # Configure mock to raise an exception containing the token
        error_message = f"Max retries exceeded with url: /api/webhooks/123456/{token}"
        mock_post.side_effect = requests.exceptions.ConnectionError(error_message)

        success, result = client.send_message("Test message")

        self.assertFalse(success)
        self.assertIn("error", result)
        self.assertNotIn(token, result["error"])
        self.assertIn("[REDACTED]", result["error"])


class TestGitHubIntegration(unittest.TestCase):
    """Tests for GitHub integration security features."""

    @patch('shared.github_integration.requests.put')
    @patch('shared.github_integration.requests.get')
    def test_github_token_redaction_in_response(self, mock_get, mock_put):
        """Should redact GitHub token from error messages including response text."""
        token = "ghp_SECRET_TOKEN"
        repo = "user/repo"
        file_path = "cdn_urls.md"

        # Mock GET to return 404 (file doesn't exist)
        mock_get_response = MagicMock()
        mock_get_response.status_code = 404
        mock_get.return_value = mock_get_response

        # Mock PUT to fail and return the token in the response text (simulating leak)
        mock_put_response = MagicMock()
        mock_put_response.status_code = 401
        mock_put_response.text = f"Bad credentials: {token} is invalid"
        mock_put.return_value = mock_put_response

        success, message = update_github_cdn_urls(repo, token, file_path, [("test.png", "http://url")])

        self.assertFalse(success)
        self.assertNotIn(token, message)
        self.assertIn("[REDACTED_TOKEN]", message)


if __name__ == "__main__":
    # Run tests
    print("Running ComfyUI-DiscordSend utility tests...\n")
    unittest.main(verbosity=2)
