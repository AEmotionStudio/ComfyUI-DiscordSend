import discord
import io
import json
import logging
from typing import Any, Optional, Union

from ..comfyui.client import ComfyUIClient
from ..embeds.builders import EmbedBuilder

logger = logging.getLogger(__name__)


class DeliveryService:
    """Handles delivery of results to Discord."""

    def __init__(self, bot: discord.Client, comfy_client: ComfyUIClient):
        self.bot = bot
        self.client = comfy_client

    async def _get_destination(
        self, job: Any
    ) -> Optional[Union[discord.User, discord.TextChannel]]:
        """Get the destination channel or user for a job."""
        if job.delivery_type == "dm":
            try:
                user = self.bot.get_user(int(job.user.discord_id))
                if not user:
                    user = await self.bot.fetch_user(int(job.user.discord_id))
                return user
            except Exception as e:
                logger.error(f"Failed to fetch user for DM: {e}")
                return None

        if job.channel_id:
            destination = self.bot.get_channel(int(job.channel_id))
            if destination:
                return destination
            # Fallback to DM if channel not found
            try:
                user = self.bot.get_user(int(job.user.discord_id))
                if not user:
                    user = await self.bot.fetch_user(int(job.user.discord_id))
                return user
            except Exception:
                pass

        return None

    async def deliver_error(self, job: Any, error_message: str) -> bool:
        """
        Deliver error notification for a failed job.

        Args:
            job: The failed Job model instance
            error_message: The error message to display

        Returns:
            True if delivery succeeded, False otherwise
        """
        # Truncate error message if too long (Discord embed field limit)
        if len(error_message) > 1000:
            error_message = error_message[:997] + "..."

        embed = EmbedBuilder.job_failed(job, error_message)

        destination = await self._get_destination(job)

        if destination:
            try:
                await destination.send(embed=embed)
                logger.info(f"Delivered error for job {job.id} to {destination}")
                return True
            except Exception as e:
                logger.error(f"Failed to deliver error: {e}")
                return False
        else:
            logger.error(
                f"Could not determine destination for error delivery (job {job.id})"
            )
            return False

    async def deliver_job(self, job: Any):  # job: Job model
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

        destination = await self._get_destination(job)

        if destination:
            content = f"Generation complete for <@{job.user.discord_id}>!\n**Prompt:** {job.positive_prompt}"
            try:
                await destination.send(content=content, files=files)
                logger.info(f"Delivered job {job.id} to {destination}")
            except Exception as e:
                logger.error(f"Failed to send message: {e}")
        else:
            logger.error(f"Could not determine destination for job {job.id}")
