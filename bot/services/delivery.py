import discord
import io
import json
import logging
from typing import List, Dict, Any, Union

from ..comfyui.client import ComfyUIClient

logger = logging.getLogger(__name__)

class DeliveryService:
    """Handles delivery of results to Discord."""

    def __init__(self, bot: discord.Client, comfy_client: ComfyUIClient):
        self.bot = bot
        self.client = comfy_client

    async def deliver_job(self, job: Any): # job: Job model
        """Deliver results for a completed job."""
        if not job.output_images:
            logger.warning(f"Job {job.id} completed but has no images.")
            return

        try:
            images_data = json.loads(job.output_images)
        except json.JSONDecodeError:
            logger.error(f"Failed to parse output images for job {job.id}")
            return

        files = []
        for img_meta in images_data:
            filename = img_meta.get("filename")
            subfolder = img_meta.get("subfolder", "")
            img_type = img_meta.get("type", "output")
            
            try:
                img_bytes = await self.client.get_image(filename, subfolder, img_type)
                files.append(discord.File(io.BytesIO(img_bytes), filename=filename))
            except Exception as e:
                logger.error(f"Failed to download image {filename}: {e}")

        if not files:
            logger.warning("No files to upload.")
            return

        # Determine destination
        destination = None
        
        if job.delivery_type == "dm":
            user = self.bot.get_user(int(job.user.discord_id)) or await self.bot.fetch_user(int(job.user.discord_id))
            destination = user
        elif job.channel_id:
            destination = self.bot.get_channel(int(job.channel_id))
            if not destination:
                 # Fallback to DM if channel not found?
                 try:
                    user = self.bot.get_user(int(job.user.discord_id)) or await self.bot.fetch_user(int(job.user.discord_id))
                    destination = user
                 except:
                     pass

        if destination:
            content = f"Generation complete for <@{job.user.discord_id}>!\n**Prompt:** {job.positive_prompt}"
            try:
                await destination.send(content=content, files=files)
                logger.info(f"Delivered job {job.id} to {destination}")
            except Exception as e:
                logger.error(f"Failed to send message: {e}")
        else:
            logger.error(f"Could not determine destination for job {job.id}")
