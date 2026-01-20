"""
Video format utilities for ComfyUI-DiscordSend

Provides format detection, extension mapping, and validation.
"""

import os
from typing import Tuple, Optional


def parse_format_string(format_str: str) -> Tuple[str, str]:
    """
    Parse a format string into type and extension.

    Args:
        format_str: Format string like "video/h264-mp4" or "image/gif"

    Returns:
        Tuple of (format_type, format_extension)
    """
    if "/" in format_str:
        format_type, format_ext = format_str.split("/", 1)
    else:
        format_type = "video"
        format_ext = format_str

    return format_type, format_ext


def normalize_video_extension(format_str: str) -> str:
    """
    Normalize a format string to a file extension.

    Args:
        format_str: Format string like "video/h264-mp4"

    Returns:
        Normalized extension (e.g., "mp4", "webm", "gif")
    """
    _, format_ext = parse_format_string(format_str)

    # Map format strings to extensions
    extension_map = {
        "h264-mp4": "mp4",
        "h265-mp4": "mp4",
        "vp9-webm": "webm",
        "prores": "mov",
    }

    return extension_map.get(format_ext, format_ext)


def get_mime_type(extension: str) -> str:
    """
    Get MIME type for a video extension.

    Args:
        extension: File extension (without dot)

    Returns:
        MIME type string
    """
    mime_types = {
        "mp4": "video/mp4",
        "webm": "video/webm",
        "gif": "image/gif",
        "mov": "video/quicktime",
        "avi": "video/x-msvideo",
        "mkv": "video/x-matroska",
    }
    return mime_types.get(extension.lower(), "application/octet-stream")


def validate_video_for_discord(file_path: str, max_size_mb: int = 25) -> Tuple[bool, str]:
    """
    Validate that a video file is compatible with Discord.

    Args:
        file_path: Path to the video file
        max_size_mb: Maximum file size in megabytes (default 25MB for Discord)

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

    max_size = max_size_mb * 1024 * 1024
    if file_size > max_size:
        return False, f"File exceeds Discord's size limit of {max_size_mb}MB ({file_size / (1024*1024):.2f}MB)"

    ext = os.path.splitext(file_path)[1].lower().lstrip('.')

    if ext in ['mp4', 'webm', 'gif']:
        return True, "Valid"
    elif ext in ['mov']:
        return False, "MOV files may need conversion for Discord compatibility"
    elif ext in ['png', 'apng']:
        return False, "PNG/APNG sequence may need compilation for Discord"
    else:
        return False, f"Unknown format '{ext}' - may not be compatible with Discord"


def is_animated_format(extension: str) -> bool:
    """
    Check if a format supports animation.

    Args:
        extension: File extension (without dot)

    Returns:
        True if the format supports animation
    """
    animated_formats = {'gif', 'webp', 'mp4', 'webm', 'mov', 'avi', 'mkv', 'apng'}
    return extension.lower() in animated_formats


def supports_alpha(extension: str) -> bool:
    """
    Check if a format supports alpha channel (transparency).

    Args:
        extension: File extension (without dot)

    Returns:
        True if the format supports alpha
    """
    alpha_formats = {'webm', 'gif', 'webp', 'png', 'apng', 'mov'}
    return extension.lower() in alpha_formats
