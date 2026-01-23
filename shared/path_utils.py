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

    # Verify parent directories
    # Walk up the tree to find the first existing directory
    current_dir = os.path.dirname(os.path.abspath(path))

    # Safety valve to prevent infinite loops (though OS paths are finite)
    # We check existence. If it doesn't exist, we check if it's a broken symlink (islink returns True even for broken links)
    # Then move to parent.

    while current_dir and current_dir != os.path.dirname(current_dir): # Until root
        if os.path.islink(current_dir):
            raise ValueError(f"Security error: Path component '{current_dir}' is a symlink. Writing through directory symlinks is not allowed.")

        if os.path.exists(current_dir):
            # Once we hit an existing directory, we verify it matches its realpath
            # This catches hidden symlinks further up that might have been resolved by abspath but diverge in realpath
            real_dir = os.path.realpath(current_dir)
            abs_dir = os.path.abspath(current_dir)

            if real_dir != abs_dir:
                 raise ValueError(f"Security error: Path resolution mismatch for '{current_dir}'. "
                                  f"Symlinks in output paths are not allowed (Real: {real_dir}, Abs: {abs_dir}).")
            # If the existing ancestor is safe, we assume children created under it will be normal directories
            # (unless we have a race condition, but we can't solve that fully without openat)
            break

        current_dir = os.path.dirname(current_dir)
