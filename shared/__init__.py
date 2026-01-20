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
    send_to_discord_with_retry
)
from .media.image_processing import tensor_to_numpy_uint8
from .github_integration import update_github_cdn_urls
from .logging_config import setup_logging, get_logger

__all__ = [
    # Workflow utilities
    'sanitize_json_for_export',
    'extract_prompts_from_workflow',
    'WorkflowBuilder',
    # Discord utilities
    'DiscordWebhookClient',
    'validate_webhook_url',
    'send_to_discord_with_retry',
    # Media utilities
    'tensor_to_numpy_uint8',
    # GitHub integration
    'update_github_cdn_urls',
    # Logging
    'setup_logging',
    'get_logger',
]
