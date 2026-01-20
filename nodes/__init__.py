"""
ComfyUI-DiscordSend Node Implementations

This package contains the ComfyUI custom nodes for sending media to Discord.
"""

from .base_node import BaseDiscordNode
from .image_node import DiscordSendSaveImage
from .video_node import DiscordSendSaveVideo

__all__ = ['BaseDiscordNode', 'DiscordSendSaveImage', 'DiscordSendSaveVideo']
