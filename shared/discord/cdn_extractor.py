"""
Discord CDN URL extraction utilities for ComfyUI-DiscordSend

Provides functions for extracting CDN URLs from Discord responses
and creating/sending URL text files.
"""

from typing import List, Tuple, Optional, Any
from uuid import uuid4


def extract_cdn_urls_from_response(
    response: Any,
    exclude_json: bool = True
) -> List[Tuple[str, str]]:
    """
    Extract CDN URLs from a Discord webhook response.

    Args:
        response: Response object from Discord API (must have .status_code and .json())
        exclude_json: Whether to exclude .json files from results

    Returns:
        List of (filename, url) tuples
    """
    cdn_urls = []

    if response.status_code != 200:
        return cdn_urls

    try:
        response_data = response.json()
        print(f"Received JSON response from Discord with "
              f"{len(response_data) if isinstance(response_data, dict) else 'invalid'} fields")

        if "attachments" in response_data and isinstance(response_data["attachments"], list):
            print(f"Found {len(response_data['attachments'])} attachments in Discord response")

            for idx, attachment in enumerate(response_data["attachments"]):
                if "url" in attachment and "filename" in attachment:
                    filename = attachment["filename"]
                    url = attachment["url"]

                    # Filter out workflow JSON files if requested
                    if exclude_json and filename.endswith(".json"):
                        print(f"Skipping JSON file: {filename}")
                        continue

                    cdn_urls.append((filename, url))
                    print(f"Extracted CDN URL for attachment {idx + 1}: {url}")
                else:
                    print(f"Attachment {idx + 1} missing URL or filename: {attachment.keys()}")

            print(f"Total CDN URLs collected: {len(cdn_urls)}")

    except Exception as e:
        print(f"Error extracting CDN URLs from response: {e}")

    return cdn_urls


def create_cdn_urls_content(
    urls: List[Tuple[str, str]],
    header: str = "# Discord CDN URLs\n\n"
) -> str:
    """
    Create text content from a list of CDN URLs.

    Args:
        urls: List of (filename, url) tuples
        header: Header text for the content

    Returns:
        Formatted text content
    """
    content = header
    for idx, (filename, url) in enumerate(urls):
        content += f"{idx + 1}. {filename}: {url}\n"
    return content


def send_cdn_urls_file(
    webhook_url: str,
    urls: List[Tuple[str, str]],
    send_func: Any,
    message: str = "Discord CDN URLs for the uploaded files:",
    filename_prefix: str = "cdn_urls"
) -> bool:
    """
    Create and send a text file containing CDN URLs to Discord.

    Args:
        webhook_url: Discord webhook URL
        urls: List of (filename, url) tuples
        send_func: Function to send to Discord (send_to_discord_with_retry)
        message: Message to accompany the file
        filename_prefix: Prefix for the generated filename

    Returns:
        True if successful, False otherwise
    """
    if not urls:
        print("No CDN URLs to send")
        return False

    try:
        # Create the text file content
        url_text_content = create_cdn_urls_content(urls)

        # Create a unique filename for the text file
        urls_filename = f"{filename_prefix}-{uuid4()}.txt"

        # Prepare the request with just the URL file
        url_files = {"file": (urls_filename, url_text_content.encode('utf-8'))}
        url_data = {"content": message}

        # Send a follow-up message with just the URLs text file
        url_response = send_func(
            webhook_url,
            files=url_files,
            data=url_data
        )

        if url_response.status_code in [200, 204]:
            print(f"Successfully sent CDN URLs text file to Discord")
            return True
        else:
            print(f"Error sending CDN URLs text file: Status code {url_response.status_code}")
            return False

    except Exception as e:
        print(f"Error creating or sending CDN URLs text file: {e}")
        return False


def collect_and_send_cdn_urls(
    response: Any,
    webhook_url: str,
    send_func: Any,
    save_cdn_urls: bool,
    existing_urls: Optional[List[Tuple[str, str]]] = None,
    message: str = "Discord CDN URLs for the uploaded files:"
) -> List[Tuple[str, str]]:
    """
    Convenience function to extract CDN URLs from a response and optionally send them.

    Args:
        response: Discord webhook response
        webhook_url: Webhook URL for sending the URLs file
        send_func: Function to send to Discord
        save_cdn_urls: Whether to extract and save CDN URLs
        existing_urls: Existing URLs to append to (for batch operations)
        message: Message to accompany the URLs file

    Returns:
        List of all collected CDN URLs
    """
    if existing_urls is None:
        existing_urls = []

    if not save_cdn_urls:
        return existing_urls

    # Extract URLs from this response
    new_urls = extract_cdn_urls_from_response(response)
    all_urls = existing_urls + new_urls

    return all_urls
