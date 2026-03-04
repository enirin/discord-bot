import discord
from discord.ext import commands
import aiohttp
import yaml

class GameServer(commands.Cog, name="ゲームサーバー管理"):
    """ゲームサーバーの起動・停止・状態確認を行うコマンド群"""

    def __init__(self, bot, config):
        self.bot = bot
        self.config = config
        # APIのベースURL (末尾のスラッシュを削除しておく)
        self.base_url = self.config.get('game_api_url', 'http://localhost:5000').rstrip('/')

    @commands.command(name="gs_list", help="管理下のゲームサーバー一覧とステータスを表示します。")
    async def list_servers(self, ctx):
        """GET /list を呼び出してサーバー一覧を表示"""
        async with ctx.typing():
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(f"{self.base_url}/list") as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            servers = data.get("servers", [])
                            
                            if not servers:
                                await ctx.reply("管理対象のサーバーは見つかりませんでした。")
                                return

                            embed = discord.Embed(title="🎮 ゲームサーバー一覧", color=discord.Color.blue())
                            for s in servers:
                                name = s.get("name")
                                status = s.get("status")
                                # ステータスに応じて絵文字を変える
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
                            
                            await ctx.reply(embed=embed)
                        else:
                            await ctx.reply(f"APIエラーが発生しました (Status: {resp.status})")
            except Exception as e:
                await ctx.reply(f"接続エラー: APIサーバーが起動しているか確認してください。\n`{e}`")

    @commands.command(name="gs_start", help="指定したサーバーを起動します。引数にサーバー名が必要です。")
    async def start_server(self, ctx, server_name: str):
        """POST /start/{server_name} を呼び出し"""
        async with ctx.typing():
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(f"{self.base_url}/start/{server_name}") as resp:
                        data = await resp.json()
                        if resp.status == 200:
                            await ctx.reply(f"✅ {data.get('message')}")
                        elif resp.status == 404:
                            await ctx.reply(f"❌ サーバー `{server_name}` が見つかりませんでした。")
                        else:
                            await ctx.reply(f"⚠️ エラー: {data.get('message', '不明なエラー')}")
            except Exception as e:
                await ctx.reply(f"接続エラー: {e}")

    @commands.command(name="gs_stop", help="指定したサーバーを停止します。引数にサーバー名が必要です。")
    async def stop_server(self, ctx, server_name: str):
        """POST /stop/{server_name} を呼び出し"""
        async with ctx.typing():
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(f"{self.base_url}/stop/{server_name}") as resp:
                        data = await resp.json()
                        if resp.status == 200:
                            await ctx.reply(f"🛑 {data.get('message')}")
                        elif resp.status == 404:
                            await ctx.reply(f"❌ サーバー `{server_name}` が見つかりませんでした。")
                        else:
                            await ctx.reply(f"⚠️ エラー: {data.get('message', '不明なエラー')}")
            except Exception as e:
                await ctx.reply(f"接続エラー: {e}")

async def setup(bot):
    with open("config.yaml", "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    await bot.add_cog(GameServer(bot, config))