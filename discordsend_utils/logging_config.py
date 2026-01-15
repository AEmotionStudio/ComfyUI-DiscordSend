"""
Logging configuration for ComfyUI-DiscordSend

Provides a configured logger for the extension.
"""

import logging
import sys


def get_logger(name: str = "comfyui_discordsend") -> logging.Logger:
    """
    Get a configured logger for the extension.
    
    Args:
        name: The logger name (default: comfyui_discordsend)
        
    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    
    # Only configure if not already configured
    if not logger.handlers:
        logger.setLevel(logging.DEBUG)
        
        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        
        # Format
        formatter = logging.Formatter(
            '[%(name)s] %(levelname)s: %(message)s'
        )
        console_handler.setFormatter(formatter)
        
        logger.addHandler(console_handler)
    
    return logger


# Default logger instance
logger = get_logger()
