"""
Path utilities for ComfyUI-DiscordSend

Provides functions for handling output directories and file paths.
"""

import os
from typing import Optional


def get_output_directory(
    save_output: bool,
    comfy_output_dir: str,
    temp_dir: str,
    subfolder: str = "discord_output"
) -> str:
    """
    Determine the appropriate output directory based on save settings.

    Args:
        save_output: Whether files should be saved permanently
        comfy_output_dir: ComfyUI's output directory path
        temp_dir: ComfyUI's temporary directory path
        subfolder: Subfolder name within output directory (default: "discord_output")

    Returns:
        Path to the destination directory
    """
    if save_output:
        # Create output subfolder in the ComfyUI output directory
        dest_folder = os.path.join(comfy_output_dir, subfolder)
        os.makedirs(dest_folder, exist_ok=True)
    else:
        # Use ComfyUI's temporary directory for preview-only files
        dest_folder = temp_dir
        os.makedirs(dest_folder, exist_ok=True)
        print(f"Using temporary directory for preview: {dest_folder}")

    return dest_folder


def ensure_directory_exists(path: str) -> str:
    """
    Ensure a directory exists, creating it if necessary.

    Args:
        path: Directory path to ensure exists

    Returns:
        The same path (for chaining)
    """
    os.makedirs(path, exist_ok=True)
    return path


def get_unique_filepath(
    directory: str,
    filename: str,
    extension: str,
    counter: Optional[int] = None
) -> str:
    """
    Generate a unique filepath, optionally with a counter.

    Args:
        directory: Base directory
        filename: Base filename (without extension)
        extension: File extension (with or without leading dot)
        counter: Optional counter to append to filename

    Returns:
        Full filepath
    """
    # Ensure extension has leading dot
    if not extension.startswith("."):
        extension = "." + extension

    if counter is not None:
        full_filename = f"{filename}_{counter:05d}{extension}"
    else:
        full_filename = f"{filename}{extension}"

    return os.path.join(directory, full_filename)


def validate_path_is_safe(path: str) -> None:
    """
    Validate that a path is safe to write to.

    Checks:
    - Path is not a symlink (to prevent overwriting targets)
    - Parent directories are not symlinks (to prevent path traversal via symlinks)

    Args:
        path: File path to validate

    Raises:
        ValueError: If path is unsafe
    """
    # Check if path exists and is a symlink
    if os.path.islink(path):
        raise ValueError(f"Security error: Output path '{path}' is a symlink. Overwriting symlinks is not allowed.")

    # Check if any parent component is a symlink or if the path resolves unexpectedly
    # Realpath resolves all symlinks
    real_path = os.path.realpath(path)
    abs_path = os.path.abspath(path)

    # If the real path and absolute path differ, it means a symlink was followed
    # Note: We only care if the directory structure involves symlinks that we didn't explicitly authorize.
    # ComfyUI output directories might be symlinks themselves in some valid setups,
    # but strictly speaking, allowing writes through symlinks is dangerous if we don't own the link.
    # For maximum security as requested, we block writing through any symlink in the path.

    # However, simply checking real_path != abs_path might be too aggressive if the user
    # legitimately has their ComfyUI folder symlinked.
    # A more targeted check for the "parent directory symlink" attack described:
    # "An attacker can create /output/evil_dir -> /etc/"

    # We should iterate through the path components and check if any is a link
    directory = os.path.dirname(path)
    if os.path.isdir(directory):
        # If the directory exists, check if it or its parents are symlinks
        # But checking every parent up to root is overkill and might break valid setups.
        # The specific concern is that 'directory' itself (or a sub-component within output) is a symlink.

        # Check if the immediate parent directory is a symlink
        if os.path.islink(directory):
             raise ValueError(f"Security error: Parent directory '{directory}' is a symlink. Writing through directory symlinks is not allowed.")

        # Also check if realpath deviates significantly, which catches nested symlinks
        # But we need to be careful. Let's stick to the reviewer's suggestion:
        # "The function should use os.path.realpath() to resolve and validate the entire path."

        # If the directory exists, we can check if it's a symlink or if any part of it inside the output root is a symlink.
        # But we don't know the output root here easily.

        # Let's verify that the directory path provided is the same as its realpath
        # This effectively bans symlinks in the directory path.
        real_dir = os.path.realpath(directory)
        abs_dir = os.path.abspath(directory)

        if real_dir != abs_dir:
             # This means there is a symlink somewhere in the directory path.
             # This is a strict check but safe for security.
             raise ValueError(f"Security error: Path resolution mismatch for '{directory}'. "
                              f"Symlinks in output paths are not allowed (Real: {real_dir}, Abs: {abs_dir}).")
