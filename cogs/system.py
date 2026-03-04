import discord
from discord.ext import commands
import subprocess

class System(commands.Cog, name="システム機能"):
    """サーバーの状態確認などのシステム系コマンド"""
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="load", help="サーバーのCPU負荷やメモリ使用率を表示します。")
    async def load_info(self, ctx): 
        """サーバーの負荷情報を取得するコマンド"""
        try:
            uptime_res = subprocess.run(['uptime'], capture_output=True, text=True)
            free_res = subprocess.run(['free', '-h'], capture_output=True, text=True)
            
            reply_msg = (
                "**[サーバー負荷情報]**\n"
                "**Uptime & Load Average:**\n```text\n"
                f"{uptime_res.stdout.strip()}\n```\n"
                "**Memory Usage:**\n```text\n"
                f"{free_res.stdout.strip()}\n```"
            )
            await ctx.reply(reply_msg)
        except Exception as e:
            await ctx.reply(f"負荷情報の取得に失敗しました: {e}")

    @commands.command(name="ping", help="Botが活きているか確認します。")
    async def ping(self, ctx):
        """疎通確認用コマンド"""
        await ctx.reply("pong!")

    @commands.command(name="hello", help="Botが挨拶を返します。引数を渡すと、その内容を返します。")
    async def hello(self, ctx, *, args=None):
        """引数をそのまま返す、または定型文を返すコマンド"""
        if args:
            # 引数がある場合はその内容を返信
            await ctx.reply(args)
        else:
            # 引数がない場合
            await ctx.reply("hello!!")

async def setup(bot):
    await bot.add_cog(System(bot))