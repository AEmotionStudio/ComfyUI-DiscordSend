
import unittest
from unittest.mock import MagicMock, patch
import sys
import os

# Mock modules that might be missing in the environment or causing issues
sys.modules["folder_paths"] = MagicMock()
sys.modules["comfy"] = MagicMock()
sys.modules["server"] = MagicMock()
sys.modules["torch"] = MagicMock()
sys.modules["numpy"] = MagicMock()
sys.modules["cv2"] = MagicMock()

# Import the module under test
sys.path.append(os.getcwd())

from shared.discord.webhook_client import DiscordWebhookClient, send_to_discord_with_retry, sanitize_token_from_text

class TestWebhookSecurity(unittest.TestCase):
    def test_token_leak_in_client_error(self):
        """
        Test that webhook tokens are NOT leaked in client error details.
        """
        webhook_url = "https://discord.com/api/webhooks/123456789/SuperSecretToken123"
        client = DiscordWebhookClient(webhook_url)

        # Mock response to simulate a 400 error that echoes the URL
        mock_response = MagicMock()
        mock_response.status_code = 400
        # Simulate an API that echoes the request URL in the error body
        mock_response.text = f"Error processing request to {webhook_url}: Invalid payload"
        mock_response.content = mock_response.text.encode('utf-8')

        with patch('requests.post', return_value=mock_response):
            success, response = client.send_message("test")

            self.assertFalse(success)
            error_details = response.get("details", "")

            print(f"\nDEBUG: Error details: {error_details}")
            self.assertNotIn("SuperSecretToken123", error_details)
            self.assertIn("[REDACTED]", error_details)

    def test_sanitize_token_from_text(self):
        """
        Test the standalone sanitization function.
        """
        webhook_url = "https://discord.com/api/webhooks/123456789/MySecretToken-Part2"

        # Test 1: Simple URL in text
        text = f"Failed to send to {webhook_url}"
        sanitized = sanitize_token_from_text(text, webhook_url)
        self.assertNotIn("MySecretToken-Part2", sanitized)
        self.assertIn("[REDACTED]", sanitized)

        # Test 2: Token embedded in other text
        text = "Some error occurred with token MySecretToken-Part2 processing"
        sanitized = sanitize_token_from_text(text, webhook_url)
        self.assertNotIn("MySecretToken-Part2", sanitized)
        self.assertIn("[REDACTED]", sanitized)

        # Test 3: Multiple occurrences
        text = f"URL: {webhook_url}, Retry: {webhook_url}"
        sanitized = sanitize_token_from_text(text, webhook_url)
        self.assertNotIn("MySecretToken-Part2", sanitized)
        self.assertEqual(sanitized.count("[REDACTED]"), 2)

if __name__ == '__main__':
    unittest.main()
