"""
Media Processing Utilities

Provides image and video processing functions.
"""

from .image_processing import tensor_to_numpy_uint8
from .format_utils import (
    parse_format_string,
    normalize_video_extension,
    get_mime_type,
    validate_video_for_discord,
    is_animated_format,
    supports_alpha
)
from .video_encoder import (
    detect_ffmpeg,
    FFmpegEncoder,
    PILEncoder,
    optimize_video_for_discord,
    mux_audio_to_video
)

__all__ = [
    # Image processing
    'tensor_to_numpy_uint8',
    # Format utilities
    'parse_format_string',
    'normalize_video_extension',
    'get_mime_type',
    'validate_video_for_discord',
    'is_animated_format',
    'supports_alpha',
    # Video encoding
    'detect_ffmpeg',
    'FFmpegEncoder',
    'PILEncoder',
    'optimize_video_for_discord',
    'mux_audio_to_video',
]
