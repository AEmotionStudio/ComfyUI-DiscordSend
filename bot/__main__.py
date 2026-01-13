import asyncio
import logging
import sys
import os
from pathlib import Path

# Add project root to python path to allow imports
project_root = Path(__file__).resolve().parent.parent
sys.path.append(str(project_root))

from bot.config import Config
from bot.bot import ComfyUIBot
from utils.logging_config import setup_logging

def main():
    # Setup logging
    setup_logging()
    logger = logging.getLogger("bot")
    
    # Load configuration
    try:
        config = Config()
    except Exception as e:
        logger.critical(f"Failed to load configuration: {e}")
        return

    if not config.discord_token:
        logger.critical("Discord token not found! Set DISCORDBOT_DISCORD_TOKEN env var or config.yaml")
        return

    # Initialize and run bot
    bot = ComfyUIBot(config)
    
    try:
        bot.run(config.discord_token)
    except KeyboardInterrupt:
        logger.info("Bot stopped by user.")
    except Exception as e:
        logger.critical(f"Bot crashed: {e}")

if __name__ == "__main__":
    main()
