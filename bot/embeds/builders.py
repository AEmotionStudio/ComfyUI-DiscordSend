import discord
import logging
from typing import Optional, List
from datetime import datetime

class EmbedBuilder:
    """Helper for building Discord embeds."""

    @staticmethod
    def job_queued(job, position: int = 0) -> discord.Embed:
        """Embed for queued job."""
        embed = discord.Embed(
            title="🎨 Generation Queued",
            description=f"**Prompt:** {job.positive_prompt}",
            color=discord.Color.blue(),
            timestamp=datetime.utcnow()
        )
        embed.add_field(name="Queue Position", value=str(position) if position > 0 else "Pending...", inline=True)
        embed.add_field(name="Status", value="Waiting to start...", inline=True)
        if job.negative_prompt:
            embed.add_field(name="Negative Prompt", value=job.negative_prompt, inline=False)
        embed.set_footer(text=f"Job ID: {job.id}")
        return embed

    @staticmethod
    def job_progress(job, progress: int, max_progress: int) -> discord.Embed:
        """Embed for running job with progress."""
        percent = int((progress / max_progress) * 100) if max_progress > 0 else 0
        bars = "█" * (percent // 10) + "░" * (10 - (percent // 10))
        
        embed = discord.Embed(
            title="🎨 Generating...",
            description=f"**Prompt:** {job.positive_prompt}",
            color=discord.Color.orange(),
            timestamp=datetime.utcnow()
        )
        embed.add_field(name="Progress", value=f"`{bars}` {percent}%", inline=False)
        if job.negative_prompt:
             embed.add_field(name="Negative Prompt", value=job.negative_prompt, inline=False)
        embed.set_footer(text=f"Job ID: {job.id}")
        return embed

    @staticmethod
    def job_completed(job, image_count: int) -> discord.Embed:
        """Embed for completed job."""
        embed = discord.Embed(
            title="✨ Generation Complete!",
            description=f"**Prompt:** {job.positive_prompt}",
            color=discord.Color.green(),
            timestamp=datetime.utcnow()
        )
        embed.add_field(name="Images", value=f"{image_count} generated", inline=True)
        embed.add_field(name="Duration", value=f"{job.duration:.1f}s" if hasattr(job, 'duration') and job.duration else "Done", inline=True)
        
        if job.negative_prompt:
             embed.add_field(name="Negative Prompt", value=job.negative_prompt, inline=False)
             
        embed.set_footer(text=f"Job ID: {job.id}")
        return embed

    @staticmethod
    def job_failed(job, error_message: str) -> discord.Embed:
        """Embed for failed job."""
        embed = discord.Embed(
            title="❌ Generation Failed",
            description=f"**Prompt:** {job.positive_prompt}",
            color=discord.Color.red(),
            timestamp=datetime.utcnow()
        )
        embed.add_field(name="Error", value=f"```{error_message}```", inline=False)
        embed.set_footer(text=f"Job ID: {job.id}")
        return embed
