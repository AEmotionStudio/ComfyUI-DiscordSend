"""ComfyUI nodes for sending images and video to Discord and saving them locally"""

import os
import sys

# Get the current directory
current_dir = os.path.dirname(os.path.realpath(__file__))

# Add to path if not already there
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

# Import nodes
from discord_image_node import DiscordSendSaveImage
from discord_video_node import DiscordSendSaveVideo

# Node class mappings for ComfyUI
NODE_CLASS_MAPPINGS = {
    "DiscordSendSaveImage": DiscordSendSaveImage,
    "DiscordSendSaveVideo": DiscordSendSaveVideo
}

# Display names for ComfyUI
NODE_DISPLAY_NAME_MAPPINGS = {
    "DiscordSendSaveImage": "Discord Send & Save Image 📤",
    "DiscordSendSaveVideo": "Discord Send & Save Video 🎬"
}

# Export all required elements
__all__ = ['NODE_CLASS_MAPPINGS', 'NODE_DISPLAY_NAME_MAPPINGS']
