"""
Discord Integration Utilities

Provides webhook client, message building, and CDN URL handling.
"""

from .webhook_client import (
    DiscordWebhookClient,
    validate_webhook_url,
    sanitize_webhook_for_logging,
    send_to_discord_with_retry,
    validate_file_for_discord
)
from .message_builder import (
    build_metadata_section,
    build_prompt_section,
    build_discord_message,
    validate_message_content,
    format_file_info,
    format_file_size
)
from .cdn_extractor import (
    extract_cdn_urls_from_response,
    create_cdn_urls_content,
    send_cdn_urls_file,
    collect_and_send_cdn_urls
)

__all__ = [
    # Webhook client
    'DiscordWebhookClient',
    'validate_webhook_url',
    'sanitize_webhook_for_logging',
    'send_to_discord_with_retry',
    'validate_file_for_discord',
    # Message building
    'build_metadata_section',
    'build_prompt_section',
    'build_discord_message',
    'validate_message_content',
    'format_file_info',
    'format_file_size',
    # CDN extraction
    'extract_cdn_urls_from_response',
    'create_cdn_urls_content',
    'send_cdn_urls_file',
    'collect_and_send_cdn_urls',
]
