import unittest
import sys
import os
from unittest.mock import MagicMock, patch

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.discord import send_to_discord_with_retry

class TestDiscordAPI(unittest.TestCase):
    """Tests for the Discord API utility with mocked network responses."""

    @patch('requests.post')
    @patch('time.sleep', return_value=None) # Don't actually wait during tests
    def test_retry_on_rate_limit(self, mock_sleep, mock_post):
        """Should retry when receiving a 429 Rate Limit error."""
        # Setup mock responses: first is 429, second is 200
        mock_429 = MagicMock()
        mock_429.status_code = 429
        mock_429.text = "Too many requests"
        mock_429.json.return_value = {"retry_after": 0.1}
        
        mock_200 = MagicMock()
        mock_200.status_code = 200
        
        mock_post.side_effect = [mock_429, mock_200]

        response = send_to_discord_with_retry(
            "https://discord.com/api/webhooks/123/abc",
            data={"content": "test message"},
            max_retries=2
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(mock_post.call_count, 2)
        mock_sleep.assert_called()

    @patch('requests.post')
    def test_no_retry_on_400(self, mock_post):
        """Should not retry and return response for 400 Bad Request."""
        mock_400 = MagicMock()
        mock_400.status_code = 400
        mock_400.text = "Bad Request"
        mock_post.return_value = mock_400

        response = send_to_discord_with_retry(
            "https://discord.com/api/webhooks/123/abc",
            data={"content": "test message"}
        )
        
        self.assertEqual(response.status_code, 400)
        self.assertEqual(mock_post.call_count, 1)

    @patch('requests.post')
    @patch('time.sleep', return_value=None)
    def test_exhaust_retries(self, mock_sleep, mock_post):
        """Should return the last failed response after exhaust all retries."""
        mock_500 = MagicMock()
        mock_500.status_code = 500
        mock_post.return_value = mock_500

        # Should return the last 500 response
        response = send_to_discord_with_retry(
            "https://discord.com/api/webhooks/131072/abc", # Valid ID
            data={"content": "test message"},
            max_retries=3
        )
        
        self.assertEqual(response.status_code, 500)
        self.assertEqual(mock_post.call_count, 3) 
        self.assertEqual(mock_sleep.call_count, 2) # Sleeps between attempts (1st to 2nd, 2nd to 3rd)

    @patch('requests.post')
    @patch('time.sleep', return_value=None)
    def test_raise_exception_on_network_failure(self, mock_sleep, mock_post):
        """Should raise RequestException if all retries hit network errors."""
        import requests
        mock_post.side_effect = requests.exceptions.ConnectionError("Failed")
        
        with self.assertRaises(requests.exceptions.ConnectionError):
            send_to_discord_with_retry(
                "https://discord.com/api/webhooks/123/abc",
                data={"content": "test"},
                max_retries=2
            )

if __name__ == "__main__":
    unittest.main()
