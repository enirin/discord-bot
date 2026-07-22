import discord
from discord.ext import commands
from skills.blender_skill import BlenderSkill
from application.services import deliver_skill_result

class Blender(commands.Cog, name="Blender 3D操作"):
    """Blenderを操作するコマンド群"""

    def __init__(self, bot, config):
        self.bot = bot
        self.config = config
        mcp_client = getattr(bot, "blender_mcp_client", None)
        self.skill = BlenderSkill(config, mcp_client)

    @commands.hybrid_command(name="blender", description="Blenderに自然言語で指示を出して操作します。")
    async def execute_blender(self, ctx, *, instruction: str):
        async with ctx.typing():
            result = await self.skill.execute_instruction_result(instruction)
            await deliver_skill_result(result, self.config, ctx)

async def setup(bot):
    config = getattr(bot, "config", None)
    if config is None:
        raise RuntimeError("Bot config is not loaded.")
    await bot.add_cog(Blender(bot, config))