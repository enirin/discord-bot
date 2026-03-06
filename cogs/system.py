import discord
from discord.ext import commands
import subprocess
import yaml
from utils.ai import generate_ai_response

class System(commands.Cog, name="システム機能"):
    """サーバーの状態確認などのシステム系コマンド"""
    def __init__(self, bot, config):
        self.bot = bot
        self.config = config

    @commands.hybrid_command(name="load", description="サーバーのCPU負荷やメモリ使用率を表示します。")
    async def load_info(self, ctx): 
        """サーバーの負荷情報を取得するコマンド"""
        try:
            uptime_res = subprocess.run(['uptime'], capture_output=True, text=True)
            free_res = subprocess.run(['free', '-h'], capture_output=True, text=True)
            
            prompt = (
                f"システム情報: ユーザーからサーバー負荷情報の確認依頼が来ました。"
                f"現在のUptime情報は「{uptime_res.stdout.strip()}」、"
                f"Memory使用状況は「{free_res.stdout.strip()}」です。"
                f"この情報を元に、あなたの言葉で現在のサーバーの調子をユーザーに報告してください。"
            )
            await generate_ai_response(prompt, self.config, reply_target=ctx)
        except Exception as e:
            prompt = f"システム情報: サーバー負荷情報の取得中にエラーが発生しました（内容: {e}）。ユーザーに謝って伝えてください。"
            await generate_ai_response(prompt, self.config, reply_target=ctx)

    @commands.hybrid_command(name="ping", description="Botが活きているか確認します。")
    async def ping(self, ctx):
        """疎通確認用コマンド"""
        prompt = "システム情報: ユーザーが生存確認（ping）を行いました。元気に生きていて反応できることをアピールする返信をしてください。"
        await generate_ai_response(prompt, self.config, reply_target=ctx)

async def setup(bot):
    with open("config.yaml", "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    await bot.add_cog(System(bot, config))