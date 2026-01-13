import discord
from discord.ext import commands
import logging
import sys
import asyncio
from pathlib import Path

from .config import Config
from .database.repository import Repository
from .comfyui.client import ComfyUIClient
from .comfyui.websocket import ComfyUIWebSocket

logger = logging.getLogger(__name__)

class ComfyUIBot(commands.Bot):
    """
    Main Bot Class for ComfyUI Companion.
    """

    def __init__(self, config: Config):
        intents = discord.Intents.default()
        intents.message_content = True  # Needed for some commands if not pure slash
        intents.members = True # Useful for permission checks

        super().__init__(
            command_prefix=commands.when_mentioned,
            intents=intents,
            help_command=None,
            description="ComfyUI Companion Bot"
        )
        self.config = config
        
        # Database
        self.repository = Repository(config.database_url)
        
        
        # ComfyUI Clients
        self.comfy_client = ComfyUIClient(base_url=config.comfyui_url)
        self.comfy_ws = ComfyUIWebSocket(base_url=config.comfyui_url)
        
        # Services
        from .services.delivery import DeliveryService
        from .services.job_manager import JobManager
        
        self.delivery_service = DeliveryService(self, self.comfy_client)
        self.job_manager = JobManager(
            self.repository, 
            self.comfy_client, 
            self.comfy_ws, 
            self.delivery_service
        )
        
    async def setup_hook(self):
        """Async setup before bot starts."""
        logger.info(f"Setting up bot for {self.user}...")
        
        # Initialize Database
        await self.repository.init_db()
        logger.info("Database initialized.")
        
        # Connect to ComfyUI WebSocket
        try:
            await self.comfy_ws.connect()
            await self.job_manager.start()
        except Exception as e:
            logger.warning(f"Could not connect to ComfyUI WebSocket at start: {e}")
            # We don't crash, as ComfyUI might come up later
            
        # Load Cogs
        await self._load_cogs()
        
        # Sync Commands
        # In production, sync might be manual or per-guild to avoid rate limits
        # For simplicity in this self-hosted bot, we'll sync global
        try:
            synced = await self.tree.sync()
            logger.info(f"Synced {len(synced)} slash commands.")
        except Exception as e:
            logger.error(f"Failed to sync commands: {e}")

    async def _load_cogs(self):
        """Load extensions from cogs directory."""
        # We need to use dotted path: bot.cogs.generate
        cogs_dir = Path(__file__).parent / "cogs"
        
        # Extensions to load
        extensions = [
            "bot.cogs.generate",
            # "bot.cogs.queue",
            # "bot.cogs.templates",
            # "bot.cogs.history",
            # "bot.cogs.admin",
        ]
        
        for ext in extensions:
            try:
                # Check if file exists first to avoid confusing errors if we haven't created it yet
                # (Since we are building incrementally)
                module_name = ext.split(".")[-1]
                if (cogs_dir / f"{module_name}.py").exists():
                    await self.load_extension(ext)
                    logger.info(f"Loaded extension: {ext}")
                else:
                    logger.debug(f"Skipping extension {ext} (file not found)")
            except Exception as e:
                logger.error(f"Failed to load extension {ext}: {e}")

    async def close(self):
        """Cleanup on shutdown."""
        logger.info("Shutting down bot...")
        await self.comfy_client.close()
        await self.comfy_ws.disconnect()
        await self.repository.close()
        await super().close()

    async def on_ready(self):
        logger.info(f"Bot logged in as {self.user} (ID: {self.user.id})")
        logger.info(f"Connected to {len(self.guilds)} guilds")

    async def on_command_error(self, ctx, error):
        """Global error handler for prefix commands (if any)."""
        logger.error(f"Command error: {error}", exc_info=False)
