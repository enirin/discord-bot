import discord
from discord.ext import commands
from skills import GameServerSkill
from application.services import GameServerRequestContext, deliver_skill_result

class GameServer(commands.Cog, name="ゲームサーバー管理"):
    """ゲームサーバーの起動・停止・状態確認や IP マッピング管理を行うコマンド群"""

    def __init__(self, bot, config):
        self.bot = bot
        self.config = config
        self.skill = GameServerSkill(
            config,
            bot.game_server_api,
            bot.game_server_catalog_repository,
            bot.game_server_operation_service,
        )

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
            result = await self.skill.start_server_result(server_name, self._build_request_context(ctx, source="command"))
            await self._deliver_skill_result(ctx, result)

    @commands.hybrid_command(name="gs_stop", description="指定したサーバーを停止します。引数にサーバー名が必要です。")
    async def stop_server(self, ctx, server_name: str = None):
        """指定サーバーを停止、引数がない場合は一覧を提示"""
        async with ctx.typing():
            result = await self.skill.stop_server_result(server_name, self._build_request_context(ctx, source="command"))
            await self._deliver_skill_result(ctx, result)

    @commands.hybrid_command(name="gs_status", description="指定したサーバーの状態を確認します。引数なしなら全体状況を表示します。")
    async def status_server(self, ctx, server_name: str = None):
        """指定サーバーまたは全体の状態を表示"""
        async with ctx.typing():
            result = await self.skill.status_result(server_name)
            await self._deliver_skill_result(ctx, result)

    @commands.hybrid_command(name="gs_maintenance", description="指定したサーバーの保守情報を表示します。")
    async def maintenance_server(self, ctx, server_name: str = None):
        async with ctx.typing():
            result = await self.skill.maintenance_result(server_name)
            await self._deliver_skill_result(ctx, result)

    @commands.hybrid_command(name="gs_player_lookup", description="IP または IP:port に登録されているプレイヤー名を確認します。")
    async def lookup_ip_player_name(self, ctx, ip_address: str):
        async with ctx.typing():
            result = await self.skill.get_ip_player_name_result(ip_address)
            await self._deliver_skill_result(ctx, result)

    @commands.hybrid_command(name="gs_player_list", description="登録済みの IP プレイヤー名マッピング一覧を表示します。")
    async def list_ip_player_names(self, ctx):
        async with ctx.typing():
            result = await self.skill.list_ip_player_names_result()
            await self._deliver_skill_result(ctx, result)

    @commands.hybrid_command(name="gs_player_register", description="IP または IP:port とプレイヤー名のマッピングを登録します。")
    async def register_ip_player_name(self, ctx, ip_address: str, *, player_name: str):
        async with ctx.typing():
            result = await self.skill.register_ip_player_name_result(ip_address=ip_address, player_name=player_name)
            await self._deliver_skill_result(ctx, result)

    @commands.hybrid_command(name="gs_confirm", description="確認待ちのゲームサーバー操作を実行します。")
    async def confirm_server_operation(self, ctx):
        async with ctx.typing():
            result = await self.skill.confirm_pending_result(self._build_request_context(ctx, source="command"))
            await self._deliver_skill_result(ctx, result)

    @commands.hybrid_command(name="gs_cancel", description="確認待ちのゲームサーバー操作をキャンセルします。")
    async def cancel_server_operation(self, ctx):
        async with ctx.typing():
            result = await self.skill.cancel_pending_result(self._build_request_context(ctx, source="command"))
            await self._deliver_skill_result(ctx, result)

    async def _deliver_skill_result(self, ctx, result):
        await deliver_skill_result(
            result,
            self.config,
            ctx,
        )

    def _build_request_context(self, ctx, source: str) -> GameServerRequestContext:
        author = getattr(ctx, "author", None)
        channel = getattr(ctx, "channel", None)
        return GameServerRequestContext(
            requester_id=getattr(author, "id", None),
            requester_name=getattr(author, "display_name", None),
            channel_id=getattr(channel, "id", None),
            source=source,
        )

async def setup(bot):
    config = getattr(bot, "config", None)
    if config is None:
        raise RuntimeError("Bot config is not loaded. Please check startup configuration loading.")
    await bot.add_cog(GameServer(bot, config))