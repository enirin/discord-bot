import discord
from discord.ext import commands
import yaml
import os
import asyncio

# --- 設定の読み込み ---
with open("config.yaml", "r", encoding="utf-8") as f:
    config = yaml.safe_load(f)

TOKEN = config['bot_token']
TARGET_CHANNEL_IDS = config['channel_ids']
BOT_NAME = config['bot_name']
ICON_PATH = config['icon_path']

# ヘルプの文言を日本語化したい場合などの設定
class MyHelp(commands.DefaultHelpCommand):
    def __init__(self):
        super().__init__()
        self.commands_heading = "コマンドリスト:"
        self.no_category = "その他のコマンド"
        self.command_attrs["help"] = "ヘルプを表示します。"

class SMEBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        # コマンドプレフィックスを / に設定
        super().__init__(command_prefix='/', intents=intents, help_command=MyHelp())

    async def setup_hook(self):
        """起動時にCogsを読み込む"""
        for filename in os.listdir('./cogs'):
            if filename.endswith('.py'):
                await self.load_extension(f'cogs.{filename[:-3]}')
                print(f'Loaded extension: {filename}')

    async def on_ready(self):
        print(f'Logged in as {self.user} (ID: {self.user.id})')

        # --- プロフィール更新処理 ---
        # 1. 名前の更新（現在の名前と違う場合のみ）
        if self.user.name != BOT_NAME:
            try:
                await self.user.edit(username=BOT_NAME)
                print(f"Bot名を '{BOT_NAME}' に更新しました。")
            except discord.HTTPException as e:
                print(f"名前の更新に失敗しました（レートリミットの可能性があります）: {e}")

        # 2. アイコンの更新
        if ICON_PATH and os.path.exists(ICON_PATH):
            # アイコンは頻繁に変えるものではないため、手動設定を推奨しますが、
            # スクリプトで完結させたい場合は以下をコメントアウト解除してください。
            """
            try:
                with open(ICON_PATH, "rb") as f:
                    await self.user.edit(avatar=f.read())
                    print("アイコンを更新しました。")
            except discord.HTTPException as e:
                print(f"アイコンの更新に失敗しました: {e}")
            """
            pass

async def on_message(self, message):
        # 1. 自分自身と他のBotを無視
        if message.author == self.user:
            return

        # 2. 監視対象チャンネル以外は無視
        if message.channel.id not in TARGET_CHANNEL_IDS:
            return

        # 3. メッセージがコマンドプレフィックスで始まる場合
        if message.content.startswith(self.command_prefix):
            ctx = await self.get_context(message)
            
            if ctx.valid:
                # Cogに登録された正式なコマンドを実行
                await self.invoke(ctx)
            else:
                # /から始まるが、Cogに登録されていない場合
                await message.reply("未定義のコマンドです。")
        else:
            pass

# 実行
bot = SMEBot()
bot.run(TOKEN)