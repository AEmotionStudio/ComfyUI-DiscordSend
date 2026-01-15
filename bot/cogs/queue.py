import discord
from discord import app_commands
from discord.ext import commands
import logging
from typing import Optional

from ..services.permissions import require_permission, Permissions
from ..database.models import JobStatus

logger = logging.getLogger(__name__)

class QueueCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="queue", description="Manage the generation queue")
    @app_commands.choices(action=[
        app_commands.Choice(name="view", value="view"),
        app_commands.Choice(name="clear", value="clear"),
    ])
    async def queue(self, interaction: discord.Interaction, action: app_commands.Choice[str]):
        """General queue commands."""
        command = action.value
        
        if command == "view":
            await self._view_queue(interaction)
        elif command == "clear":
            await self._clear_queue(interaction)

    async def _view_queue(self, interaction: discord.Interaction):
        """Show current pending jobs."""
        await interaction.response.defer(ephemeral=True)
        
        pending_jobs = await self.bot.repository.get_pending_jobs()
        
        if not pending_jobs:
            await interaction.followup.send("🟢 The queue is currently empty.", ephemeral=True)
            return

        embed = discord.Embed(
            title=f"Generation Queue ({len(pending_jobs)})",
            color=discord.Color.blue()
        )
        
        # Show top 10
        desc_lines = []
        for i, job in enumerate(pending_jobs[:10]):
            status_icon = "🔄" if job.status == JobStatus.RUNNING.value else "⏳"
            user_mention = f"<@{job.user.discord_id}>"
            prompt_text = job.positive_prompt or "No prompt provided"
            prompt_preview = (prompt_text[:40] + "...") if len(prompt_text) > 40 else prompt_text
            desc_lines.append(f"`#{i+1}` {status_icon} **ID:{job.id}** {user_mention}: {prompt_preview}")
        
        if len(pending_jobs) > 10:
            desc_lines.append(f"...and {len(pending_jobs) - 10} more.")
            
        embed.description = "\n".join(desc_lines)
        await interaction.followup.send(embed=embed, ephemeral=True)

    async def _clear_queue(self, interaction: discord.Interaction):
        """Clear user's own pending jobs."""
        # Check permission manually since it's a subcommand handler
        has_perm = await self.bot.permission_service.check_permission(interaction.user, Permissions.GENERATOR.value)
        if not has_perm:
             await interaction.response.send_message("⛔ You need the **Generator** role to clear the queue.", ephemeral=True)
             return

        await interaction.response.defer(ephemeral=True)
        
        # Get user's pending jobs
        # Note: repo.get_pending_jobs returns ALL. Better to filter or add new repo method.
        # But for now let's iterate.
        all_pending = await self.bot.repository.get_pending_jobs()
        user_jobs = [j for j in all_pending if str(j.user.discord_id) == str(interaction.user.id)]
        
        count = 0
        for job in user_jobs:
            success = await self.bot.job_manager.cancel_job(job.id)
            if success:
                count += 1
                
        if count > 0:
            await interaction.followup.send(f"🗑️ Cancelled {count} of your pending jobs.", ephemeral=True)
        else:
            await interaction.followup.send("No pending jobs found to clear.", ephemeral=True)


    @app_commands.command(name="cancel", description="Cancel a specific job")
    @app_commands.describe(job_id="The ID of the job to cancel")
    @require_permission(Permissions.GENERATOR.value)
    async def cancel(self, interaction: discord.Interaction, job_id: int):
        """Cancel a specific job by ID."""
        await interaction.response.defer(ephemeral=True)
        
        job = await self.bot.repository.get_job_by_id(job_id)
        if not job:
             await interaction.followup.send(f"❌ Job ID {job_id} not found.", ephemeral=True)
             return

        # Check permissions
        is_owner = str(job.user.discord_id) == str(interaction.user.id)
        is_admin = await self.bot.permission_service.check_permission(interaction.user, Permissions.ADMIN.value)
        
        if not is_owner and not is_admin:
            await interaction.followup.send("⛔ You can only cancel your own jobs.", ephemeral=True)
            return

        success = await self.bot.job_manager.cancel_job(job_id)
        if success:
            await interaction.followup.send(f"✅ Job {job_id} cancelled.", ephemeral=True)
        else:
            await interaction.followup.send(f"⚠️ Could not cancel job {job_id} (maybe already finished?).", ephemeral=True)

async def setup(bot):
    await bot.add_cog(QueueCog(bot))
