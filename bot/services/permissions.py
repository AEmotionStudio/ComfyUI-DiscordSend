import logging
from typing import Optional, List, Dict
import discord
from enum import Enum

from ..database.repository import Repository
from ..database.models import PermissionLevel, ServerRole, User

logger = logging.getLogger(__name__)

class Permissions(Enum):
    USER = "user"
    GENERATOR = "generator"
    ADMIN = "admin"

class PermissionService:
    """Manages role-based permissions."""

    def __init__(self, repository: Repository):
        self.repo = repository

    def get_permission_hierarchy(self) -> Dict[str, int]:
        return {
            Permissions.USER.value: 1,
            Permissions.GENERATOR.value: 2,
            Permissions.ADMIN.value: 3
        }

    import discord
from typing import Union

    async def get_user_permission_level(self, member: Union[discord.Member, discord.User]) -> str:
        """
        Determine the highest permission level for a user in a guild.
        Default is USER.
        Administrator permission in Discord implies ADMIN level.
        """
        # Handle DMs or non-guild context where we have User instead of Member
        if isinstance(member, discord.User):
            return Permissions.USER.value
            
        if member.guild_permissions.administrator:
            return Permissions.ADMIN.value

        # Fetch configured roles for this server
        server_roles = await self.repo.get_server_roles(str(member.guild.id))
        
        if not server_roles:
            return Permissions.USER.value

        hierarchy = self.get_permission_hierarchy()
        current_level = Permissions.USER.value
        current_score = hierarchy[current_level]

        # Check user's roles against configured roles
        member_role_ids = [str(r.id) for r in member.roles]
        
        for server_role in server_roles:
            if server_role.role_discord_id in member_role_ids:
                level = server_role.permission_level
                if level in hierarchy and hierarchy[level] > current_score:
                    current_level = level
                    current_score = hierarchy[level]
        
        return current_level

    async def check_permission(self, member: discord.Member, required_level: str) -> bool:
        """Check if user meets the required permission level."""
        user_level = await self.get_user_permission_level(member)
        hierarchy = self.get_permission_hierarchy()
        
        return hierarchy.get(user_level, 0) >= hierarchy.get(required_level, 0)

# Helper decorator for checking permissions in commands
def require_permission(level: str):
    async def predicate(interaction: discord.Interaction):
        if not interaction.guild:
            return True # DMs are always allowed/handled differently? Or restrict? 
                        # For now, let's assume commands needing permissions are guild-only.
        
        # We need to access the bot instance to get the permission service
        bot = interaction.client
        if not hasattr(bot, "permission_service"):
            logger.error("Bot instance missing permission_service")
            return False

        has_perm = await bot.permission_service.check_permission(interaction.user, level)
        
        if not has_perm:
            await interaction.response.send_message(
                f"⛔ You need **{level.upper()}** permission to use this command.",
                ephemeral=True
            )
        return has_perm
    return discord.app_commands.check(predicate)
