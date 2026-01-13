"""
ComfyUI-DiscordSend Companion Bot

A Discord bot for triggering ComfyUI generations, managing queues,
saving prompt templates, and browsing generation history.
"""

import sys
from pathlib import Path

# Add parent directory to path for importing shared utils
_parent_dir = Path(__file__).parent.parent
if str(_parent_dir) not in sys.path:
    sys.path.insert(0, str(_parent_dir))

__version__ = "0.1.0"
__author__ = "AEmotionStudio"
