"""
ComfyUI-DiscordSend Node Implementations

This package contains the ComfyUI custom nodes for sending media to Discord.
"""

from .image_node import DiscordSendSaveImage
from .video_node import DiscordSendSaveVideo

__all__ = ['DiscordSendSaveImage', 'DiscordSendSaveVideo']
