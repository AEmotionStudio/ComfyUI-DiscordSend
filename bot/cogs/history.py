"""History cog for viewing past generations and rerunning them."""

import discord
from discord import app_commands
from discord.ext import commands
import logging
import json
import random
from typing import List

from ..services.permissions import require_permission, Permissions
from ..database.models import JobStatus
from ..embeds.builders import EmbedBuilder
from shared.workflow import WorkflowBuilder

logger = logging.getLogger(__name__)


class HistoryPaginator(discord.ui.View):
    """Paginated view for job history."""

    def __init__(self, jobs: List, per_page: int = 5):
        super().__init__(timeout=180)
        self.jobs = jobs
        self.per_page = per_page
        self.page = 0
        self.max_page = (len(jobs) - 1) // per_page if jobs else 0
        self._update_buttons()

    def _update_buttons(self):
        self.prev_button.disabled = self.page <= 0
        self.next_button.disabled = self.page >= self.max_page

    def get_embed(self) -> discord.Embed:
        embed = discord.Embed(title="Generation History", color=discord.Color.blue())

        start = self.page * self.per_page
        end = start + self.per_page
        page_jobs = self.jobs[start:end]

        if not page_jobs:
            embed.description = "No generation history found."
            return embed

        lines = []
        for job in page_jobs:
            status_emoji = {
                JobStatus.COMPLETED.value: "✅",
                JobStatus.FAILED.value: "❌",
                JobStatus.CANCELLED.value: "🚫",
                JobStatus.PENDING.value: "⏳",
                JobStatus.RUNNING.value: "🔄",
            }.get(job.status, "❓")

            prompt_preview = (job.positive_prompt or "No prompt")[:50]
            if len(job.positive_prompt or "") > 50:
                prompt_preview += "..."

            timestamp = (
                job.created_at.strftime("%Y-%m-%d %H:%M") if job.created_at else "Unknown"
            )

            lines.append(
                f"{status_emoji} **ID: {job.id}** | {timestamp}\n└ {prompt_preview}"
            )

        embed.description = "\n\n".join(lines)
        embed.set_footer(
            text=f"Page {self.page + 1}/{self.max_page + 1} | Use /rerun <id> to regenerate"
        )

        return embed

    @discord.ui.button(label="◀ Previous", style=discord.ButtonStyle.secondary)
    async def prev_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        self.page = max(0, self.page - 1)
        self._update_buttons()
        await interaction.response.edit_message(embed=self.get_embed(), view=self)

    @discord.ui.button(label="Next ▶", style=discord.ButtonStyle.secondary)
    async def next_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        self.page = min(self.max_page, self.page + 1)
        self._update_buttons()
        await interaction.response.edit_message(embed=self.get_embed(), view=self)


class HistoryCog(commands.Cog):
    """View generation history and rerun past jobs."""

    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="history", description="View your generation history")
    @app_commands.describe(limit="Number of jobs to show (default: 20, max: 50)")
    async def history(self, interaction: discord.Interaction, limit: int = 20):
        """Show paginated generation history."""
        await interaction.response.defer(ephemeral=True)

        limit = min(max(1, limit), 50)  # Clamp between 1 and 50

        jobs = await self.bot.repository.list_user_jobs(
            user_discord_id=str(interaction.user.id), limit=limit
        )

        if not jobs:
            await interaction.followup.send(
                "You have no generation history.", ephemeral=True
            )
            return

        view = HistoryPaginator(jobs)
        await interaction.followup.send(embed=view.get_embed(), view=view, ephemeral=True)

    @app_commands.command(name="rerun", description="Rerun a previous generation")
    @app_commands.describe(job_id="The ID of the job to rerun")
    @require_permission(Permissions.USER.value)
    async def rerun(self, interaction: discord.Interaction, job_id: int):
        """Rerun a previous job with the same parameters."""
        await interaction.response.defer()

        # Get the original job
        original_job = await self.bot.repository.get_job_by_id(job_id)

        if not original_job:
            await interaction.followup.send(
                f"Job ID {job_id} not found.", ephemeral=True
            )
            return

        # Check ownership
        if str(original_job.user.discord_id) != str(interaction.user.id):
            await interaction.followup.send(
                "You can only rerun your own jobs.", ephemeral=True
            )
            return

        # Check if job has required data
        if not original_job.workflow_json:
            await interaction.followup.send(
                "This job cannot be rerun (workflow data not saved).", ephemeral=True
            )
            return

        try:
            workflow = json.loads(original_job.workflow_json)
        except json.JSONDecodeError:
            await interaction.followup.send(
                "Failed to parse original workflow.", ephemeral=True
            )
            return

        # Parse parameters
        parameters = {}
        if original_job.parameters:
            try:
                parameters = json.loads(original_job.parameters)
            except json.JSONDecodeError:
                pass

        # Generate new seed for rerun
        new_seed = random.randint(1, 1000000000000000)
        parameters["seed"] = new_seed

        # Update workflow with new seed
        builder = WorkflowBuilder(workflow)
        builder.set_seed(new_seed)
        final_workflow = builder.get_workflow()

        # Determine delivery and context
        server_id = str(interaction.guild_id) if interaction.guild else None
        channel_id = str(interaction.channel_id)

        try:
            # Create new job
            job = await self.bot.job_manager.create_job(
                user_discord_id=str(interaction.user.id),
                workflow=final_workflow,
                positive_prompt=original_job.positive_prompt or "",
                negative_prompt=original_job.negative_prompt or "",
                parameters=parameters,
                server_discord_id=server_id,
                channel_id=channel_id,
                delivery_type=original_job.delivery_type or "channel",
            )

            embed = EmbedBuilder.job_queued(job)
            embed.set_footer(text=f"Rerun of job #{job_id} | New job ID: {job.id}")

            await interaction.followup.send(embed=embed)

            # Store message ID
            original_message = await interaction.original_response()
            await self.bot.repository.update_job_message(
                job.prompt_id, str(original_message.id)
            )

        except Exception as e:
            logger.error(f"Failed to rerun job: {e}")
            await interaction.followup.send(
                f"Failed to rerun job: {str(e)}", ephemeral=True
            )


async def setup(bot):
    await bot.add_cog(HistoryCog(bot))
