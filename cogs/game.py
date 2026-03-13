import discord
from discord.ext import commands
from skills import GameServerSkill
from application.services import deliver_ai_response

class GameServer(commands.Cog, name="ゲームサーバー管理"):
    """ゲームサーバーの起動・停止・状態確認を行うコマンド群"""

    def __init__(self, bot, config):
        self.bot = bot
        self.config = config
        self.skill = GameServerSkill(config, bot.game_server_api, bot.game_server_catalog_repository)

    @commands.hybrid_command(name="gs_list", description="管理下のゲームサーバー一覧とステータスを表示します。")
    async def list_servers(self, ctx):
        """APIからサーバー一覧を取得して表示"""
        async with ctx.typing():
            result = await self.skill.list_servers_result()
            await self._deliver_skill_result(ctx, result)

    @commands.hybrid_command(name="gs_start", description="指定したサーバーを起動します。引数にサーバー名が必要です。")
    async def start_server(self, ctx, server_name: str = None):
        """指定サーバーを起動、引数がない場合は一覧を提示"""
        async with ctx.typing():
            result = await self.skill.start_server_result(server_name)
            await self._deliver_skill_result(ctx, result)

    @commands.hybrid_command(name="gs_stop", description="指定したサーバーを停止します。引数にサーバー名が必要です。")
    async def stop_server(self, ctx, server_name: str = None):
        """指定サーバーを停止、引数がない場合は一覧を提示"""
        async with ctx.typing():
            result = await self.skill.stop_server_result(server_name)
            await self._deliver_skill_result(ctx, result)

    @commands.hybrid_command(name="gs_status", description="指定したサーバーの状態を確認します。引数なしなら全体状況を表示します。")
    async def status_server(self, ctx, server_name: str = None):
        """指定サーバーまたは全体の状態を表示"""
        async with ctx.typing():
            result = await self.skill.status_result(server_name)
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
    await bot.add_cog(GameServer(bot, config))