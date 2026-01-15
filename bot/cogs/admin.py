import discord
from discord import app_commands
from discord.ext import commands
import logging

from ..services.permissions import require_permission, Permissions, PermissionLevel

logger = logging.getLogger(__name__)

class AdminCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="admin", description="Bot configuration (Admin only)")
    @require_permission(Permissions.ADMIN.value)
    @app_commands.choices(action=[
        app_commands.Choice(name="status", value="status"),
    ])
    async def admin(self, interaction: discord.Interaction, action: app_commands.Choice[str]):
        if action.value == "status":
            await self._show_status(interaction)

    async def _show_status(self, interaction: discord.Interaction):
        comfy_status = await self.bot.comfy_client.check_status()
        status_emoji = "✅" if comfy_status else "❌"
        
        embed = discord.Embed(title="Bot Status", color=discord.Color.dark_grey())
        embed.add_field(name="ComfyUI Connection", value=f"{status_emoji} {self.bot.config.comfyui_url}", inline=False)
        embed.add_field(name="Guilds", value=str(len(self.bot.guilds)), inline=True)
        embed.add_field(name="Latency", value=f"{round(self.bot.latency * 1000)}ms", inline=True)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="setrole", description="Set permission level for a role")
    @require_permission(Permissions.ADMIN.value)
    @app_commands.choices(level=[
        app_commands.Choice(name="User", value="user"),
        app_commands.Choice(name="Generator", value="generator"),
        app_commands.Choice(name="Admin", value="admin"),
    ])
    async def setrole(self, interaction: discord.Interaction, role: discord.Role, level: app_commands.Choice[str]):
        """Assign a permission level to a Discord role."""
        if not interaction.guild:
            await interaction.response.send_message("This command must be used in a server.", ephemeral=True)
            return

        try:
            # Ensure server exists in DB
            await self.bot.repository.get_or_create_server(
                str(interaction.guild.id), 
                interaction.guild.name
            )

            await self.bot.repository.set_server_role(
                server_discord_id=str(interaction.guild.id),
                role_discord_id=str(role.id),
                permission_level=level.value
            )
            await interaction.response.send_message(
                f"✅ Role {role.mention} set to **{level.name}** permission level.",
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Failed to set role: {e}")
            await interaction.response.send_message("❌ Failed to update role permissions.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(AdminCog(bot))
