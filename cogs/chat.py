import discord
from discord.ext import commands
import time
import yaml
import aiohttp
import json

class Chat(commands.Cog):
    def __init__(self, bot, config):
        self.bot = bot
        self.config = config
        # ユーザーごとの発言時間を記録する辞書 {user_id: [timestamp, timestamp, ...]}
        self.user_history = {}
        # コンフィグから優先キーワードを取得（なければ空リスト）
        self.priority_keywords = self.config.get('priority_keywords', [])
        self.ollama_url = "http://localhost:11434/api/generate"

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
            await message.reply("優先キーワードを検知しました！即座に対応します。")
            return # ここで処理を終了させることで、下のレートリミット判定を通らない

        # --- レートリミットの判定 ---
        user_id = message.author.id
        now = time.time()
        limit_sec = self.config['rate_limit_seconds']
        limit_count = self.config['rate_limit_count']

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
        # ユーザーが「入力中...」になるようにアクションを表示
        async with message.channel.typing():
            # configからシステムプロンプトを取得
            system_instruction = self.config.get('system_prompt', "You are a helpful assistant.")
            # configからモデル名を取得。なければデフォルトで llama3.2
            target_model = self.config.get('ai_model', "llama3.2")

            payload = {
                "model": target_model, # 使用するモデル名
                "prompt": message.content,
                "system": system_instruction, # ここに性格設定を渡す
                "stream": False # ストリーミングなし（一括回答）
            }

            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(self.ollama_url, json=payload) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            response_text = data.get("response", "ごめんなさい、うまく考えられませんでした。")
                            await message.reply(response_text)
                        else:
                            await message.reply("AIサーバーが応答していません。")
            except Exception as e:
                print(f"エラーが発生しました: {e}")
                await message.reply("エラーが発生したため、おしゃべり機能（定型文モード）です。" + str(len(self.user_history[user_id])) + "messages for " + str(message.author))

async def setup(bot):
    # main.pyから渡されるconfigを利用できるようにする
    with open("config.yaml", "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    await bot.add_cog(Chat(bot, config))