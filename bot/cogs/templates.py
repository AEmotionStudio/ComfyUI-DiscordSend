"""Template management cog for saving and loading prompt presets."""

import discord
from discord import app_commands
from discord.ext import commands
import logging
from typing import List

from ..services.permissions import require_permission, Permissions

logger = logging.getLogger(__name__)


class TemplateCog(commands.Cog):
    """Manage prompt templates."""

    def __init__(self, bot):
        self.bot = bot

    template_group = app_commands.Group(
        name="template", description="Manage prompt templates"
    )

    @template_group.command(name="save", description="Save a prompt as a template")
    @app_commands.describe(
        name="Template name (unique per user/server)",
        prompt="The positive prompt to save",
        negative_prompt="Negative prompt (optional)",
        shared="Share with entire server (default: private)",
    )
    @require_permission(Permissions.GENERATOR.value)
    async def template_save(
        self,
        interaction: discord.Interaction,
        name: str,
        prompt: str,
        negative_prompt: str = "",
        shared: bool = False,
    ):
        """Save current prompt as a named template."""
        await interaction.response.defer(ephemeral=True)

        # Validate name
        if len(name) > 100:
            await interaction.followup.send(
                "Template name must be 100 characters or less.", ephemeral=True
            )
            return

        # Ensure user exists
        await self.bot.repository.get_or_create_user(
            str(interaction.user.id), interaction.user.display_name
        )

        server_id = str(interaction.guild_id) if interaction.guild and shared else None
        if server_id:
            await self.bot.repository.get_or_create_server(
                server_id, interaction.guild.name
            )

        try:
            await self.bot.repository.create_template(
                user_discord_id=str(interaction.user.id),
                name=name,
                positive_prompt=prompt,
                negative_prompt=negative_prompt,
                server_discord_id=server_id,
            )

            scope = "server" if shared else "private"
            await interaction.followup.send(
                f"Saved template **{name}** ({scope}).", ephemeral=True
            )
        except Exception as e:
            if "UNIQUE constraint" in str(e):
                await interaction.followup.send(
                    f"A template named **{name}** already exists. "
                    "Delete it first or use a different name.",
                    ephemeral=True,
                )
            else:
                logger.error(f"Failed to save template: {e}")
                await interaction.followup.send(
                    "Failed to save template.", ephemeral=True
                )

    @template_group.command(name="load", description="Load a saved template")
    @app_commands.describe(name="Template name to load")
    async def template_load(self, interaction: discord.Interaction, name: str):
        """Load a template and show its contents."""
        await interaction.response.defer(ephemeral=True)

        server_id = str(interaction.guild_id) if interaction.guild else None

        # Try user's private template first
        template = await self.bot.repository.get_template(
            user_discord_id=str(interaction.user.id), name=name
        )

        # Try shared server template if not found
        if not template and server_id:
            templates = await self.bot.repository.list_templates(
                user_discord_id=str(interaction.user.id),
                server_discord_id=server_id,
                include_shared=True,
            )
            template = next((t for t in templates if t.name == name), None)

        if not template:
            await interaction.followup.send(
                f"Template **{name}** not found.", ephemeral=True
            )
            return

        embed = discord.Embed(title=f"Template: {template.name}", color=discord.Color.blue())
        embed.add_field(
            name="Prompt", value=template.positive_prompt[:1024], inline=False
        )
        if template.negative_prompt:
            embed.add_field(
                name="Negative Prompt",
                value=template.negative_prompt[:1024],
                inline=False,
            )

        scope = "Shared" if template.server_id else "Private"
        embed.set_footer(text=f"{scope} template | Use /generate with this prompt")

        await interaction.followup.send(embed=embed, ephemeral=True)

    @template_group.command(name="list", description="List your saved templates")
    async def template_list(self, interaction: discord.Interaction):
        """List all available templates."""
        await interaction.response.defer(ephemeral=True)

        server_id = str(interaction.guild_id) if interaction.guild else None

        templates = await self.bot.repository.list_templates(
            user_discord_id=str(interaction.user.id),
            server_discord_id=server_id,
            include_shared=True,
        )

        if not templates:
            await interaction.followup.send(
                "You have no saved templates.", ephemeral=True
            )
            return

        embed = discord.Embed(title="Your Templates", color=discord.Color.blue())

        private_templates = [t for t in templates if t.server_id is None]
        shared_templates = [t for t in templates if t.server_id is not None]

        if private_templates:
            names = "\n".join([f"• {t.name}" for t in private_templates[:10]])
            if len(private_templates) > 10:
                names += f"\n...and {len(private_templates) - 10} more"
            embed.add_field(name="Private Templates", value=names, inline=False)

        if shared_templates:
            names = "\n".join([f"• {t.name}" for t in shared_templates[:10]])
            if len(shared_templates) > 10:
                names += f"\n...and {len(shared_templates) - 10} more"
            embed.add_field(name="Server Templates", value=names, inline=False)

        await interaction.followup.send(embed=embed, ephemeral=True)

    @template_group.command(name="delete", description="Delete a saved template")
    @app_commands.describe(name="Template name to delete")
    @require_permission(Permissions.GENERATOR.value)
    async def template_delete(self, interaction: discord.Interaction, name: str):
        """Delete a template."""
        await interaction.response.defer(ephemeral=True)

        # Try deleting private template
        deleted = await self.bot.repository.delete_template(
            user_discord_id=str(interaction.user.id), name=name
        )

        # Try deleting shared template if private not found
        if not deleted and interaction.guild:
            deleted = await self.bot.repository.delete_template(
                user_discord_id=str(interaction.user.id),
                name=name,
                server_discord_id=str(interaction.guild_id),
            )

        if deleted:
            await interaction.followup.send(
                f"Deleted template **{name}**.", ephemeral=True
            )
        else:
            await interaction.followup.send(
                f"Template **{name}** not found or you don't have permission to delete it.",
                ephemeral=True,
            )

    @template_load.autocomplete("name")
    @template_delete.autocomplete("name")
    async def template_name_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> List[app_commands.Choice[str]]:
        """Autocomplete for template names."""
        server_id = str(interaction.guild_id) if interaction.guild else None

        templates = await self.bot.repository.list_templates(
            user_discord_id=str(interaction.user.id),
            server_discord_id=server_id,
            include_shared=True,
        )

        # Filter by current input
        filtered = [t for t in templates if current.lower() in t.name.lower()]

        return [
            app_commands.Choice(name=t.name, value=t.name)
            for t in filtered[:25]  # Discord limit
        ]


async def setup(bot):
    await bot.add_cog(TemplateCog(bot))
