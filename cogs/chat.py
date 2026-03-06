import discord
from discord.ext import commands
import time
import yaml
import aiohttp
import json
from utils.ai import generate_ai_response

class Chat(commands.Cog):
    def __init__(self, bot, config):
        self.bot = bot
        self.config = config
        # ユーザーごとの発言時間を記録する辞書 {user_id: [timestamp, timestamp, ...]}
        self.user_history = {}
        # コンフィグから優先キーワードを取得（なければ空リスト）
        self.priority_keywords = self.config.get('priority_keywords', [])

    @commands.Cog.listener()
    async def on_message(self, message):
        # 1. 自分自身の投稿は無視
        if message.author == self.bot.user:
            return

        # 2. 監視対象のチャンネル以外は無視
        if message.channel.id not in self.config['channel_ids']:
            return

        # 3. コマンド（/から始まる）の場合は処理しない
        if message.content.startswith(self.bot.command_prefix):
            return

        # --- 優先キーワードの判定 (レートリミット回避) ---
        # メッセージ内に優先キーワードが含まれているかチェック
        is_priority = any(kw in message.content for kw in self.priority_keywords)

        if is_priority:
            # 優先キーワードが含まれる場合は、レートリミット判定をバイパスして即座にAIへ送信
            result = await generate_ai_response(message, self.config)
            if not result.get("success"):
                await message.reply("(優先キーワードでの応答に失敗しました)")
            return

        # --- レートリミットの判定 ---
        user_id = message.author.id
        now = time.time()
        limit_sec = self.config.get('rate_limit_seconds', 30)
        limit_count = self.config.get('rate_limit_count', 3)

        # そのユーザーの履歴がなければ作成
        if user_id not in self.user_history:
            self.user_history[user_id] = []

        # 期限切れ（limit_secより古い）のタイムスタンプを削除
        self.user_history[user_id] = [t for t in self.user_history[user_id] if now - t < limit_sec]

        # 履歴が上限に達しているかチェック
        if len(self.user_history[user_id]) >= limit_count:
            # 上限超えなら無視
            print(f"Rate limit exceeded for {message.author}")
            return

        # 今回の発言時間を記録
        self.user_history[user_id].append(now)

        # --- AIへのリクエスト ---
        result = await generate_ai_response(message, self.config)
        if not result.get("success"):
            # 汎用エラーとは別に、このCog独自の履歴件数を追加で表示する
            user_id = message.author.id
            history_count = len(self.user_history.get(user_id, []))
            await message.reply(f"(おしゃべり機能履歴: {history_count}件 / {message.author})")

async def setup(bot):
    # main.pyから渡されるconfigを利用できるようにする
    with open("config.yaml", "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    await bot.add_cog(Chat(bot, config))