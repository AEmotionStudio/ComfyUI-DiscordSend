"""
ComfyUI-DiscordSend Shared Utilities

This package contains shared utilities used by both ComfyUI nodes and the Discord bot.
Organized into subpackages:
- discord: Discord webhook and message utilities
- media: Image and video processing utilities
- workflow: ComfyUI workflow manipulation utilities
"""

# Re-export commonly used utilities for convenience
from .workflow.sanitizer import sanitize_json_for_export
from .workflow.prompt_extractor import extract_prompts_from_workflow
from .workflow.workflow_builder import WorkflowBuilder
from .discord.webhook_client import (
    DiscordWebhookClient,
    validate_webhook_url,
    send_to_discord_with_retry,
    sanitize_token_from_text
)
from .discord.message_builder import (
    build_metadata_section,
    build_prompt_section,
    build_discord_message,
    format_file_size
)
from .discord.cdn_extractor import (
    extract_cdn_urls_from_response,
    send_cdn_urls_file
)
from .media.image_processing import tensor_to_numpy_uint8
from .github_integration import update_github_cdn_urls
from .logging_config import setup_logging, get_logger
from .filename_utils import build_filename_with_metadata, get_timestamp_string
from .path_utils import get_output_directory, ensure_directory_exists

__all__ = [
    # Workflow utilities
    'sanitize_json_for_export',
    'extract_prompts_from_workflow',
    'WorkflowBuilder',
    # Discord utilities
    'DiscordWebhookClient',
    'validate_webhook_url',
    'send_to_discord_with_retry',
    'sanitize_token_from_text',
    # Discord message building
    'build_metadata_section',
    'build_prompt_section',
    'build_discord_message',
    'format_file_size',
    # CDN extraction
    'extract_cdn_urls_from_response',
    'send_cdn_urls_file',
    # Media utilities
    'tensor_to_numpy_uint8',
    # GitHub integration
    'update_github_cdn_urls',
    # Logging
    'setup_logging',
    'get_logger',
    # Filename utilities
    'build_filename_with_metadata',
    'get_timestamp_string',
    # Path utilities
    'get_output_directory',
    'ensure_directory_exists',
]
