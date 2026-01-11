"""
Discord API Utilities for ComfyUI-DiscordSend

Provides a client for interacting with Discord webhooks and validation utilities.
"""

import os
import re
import time
from io import BytesIO
from typing import Any, Dict, List, Optional, Tuple

import requests


# Discord webhook URL patterns
WEBHOOK_URL_PATTERNS = [
    r"https?://(?:www\.)?discord(?:app)?\.com/api/webhooks/\d+/[\w-]+",
    r"https?://(?:www\.)?discordapp\.com/api/webhooks/\d+/[\w-]+",
]


def validate_webhook_url(url: str) -> Tuple[bool, str]:
    """
    Validate a Discord webhook URL.
    
    Args:
        url: The webhook URL to validate
        
    Returns:
        Tuple of (is_valid, message)
    """
    if not url:
        return False, "Webhook URL is empty"
    
    if not url.startswith("http"):
        return False, "Webhook URL must start with http:// or https://"
    
    # Check against known patterns
    for pattern in WEBHOOK_URL_PATTERNS:
        if re.match(pattern, url, re.IGNORECASE):
            return True, "Valid Discord webhook URL"
    
    # More lenient check
    if "discord" in url.lower() and "webhook" in url.lower():
        return True, "Appears to be a Discord webhook URL"
    
    return False, "URL does not appear to be a valid Discord webhook URL"


def sanitize_webhook_for_logging(url: str) -> str:
    """
    Sanitize a webhook URL for safe logging (hide the token portion).
    
    Args:
        url: The webhook URL
        
    Returns:
        Sanitized URL safe for logging
    """
    if not url:
        return ""
    
    # Pattern: https://discord.com/api/webhooks/{id}/{token}
    match = re.match(r"(https?://[^/]+/api/webhooks/\d+/)(.+)", url)
    if match:
        return f"{match.group(1)}[REDACTED]"
    
    return "[REDACTED_WEBHOOK_URL]"


class DiscordWebhookClient:
    """
    Client for sending messages and files to Discord via webhooks.
    
    Features:
    - Automatic retry with exponential backoff
    - Rate limit handling
    - File size validation
    - Error handling with sanitized logging
    """
    
    # Discord limits
    MAX_FILE_SIZE = 25 * 1024 * 1024  # 25MB for regular users
    MAX_FILES_PER_MESSAGE = 10
    MAX_MESSAGE_LENGTH = 2000
    
    def __init__(self, webhook_url: str, max_retries: int = 3):
        """
        Initialize the Discord webhook client.
        
        Args:
            webhook_url: The Discord webhook URL
            max_retries: Maximum number of retry attempts for failed requests
        """
        self.webhook_url = webhook_url
        self.max_retries = max_retries
        self._validated = False
    
    def validate(self) -> Tuple[bool, str]:
        """Validate the webhook URL."""
        is_valid, message = validate_webhook_url(self.webhook_url)
        self._validated = is_valid
        return is_valid, message
    
    def send_message(
        self,
        content: str = "",
        files: Optional[List[Tuple[str, bytes, str]]] = None,
        embeds: Optional[List[Dict]] = None
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Send a message to Discord.
        
        Args:
            content: Text message content
            files: List of (filename, file_bytes, content_type) tuples
            embeds: List of embed dictionaries
            
        Returns:
            Tuple of (success, response_data)
        """
        if not self.webhook_url:
            return False, {"error": "No webhook URL configured"}
        
        # Validate URL if not already done
        if not self._validated:
            is_valid, message = self.validate()
            if not is_valid:
                return False, {"error": message}
        
        # Truncate message if too long
        if content and len(content) > self.MAX_MESSAGE_LENGTH:
            content = content[:self.MAX_MESSAGE_LENGTH - 3] + "..."
        
        # Prepare request
        data = {}
        if content:
            data["content"] = content
        if embeds:
            data["embeds"] = embeds
        
        # Prepare files
        request_files = None
        if files:
            request_files = []
            for i, (filename, file_bytes, content_type) in enumerate(files):
                # Validate file size
                if len(file_bytes) > self.MAX_FILE_SIZE:
                    continue  # Skip oversized files
                
                request_files.append(
                    (f"file{i}", (filename, BytesIO(file_bytes), content_type))
                )
            
            if len(request_files) > self.MAX_FILES_PER_MESSAGE:
                request_files = request_files[:self.MAX_FILES_PER_MESSAGE]
        
        # Send with retry logic
        return self._send_with_retry(data, request_files)
    
    def send_file(
        self,
        file_path: str,
        message: str = "",
        additional_files: Optional[List[str]] = None
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Send a file from disk to Discord.
        
        Args:
            file_path: Path to the file to send
            message: Optional message to accompany the file
            additional_files: Optional list of additional file paths
            
        Returns:
            Tuple of (success, response_data)
        """
        files = []
        
        # Add main file
        if os.path.exists(file_path):
            file_size = os.path.getsize(file_path)
            if file_size <= self.MAX_FILE_SIZE:
                with open(file_path, "rb") as f:
                    filename = os.path.basename(file_path)
                    content_type = self._get_content_type(filename)
                    files.append((filename, f.read(), content_type))
        
        # Add additional files
        if additional_files:
            for path in additional_files:
                if os.path.exists(path):
                    file_size = os.path.getsize(path)
                    if file_size <= self.MAX_FILE_SIZE:
                        with open(path, "rb") as f:
                            filename = os.path.basename(path)
                            content_type = self._get_content_type(filename)
                            files.append((filename, f.read(), content_type))
        
        if not files:
            return False, {"error": "No valid files to send"}
        
        return self.send_message(content=message, files=files)
    
    def _send_with_retry(
        self,
        data: Dict,
        files: Optional[List] = None
    ) -> Tuple[bool, Dict[str, Any]]:
        """Send request with retry logic."""
        last_error = None
        
        for attempt in range(self.max_retries):
            try:
                if files:
                    response = requests.post(
                        self.webhook_url,
                        data={"payload_json": str(data)} if data else None,
                        files=files,
                        timeout=60
                    )
                else:
                    response = requests.post(
                        self.webhook_url,
                        json=data,
                        timeout=30
                    )
                
                # Handle rate limiting
                if response.status_code == 429:
                    retry_after = response.json().get("retry_after", 1)
                    time.sleep(retry_after)
                    continue
                
                # Success
                if response.status_code in [200, 204]:
                    try:
                        return True, response.json() if response.content else {}
                    except:
                        return True, {}
                
                # Client errors (don't retry)
                if 400 <= response.status_code < 500:
                    return False, {
                        "error": f"Discord API error: {response.status_code}",
                        "details": response.text[:500]
                    }
                
                # Server errors (retry)
                last_error = f"Discord API returned {response.status_code}"
                
            except requests.exceptions.Timeout:
                last_error = "Request timed out"
            except requests.exceptions.RequestException as e:
                last_error = str(e)
            
            # Exponential backoff
            if attempt < self.max_retries - 1:
                time.sleep(2 ** attempt)
        
        return False, {"error": last_error or "Unknown error"}
    
    def _get_content_type(self, filename: str) -> str:
        """Get content type based on file extension."""
        ext = os.path.splitext(filename)[1].lower()
        content_types = {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".gif": "image/gif",
            ".webp": "image/webp",
            ".mp4": "video/mp4",
            ".webm": "video/webm",
            ".mov": "video/quicktime",
            ".json": "application/json",
            ".txt": "text/plain",
        }
        return content_types.get(ext, "application/octet-stream")


def validate_file_for_discord(file_path: str) -> Tuple[bool, str]:
    """
    Validate that a file is compatible with Discord uploads.
    
    Args:
        file_path: Path to the file
        
    Returns:
        Tuple of (is_valid, message)
    """
    if not os.path.exists(file_path):
        return False, f"File does not exist: {file_path}"
    
    file_size = os.path.getsize(file_path)
    
    if file_size == 0:
        return False, "File is empty"
    
    if file_size < 1024:
        return False, f"File is suspiciously small: {file_size} bytes"
    
    max_size = 25 * 1024 * 1024  # 25MB
    if file_size > max_size:
        return False, f"File exceeds Discord's size limit: {file_size} bytes (max {max_size} bytes)"
    
    # Check extension
    ext = os.path.splitext(file_path)[1].lower().lstrip('.')
    supported_formats = ['png', 'jpg', 'jpeg', 'gif', 'webp', 'mp4', 'webm', 'mov']
    
    if ext in supported_formats:
        return True, f"Valid {ext.upper()} file for Discord"
    else:
        return False, f"Format {ext} may not be fully supported by Discord"


def send_to_discord_with_retry(
    webhook_url: str,
    files: Optional[List] = None,
    data: Optional[Dict] = None,
    json_data: Optional[Dict] = None,
    max_retries: int = 3,
    timeout: int = 60
) -> requests.Response:
    """
    Send a request to Discord webhook with retry logic.
    
    This is a drop-in replacement for requests.post() with added retry logic,
    rate limit handling, and exponential backoff.
    
    Args:
        webhook_url: The Discord webhook URL
        files: Files to upload (same format as requests.post)
        data: Form data (same format as requests.post)
        json_data: JSON data (same format as requests.post)
        max_retries: Maximum number of retry attempts
        timeout: Request timeout in seconds
        
    Returns:
        The response object from the successful request
        
    Raises:
        requests.exceptions.RequestException: If all retries fail
    """
    last_exception = None
    
    for attempt in range(max_retries):
        try:
            if files:
                response = requests.post(
                    webhook_url,
                    files=files,
                    data=data,
                    timeout=timeout
                )
            elif json_data:
                response = requests.post(
                    webhook_url,
                    json=json_data,
                    timeout=timeout
                )
            else:
                response = requests.post(
                    webhook_url,
                    data=data,
                    timeout=timeout
                )
            
            # Handle rate limiting
            if response.status_code == 429:
                retry_after = 1
                try:
                    retry_after = response.json().get("retry_after", 1)
                except:
                    pass
                print(f"Rate limited by Discord, waiting {retry_after}s before retry...")
                time.sleep(retry_after)
                continue
            
            # Success or client error (don't retry client errors)
            if response.status_code < 500:
                return response
            
            # Server error - retry
            print(f"Discord server error {response.status_code}, attempt {attempt + 1}/{max_retries}")
            
        except requests.exceptions.Timeout:
            print(f"Request timeout, attempt {attempt + 1}/{max_retries}")
            last_exception = requests.exceptions.Timeout("Discord request timed out")
        except requests.exceptions.RequestException as e:
            print(f"Request error: {e}, attempt {attempt + 1}/{max_retries}")
            last_exception = e
        
        # Exponential backoff before retry
        if attempt < max_retries - 1:
            wait_time = 2 ** attempt
            time.sleep(wait_time)
    
    # If we get here, all retries failed
    if last_exception:
        raise last_exception
    
    # Return the last response even if it was an error
    return response

