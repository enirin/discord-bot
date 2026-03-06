import discord
from discord.ext import commands
import time
import yaml
from utils.ai import generate_ai_response

# チャンネルごとの会話履歴の最大保持件数（ユーザー発言＋AI返答の合計）
DEFAULT_HISTORY_LIMIT = 20

class Chat(commands.Cog):
    def __init__(self, bot, config):
        self.bot = bot
        self.config = config
        # ユーザーごとの発言時間を記録する辞書 {user_id: [timestamp, timestamp, ...]}
        self.user_history = {}
        # コンフィグから優先キーワードを取得（なければ空リスト）
        self.priority_keywords = self.config.get('priority_keywords', [])
        # チャンネルごとの会話履歴 {channel_id: [{"role": "user"/"assistant", "content": "..."}, ...]}
        self.channel_conversations = {}
        # 会話履歴の最大保持件数
        self.history_limit = self.config.get('conversation_history_limit', DEFAULT_HISTORY_LIMIT)

    def _get_conversation(self, channel_id):
        """チャンネルの会話履歴を取得する（なければ初期化）"""
        if channel_id not in self.channel_conversations:
            self.channel_conversations[channel_id] = []
        return self.channel_conversations[channel_id]

    def _add_to_conversation(self, channel_id, role, content):
        """会話履歴にメッセージを追加し、上限を超えた分を古い順に削除する"""
        history = self._get_conversation(channel_id)
        history.append({"role": role, "content": content})
        # 上限を超えたら先頭から削除
        while len(history) > self.history_limit:
            history.pop(0)

    @commands.Cog.listener()
    async def on_message(self, message):
        # 1. 自分自身の投稿は無視
        if message.author == self.bot.user:
            return

        # 2. 監視対象のチャンネル以外は無視
        if message.channel.id not in self.config['channel_ids']:
            return

        # 3. コマンド（!から始まる）の場合は処理しない
        if message.content.startswith(self.bot.command_prefix):
            return

        channel_id = message.channel.id

        # --- 優先キーワードの判定 (レートリミット回避) ---
        is_priority = any(kw in message.content for kw in self.priority_keywords)

        if is_priority:
            # 今回のユーザー発言を履歴に追加してからAIへ送信
            history = self._get_conversation(channel_id)
            self._add_to_conversation(channel_id, "user", message.content)
            result = await generate_ai_response(message, self.config, conversation_history=history[:-1])
            if result.get("success"):
                self._add_to_conversation(channel_id, "assistant", result["response"])
            else:
                await message.reply("(優先キーワードでの応答に失敗しました)")
            return

        # --- レートリミットの判定 ---
        user_id = message.author.id
        now = time.time()
        limit_sec = self.config.get('rate_limit_seconds', 30)
        limit_count = self.config.get('rate_limit_count', 3)

        if user_id not in self.user_history:
            self.user_history[user_id] = []

        self.user_history[user_id] = [t for t in self.user_history[user_id] if now - t < limit_sec]

        if len(self.user_history[user_id]) >= limit_count:
            print(f"Rate limit exceeded for {message.author}")
            return

        self.user_history[user_id].append(now)

        # --- AIへのリクエスト（会話履歴付き）---
        history = self._get_conversation(channel_id)
        self._add_to_conversation(channel_id, "user", message.content)
        result = await generate_ai_response(message, self.config, conversation_history=history[:-1])
        if result.get("success"):
            self._add_to_conversation(channel_id, "assistant", result["response"])
        else:
            user_id = message.author.id
            history_count = len(self.user_history.get(user_id, []))
            await message.reply(f"(おしゃべり機能履歴: {history_count}件 / {message.author})")

async def setup(bot):
    with open("config.yaml", "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    await bot.add_cog(Chat(bot, config))