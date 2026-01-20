"""
Filename utilities for ComfyUI-DiscordSend

Provides functions for building filenames with date, time, and dimension metadata.
"""

import time
from typing import Dict, Optional, Tuple, Any


def build_filename_with_metadata(
    prefix: str,
    add_date: bool = False,
    add_time: bool = False,
    add_dimensions: bool = False,
    width: Optional[int] = None,
    height: Optional[int] = None,
    info_dict: Optional[Dict[str, Any]] = None
) -> Tuple[str, Dict[str, Any]]:
    """
    Build a filename with optional date, time, and dimension suffixes.

    Args:
        prefix: The base filename prefix
        add_date: Whether to add the current date (YYYY-MM-DD)
        add_time: Whether to add the current time (HH-MM-SS)
        add_dimensions: Whether to add dimensions (WxH)
        width: Image/video width (required if add_dimensions is True)
        height: Image/video height (required if add_dimensions is True)
        info_dict: Optional dict to update with metadata (creates new if None)

    Returns:
        Tuple of (modified_prefix, info_dict with metadata)
    """
    if info_dict is None:
        info_dict = {}

    metadata_parts = []

    if add_date:
        current_date = time.strftime("%Y-%m-%d")
        metadata_parts.append(current_date)
        info_dict["date"] = current_date
        print(f"Adding date to filename: {current_date}")

    if add_time:
        current_time = time.strftime("%H-%M-%S")
        metadata_parts.append(current_time)
        info_dict["time"] = current_time
        print(f"Adding time to filename: {current_time}")

    if add_dimensions and width is not None and height is not None:
        dim_text = f"{width}x{height}"
        metadata_parts.append(dim_text)
        info_dict["dimensions"] = dim_text
        print(f"Adding dimensions to filename: {dim_text}")

    modified_prefix = prefix
    if metadata_parts:
        metadata_suffix = "_" + "_".join(metadata_parts)
        modified_prefix += metadata_suffix
        print(f"Final metadata suffix: {metadata_suffix}")

    return modified_prefix, info_dict


def get_timestamp_string(include_date: bool = True, include_time: bool = True) -> str:
    """
    Get a formatted timestamp string.

    Args:
        include_date: Include date in format YYYY-MM-DD
        include_time: Include time in format HH-MM-SS

    Returns:
        Formatted timestamp string
    """
    parts = []
    if include_date:
        parts.append(time.strftime("%Y-%m-%d"))
    if include_time:
        parts.append(time.strftime("%H-%M-%S"))
    return "_".join(parts) if parts else ""
