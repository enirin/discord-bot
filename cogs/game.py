import discord
from discord.ext import commands
from utils.ai import generate_ai_response
from utils.game_api import GameServerAPI

class GameServer(commands.Cog, name="ゲームサーバー管理"):
    """ゲームサーバーの起動・停止・状態確認を行うコマンド群"""

    def __init__(self, bot, config):
        self.bot = bot
        self.config = config
        base_url = self.config.get('game_api_url', 'http://localhost:5000')
        self.api = GameServerAPI(base_url)

    @commands.hybrid_command(name="gs_list", description="管理下のゲームサーバー一覧とステータスを表示します。")
    async def list_servers(self, ctx):
        """APIからサーバー一覧を取得して表示"""
        async with ctx.typing():
            res = await self.api.list_servers()
            
            if not res["success"]:
                err = res.get("error", "不明なエラー")
                prompt = f"システム情報: ゲームサーバー一覧の取得中にエラーが発生しました（内容: {err}）。ユーザーに謝って状況を報告してください。"
                await generate_ai_response(prompt, self.config, reply_target=ctx)
                return

            servers = res.get("servers", [])
            if not servers:
                prompt = "システム情報: 登録されているゲームサーバーが一つも見つかりませんでした。ユーザーに教えてあげてください。"
                await generate_ai_response(prompt, self.config, reply_target=ctx)
                return

            embed = discord.Embed(title="🎮 ゲームサーバー一覧", color=discord.Color.blue())
            for s in servers:
                name = s.get("name")
                status = s.get("status")
                status_emoji = "🟢" if status == "online" else "🔴" if status == "offline" else "🟡"
                
                stats = s.get("stats", {})
                info = (
                    f"**Status:** {status_emoji} {status}\n"
                    f"**Address:** `{s.get('address')}`\n"
                    f"**Players:** {stats.get('players')}\n"
                    f"**Day:** {s.get('day')}\n"
                    f"**Resources:** CPU {stats.get('cpu')}% / Mem {stats.get('memory')}GB"
                )
                embed.add_field(name=name, value=info, inline=False)
            
            prompt = f"システム情報: 現在{len(servers)}個のゲームサーバーの状態を取得し表示しました。これから管理しているゲームサーバーの一覧とそれぞれ現在の詳細状況が表示されるということを、あなたの言葉で短く案内してください。"
            await generate_ai_response(prompt, self.config, reply_target=ctx)
            await ctx.reply(embed=embed)

    @commands.hybrid_command(name="gs_start", description="指定したサーバーを起動します。引数にサーバー名が必要です。")
    async def start_server(self, ctx, server_name: str = None):
        """指定サーバーを起動、引数がない場合は一覧を提示"""
        async with ctx.typing():
            if not server_name:
                await self._prompt_server_selection(ctx, "起動")
                return

            res = await self.api.start_server(server_name)
            await self._handle_action_response(ctx, "起動", server_name, res)

    @commands.hybrid_command(name="gs_stop", description="指定したサーバーを停止します。引数にサーバー名が必要です。")
    async def stop_server(self, ctx, server_name: str = None):
        """指定サーバーを停止、引数がない場合は一覧を提示"""
        async with ctx.typing():
            if not server_name:
                await self._prompt_server_selection(ctx, "停止")
                return

            res = await self.api.stop_server(server_name)
            await self._handle_action_response(ctx, "停止", server_name, res)

    async def _prompt_server_selection(self, ctx, action_name: str):
        """サーバー名が指定されなかった場合に一覧を取得し、ユーザーに選ばせるためのプロンプトをAIに投げる"""
        res = await self.api.list_servers()
        if not res["success"]:
            prompt = f"システム情報: ユーザーがサーバーの{action_name}をしようとしましたがサーバー名の指定がありませんでした。さらにサーバー一覧を取得しようとしましたがエラー（内容: {res.get('error', '不明')}）が発生しました。謝罪してください。"
            await generate_ai_response(prompt, self.config, reply_target=ctx)
            return

        servers = res.get("servers", [])
        if not servers:
            prompt = f"システム情報: ユーザーがサーバーの{action_name}をしようとしましたがサーバー名の指定がなく、管理対象のサーバーも1つも登録されていません。ユーザーに登録されていない旨を教えてあげてください。"
            await generate_ai_response(prompt, self.config, reply_target=ctx)
            return

        server_names = ", ".join([f"「{s['name']}」" for s in servers])
        prompt = f"システム情報: ユーザーがサーバーの{action_name}をしようとしましたが、サーバー名の指定（引数）がありませんでした。現在登録されているサーバーは {server_names} です。ユーザーに、どのサーバーを{action_name}したいのか尋ねて（コマンドにサーバー名をつけてね、と添えて）ください。"
        await generate_ai_response(prompt, self.config, reply_target=ctx)

    async def _handle_action_response(self, ctx, action_name: str, server_name: str, res: dict):
        """起動/停止コマンド共通のレスポンス処理ルーチン"""
        if not res["success"] and res.get("is_connection_error"):
            prompt = f"システム情報: ゲームサーバー「{server_name}」の{action_name}処理中に接続エラーが発生しました（エラー: {res.get('error')}）。ユーザーに伝えてください。"
            await generate_ai_response(prompt, self.config, reply_target=ctx)
            return

        status = res.get("status")
        data = res.get("data", {})
        
        if status == 200:
            prompt = f"システム情報: ユーザーがゲームサーバー「{server_name}」を{action_name}させる依頼があったため実行しました。APIからの応答は「{data.get('message')}」です。お礼や報告の言葉を添えてユーザーに教えてあげてください。"
        elif status == 404:
            prompt = f"システム情報: ゲームサーバー「{server_name}」を{action_name}しようとしましたが、そんな名前のサーバーは見つかりませんでした。ユーザーに、名前が間違っているかもしれないと教えてあげてください。"
        else:
            prompt = f"システム情報: ゲームサーバー「{server_name}」を{action_name}しようとしましたが、エラーが発生しました（内容: {data.get('message', '不明なエラー')}）。状況を報告してください。"
            
        await generate_ai_response(prompt, self.config, reply_target=ctx)

async def setup(bot):
    config = getattr(bot, "config", None)
    if config is None:
        raise RuntimeError("Bot config is not loaded. Please check startup configuration loading.")
    await bot.add_cog(GameServer(bot, config))