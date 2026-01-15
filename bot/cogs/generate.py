import discord
from discord import app_commands
from discord.ext import commands
import logging
import json
from pathlib import Path

from ..embeds.builders import EmbedBuilder
from ..services.permissions import require_permission, Permissions
from ...utils.workflow_builder import WorkflowBuilder

logger = logging.getLogger(__name__)

class GenerateCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="generate", description="Generate an image using ComfyUI")
    @app_commands.describe(
        prompt="The positive prompt to generate",
        negative_prompt="Aspects to avoid (optional)",
        seed="Seed for generation (optional)",
        steps="Number of steps (optional)",
        cfg="CFG Scale (optional)",
        delivery="Delivery method (channel or dm)"
    )
    @app_commands.choices(delivery=[
        app_commands.Choice(name="Current Channel", value="channel"),
        app_commands.Choice(name="Direct Message", value="dm")
    ])
    @require_permission(Permissions.USER.value)
    async def generate(self, interaction: discord.Interaction, 
                       prompt: str, 
                       negative_prompt: str = "", 
                       seed: int = None,
                       steps: int = None,
                       cfg: float = None,
                       delivery: app_commands.Choice[str] = None):
        
        await interaction.response.defer()
        
        # Load default workflow
        # TODO: Move this path to config or database
        workflow_path = Path(__file__).parent.parent / "data" / "default_workflow_api.json"
        
        if not workflow_path.exists():
            await interaction.followup.send("❌ Error: Default workflow not found.", ephemeral=True)
            return

        try:
            with open(workflow_path, "r") as f:
                workflow_json = json.load(f)
        except Exception as e:
            logger.error(f"Failed to load workflow: {e}")
            await interaction.followup.send("❌ Error: Failed to load workflow configuration.", ephemeral=True)
            return

        # Prepare parameters for tracking
        parameters = {
            "seed": seed,
            "steps": steps,
            "cfg": cfg
        }

        # Modify workflow
        builder = WorkflowBuilder(workflow_json)
        builder.set_prompt(prompt, negative_prompt)
        
        if seed is not None:
            builder.set_seed(seed)
        else:
            # Random seed if not provided
            import random
            generated_seed = random.randint(1, 1000000000000000)
            builder.set_seed(generated_seed)
            parameters["seed"] = generated_seed # Track actual seed

        if steps is not None:
            builder.set_steps(steps)
            
        if cfg is not None:
            builder.set_cfg(cfg)

        final_workflow = builder.get_workflow()

        # Determine delivery method
        delivery_method = delivery.value if delivery else "channel"

        # Check server context
        server_id = str(interaction.guild_id) if interaction.guild else None
        channel_id = str(interaction.channel_id)

        try:
            # Create Job
            job = await self.bot.job_manager.create_job(
                user_discord_id=str(interaction.user.id),
                workflow=final_workflow,
                positive_prompt=prompt,
                negative_prompt=negative_prompt,
                parameters=parameters,
                server_discord_id=server_id,
                channel_id=channel_id,
                delivery_type=delivery_method
            )
            
            # Send Queued Embed
            embed = EmbedBuilder.job_queued(job)
            await interaction.followup.send(embed=embed)
            
            # Store the interaction message ID if we want to update it later
            # (JobManager could use this to update the specific message)
            original_message = await interaction.original_response()
            await self.bot.repository.update_job_message(job.prompt_id, str(original_message.id))

        except Exception as e:
            logger.error(f"Failed to start generation: {e}")
            await interaction.followup.send(f"❌ Error starting generation: {str(e)}", ephemeral=True)

async def setup(bot):
    await bot.add_cog(GenerateCog(bot))
