"""
Discord message building utilities for ComfyUI-DiscordSend

Provides functions for constructing Discord messages with metadata,
prompts, and other formatted content.
"""

from typing import Dict, Any, Optional, Tuple, List


def build_metadata_section(
    info_dict: Dict[str, Any],
    include_date: bool = True,
    include_time: bool = True,
    include_dimensions: bool = True,
    include_format: bool = True,
    file_format: Optional[str] = None,
    frame_rate: Optional[float] = None,
    section_title: str = "Information"
) -> str:
    """
    Build a formatted metadata section for Discord messages.

    Args:
        info_dict: Dictionary containing metadata (date, time, dimensions, etc.)
        include_date: Whether to include date if present
        include_time: Whether to include time if present
        include_dimensions: Whether to include dimensions if present
        include_format: Whether to include format information
        file_format: File format string (e.g., "png", "mp4")
        frame_rate: Frame rate for video (optional)
        section_title: Title for the section (e.g., "Image Information", "Video Info")

    Returns:
        Formatted metadata string, or empty string if no metadata
    """
    metadata_lines = []

    if include_date and "date" in info_dict:
        metadata_lines.append(f"**Date:** {info_dict['date']}")

    if include_time and "time" in info_dict:
        metadata_lines.append(f"**Time:** {info_dict['time']}")

    if include_dimensions and "dimensions" in info_dict:
        metadata_lines.append(f"**Dimensions:** {info_dict['dimensions']}")

    if frame_rate is not None:
        metadata_lines.append(f"**Frame Rate:** {frame_rate} fps")

    if include_format and file_format:
        metadata_lines.append(f"**Format:** {file_format.upper()}")

    if not metadata_lines:
        return ""

    section = f"\n\n**{section_title}:**\n"
    section += "\n".join(metadata_lines)
    return section


def build_prompt_section(
    positive_prompt: Optional[str],
    negative_prompt: Optional[str],
    section_title: str = "Generation Prompts"
) -> str:
    """
    Build a formatted prompts section for Discord messages.

    Args:
        positive_prompt: The positive/main prompt text
        negative_prompt: The negative prompt text
        section_title: Title for the section

    Returns:
        Formatted prompt string, or empty string if no prompts
    """
    # Validate and normalize prompts
    if positive_prompt is not None and not isinstance(positive_prompt, str):
        positive_prompt = str(positive_prompt)
    if negative_prompt is not None and not isinstance(negative_prompt, str):
        negative_prompt = str(negative_prompt)

    has_positive = isinstance(positive_prompt, str) and positive_prompt.strip()
    has_negative = isinstance(negative_prompt, str) and negative_prompt.strip()

    if not has_positive and not has_negative:
        return ""

    section = f"\n\n**{section_title}:**\n"

    if has_positive:
        section += f"**Positive:**\n```\n{positive_prompt.strip()}\n```\n"

    if has_negative:
        section += f"**Negative:**\n```\n{negative_prompt.strip()}\n```\n"

    return section


def build_discord_message(
    base_message: str = "",
    metadata_section: str = "",
    prompt_section: str = "",
    additional_sections: Optional[List[str]] = None,
    max_length: int = 2000
) -> str:
    """
    Build a complete Discord message from components.

    Args:
        base_message: The main message content
        metadata_section: Pre-built metadata section
        prompt_section: Pre-built prompt section
        additional_sections: List of additional section strings
        max_length: Maximum message length (Discord limit is 2000)

    Returns:
        Complete formatted message, truncated if necessary
    """
    parts = [base_message] if base_message else []

    if metadata_section:
        parts.append(metadata_section)

    if prompt_section:
        parts.append(prompt_section)

    if additional_sections:
        parts.extend(additional_sections)

    message = "".join(parts)

    # Truncate if necessary
    if len(message) > max_length:
        truncation_notice = "\n...[Message truncated]"
        message = message[:max_length - len(truncation_notice)] + truncation_notice

    return message


def validate_message_content(message: str) -> Tuple[bool, str]:
    """
    Validate Discord message content.

    Args:
        message: Message content to validate

    Returns:
        Tuple of (is_valid, validation_message)
    """
    if not message:
        return True, "Empty message (valid for file-only uploads)"

    if len(message) > 2000:
        return False, f"Message exceeds 2000 character limit ({len(message)} chars)"

    # Check for required sections (informational)
    has_prompts = "Generation Prompts" in message

    info_parts = []
    info_parts.append(f"Message has {message.count(chr(10))} lines")

    if not has_prompts:
        info_parts.append("WARNING: Message does NOT contain 'Generation Prompts' section")

    return True, "\n".join(info_parts)


def format_file_info(
    filename: str,
    file_size: int,
    mime_type: Optional[str] = None
) -> str:
    """
    Format file information for logging/display.

    Args:
        filename: Name of the file
        file_size: Size in bytes
        mime_type: MIME type of the file

    Returns:
        Formatted string with file information
    """
    size_str = format_file_size(file_size)
    info = f"File: {filename} ({size_str})"
    if mime_type:
        info += f" [{mime_type}]"
    return info


def format_file_size(size_bytes: int) -> str:
    """
    Format file size in human-readable format.

    Args:
        size_bytes: Size in bytes

    Returns:
        Formatted string (e.g., "1.5 MB", "256 KB")
    """
    if size_bytes < 1024:
        return f"{size_bytes} bytes"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"
