import discord
from discord.ext import commands
from skills import SystemSkill
from application.services import deliver_ai_response

class System(commands.Cog, name="システム機能"):
    """サーバーの状態確認などのシステム系コマンド"""
    def __init__(self, bot, config):
        self.bot = bot
        self.config = config
        self.skill = SystemSkill(config)

    @commands.hybrid_command(name="load", description="サーバーのCPU負荷やメモリ使用率を表示します。")
    async def load_info(self, ctx): 
        """サーバーの負荷情報を取得するコマンド"""
        result = await self.skill.load_result()
        await self._deliver_skill_result(ctx, result)

    @commands.hybrid_command(name="ping", description="Botが活きているか確認します。")
    async def ping(self, ctx):
        """疎通確認用コマンド"""
        result = await self.skill.ping_result()
        await self._deliver_skill_result(ctx, result)

    async def _deliver_skill_result(self, ctx, result):
        await deliver_ai_response(
            result.prompt,
            self.config,
            ctx,
            fallback_text=result.fallback_text,
            embed=result.embed,
        )

async def setup(bot):
    config = getattr(bot, "config", None)
    if config is None:
        raise RuntimeError("Bot config is not loaded. Please check startup configuration loading.")
    await bot.add_cog(System(bot, config))