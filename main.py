import discord
from discord.ext import commands
import yaml
import os
import asyncio
import sys


def load_config_or_exit(config_path="config.yaml"):
    """config.yaml を読み込み、構文/必須項目エラー時は案内を表示して終了する。"""
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            loaded = yaml.safe_load(f)
    except FileNotFoundError:
        print(f"設定ファイルが見つかりません: {config_path}")
        print("config.yaml.sample をコピーして config.yaml を作成してください。")
        sys.exit(1)
    except yaml.YAMLError as e:
        print(f"config.yaml の構文エラーを検出しました: {e}")
        mark = getattr(e, "problem_mark", None)
        if mark is not None:
            print(f"エラー位置: 行 {mark.line + 1}, 列 {mark.column + 1}")
        print("Botは起動しません。config.yaml の記述を確認して再実行してください。")
        sys.exit(1)

    if not isinstance(loaded, dict):
        print("config.yaml の形式が不正です。トップレベルはマッピング形式（key: value）にしてください。")
        print("Botは起動しません。config.yaml を確認して再実行してください。")
        sys.exit(1)

    required_keys = ["bot_token", "channel_ids", "bot_name"]
    missing = [key for key in required_keys if key not in loaded]
    if missing:
        print(f"config.yaml の必須項目が不足しています: {', '.join(missing)}")
        print("Botは起動しません。config.yaml を確認して再実行してください。")
        sys.exit(1)

    if not isinstance(loaded.get("channel_ids"), list):
        print("config.yaml の channel_ids は配列（- 123...）で指定してください。")
        print("Botは起動しません。config.yaml を確認して再実行してください。")
        sys.exit(1)

    numeric_required_fields = [
        "rate_limit_seconds",
        "rate_limit_count",
        "conversation_history_limit",
        "conversation_summary_keep_recent",
        "conversation_session_timeout_seconds",
        "conversation_reply_cooldown_seconds",
    ]
    numeric_optional_fields = [
        "guild_id",
    ]

    for channel_id in loaded.get("channel_ids", []):
        if not isinstance(channel_id, int):
            print(f"config.yaml の channel_ids に数値以外が含まれています: {channel_id}")
            print("channel_ids は整数の配列で指定してください。")
            print("Botは起動しません。config.yaml を確認して再実行してください。")
            sys.exit(1)

    invalid_required = [
        key for key in numeric_required_fields
        if key in loaded and not isinstance(loaded.get(key), int)
    ]
    if invalid_required:
        print(
            "config.yaml の数値項目に不正な型があります: "
            f"{', '.join(invalid_required)}"
        )
        print("これらの項目は整数で指定してください。")
        print("Botは起動しません。config.yaml を確認して再実行してください。")
        sys.exit(1)

    invalid_optional = [
        key for key in numeric_optional_fields
        if key in loaded and loaded.get(key) not in (None, "") and not isinstance(loaded.get(key), int)
    ]
    if invalid_optional:
        print(
            "config.yaml の数値項目に不正な型があります: "
            f"{', '.join(invalid_optional)}"
        )
        print("これらの項目は未設定（空欄）または整数で指定してください。")
        print("Botは起動しません。config.yaml を確認して再実行してください。")
        sys.exit(1)

    return loaded

# --- 設定の読み込み ---
config = load_config_or_exit("config.yaml")

TOKEN = config['bot_token']
TARGET_CHANNEL_IDS = config['channel_ids']
BOT_NAME = config['bot_name']
ICON_PATH = config['icon_path']
GUILD_ID = config.get('guild_id', None) # 開発用・即時反映用ギルドID

# ヘルプの文言を日本語化したい場合などの設定
class MyHelp(commands.DefaultHelpCommand):
    def __init__(self):
        super().__init__()
        self.commands_heading = "コマンドリスト:"
        self.no_category = "その他のコマンド"
        self.command_attrs["help"] = "ヘルプを表示します。"

class SMEBot(commands.Bot):
    def __init__(self, config_data):
        intents = discord.Intents.default()
        intents.message_content = True
        self.config = config_data
        # コマンドプレフィックスを / に設定
        super().__init__(command_prefix='!', intents=intents, help_command=MyHelp())

    async def setup_hook(self):
        """起動時にCogsを読み込む"""
        for filename in os.listdir('./cogs'):
            if filename.endswith('.py'):
                await self.load_extension(f'cogs.{filename[:-3]}')
                print(f'Loaded extension: {filename}')
        
        # SlashCommands(App Commands)をDiscord側に同期
        try:
            if GUILD_ID:
                guild = discord.Object(id=GUILD_ID)
                self.tree.copy_global_to(guild=guild)
                synced = await self.tree.sync(guild=guild)
                print(f"Synced {len(synced)} command(s) to guild {GUILD_ID}.")
            else:
                synced = await self.tree.sync()
                print(f"Synced {len(synced)} command(s) globally. (Note: Global sync can take up to 1 hour to propagate.)")
        except Exception as e:
            print(f"Failed to sync commands: {e}")

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

        # 3. メッセージに対するコマンド処理
        # HybridCommand を含む従来のコマンドハンドリングを実行
        await self.process_commands(message)

# 実行
bot = SMEBot(config)
bot.run(TOKEN)