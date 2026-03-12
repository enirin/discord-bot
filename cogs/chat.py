import discord
from discord.ext import commands
import time
import re
from utils.ai import generate_ai_response, generate_ai_text

# デフォルト設定値
DEFAULT_HISTORY_LIMIT = 20
DEFAULT_SUMMARY_KEEP_RECENT = 8
DEFAULT_SESSION_TIMEOUT_SECONDS = 90
DEFAULT_REPLY_COOLDOWN_SECONDS = 20

class Chat(commands.Cog):
    """AIとの対話、会話履歴の管理、および自然言語によるサーバー操作を制御するモジュール"""

    def __init__(self, bot, config):
        self.bot = bot
        self.config = config
        self.user_history = {}
        self.priority_keywords = self.config.get('priority_keywords', [])
        self.channel_conversations = {}
        self.channel_summaries = {}
        self.channel_active_until = {}
        self.channel_last_bot_reply_at = {}
        
        # コンフィグから設定を取得（なければデフォルト値を使用）
        self.history_limit = self.config.get('conversation_history_limit', DEFAULT_HISTORY_LIMIT)
        configured_keep_recent = self.config.get('conversation_summary_keep_recent', DEFAULT_SUMMARY_KEEP_RECENT)
        self.summary_keep_recent = max(1, min(configured_keep_recent, self.history_limit))
        self.session_timeout_seconds = self.config.get('conversation_session_timeout_seconds', DEFAULT_SESSION_TIMEOUT_SECONDS)
        self.reply_cooldown_seconds = self.config.get('conversation_reply_cooldown_seconds', DEFAULT_REPLY_COOLDOWN_SECONDS)

    def _get_conversation(self, channel_id):
        """チャンネルの会話履歴を取得（初期化）"""
        if channel_id not in self.channel_conversations:
            self.channel_conversations[channel_id] = []
        return self.channel_conversations[channel_id]

    def _create_user_record(self, message):
        """ユーザーの発言を履歴用レコードに変換"""
        return {
            "role": "user",
            "content": message.content,
            "author_id": message.author.id,
            "author_name": message.author.name,
            "display_name": message.author.display_name,
            "message_id": message.id,
            "timestamp": message.created_at.isoformat(),
        }

    def _create_assistant_record(self, content):
        """AIの返答を履歴用レコードに変換"""
        return {
            "role": "assistant",
            "content": content,
            "author_id": self.bot.user.id if self.bot.user else None,
            "author_name": self.bot.user.name if self.bot.user else self.config.get('bot_name', 'Bot'),
            "display_name": self.bot.user.display_name if self.bot.user else self.config.get('bot_name', 'Bot'),
            "timestamp": time.strftime('%Y-%m-%dT%H:%M:%S'),
        }

    async def _add_to_conversation(self, channel_id, record):
        """履歴にメッセージを追加し、上限を超えたら要約（圧縮）する"""
        history = self._get_conversation(channel_id)
        history.append(record)
        if len(history) > self.history_limit:
            await self._compress_conversation(channel_id)

    def _format_history_record_for_ai(self, record):
        """AIへ渡すための単一メッセージフォーマット"""
        role = record.get("role")
        content = str(record.get("content", "")).strip()
        if not content: return None
        if role == "assistant":
            return {"role": "assistant", "content": content}
        speaker = record.get("display_name") or record.get("author_name") or "ユーザー"
        return {"role": "user", "content": f"{speaker}: {content}"}

    def _get_ai_history(self, channel_id, history=None):
        """AIへ渡すための会話履歴リストを作成"""
        source_history = history if history is not None else self._get_conversation(channel_id)
        formatted_history = []
        for record in source_history:
            formatted_record = self._format_history_record_for_ai(record)
            if formatted_record:
                formatted_history.append(formatted_record)
        return formatted_history

    def _get_latest_user_prompt(self, record):
        """最新のユーザー発言を名前付きで整形（これが不足していた関数です）"""
        speaker_name = record.get("display_name") or record.get("author_name") or "ユーザー"
        content = str(record.get("content", "")).strip()
        return f"{speaker_name}: {content}"

    def _looks_like_question(self, content):
        """メッセージが質問形式か判定"""
        lowered = content.lower()
        question_markers = ["?", "？", "教えて", "おしえて", "わからない", "なに", "何", "どう", "なんで", "なぜ", "かな", "でしょうか"]
        return any(marker in lowered for marker in question_markers)

    async def _is_reply_to_bot(self, message):
        """Botへの返信かどうか判定"""
        reference = message.reference
        if reference is None: return False
        resolved = reference.resolved
        if resolved is not None and hasattr(resolved, 'author'):
            return resolved.author == self.bot.user
        return False

    def _mark_bot_replied(self, channel_id):
        """返信時刻とセッション期限を更新"""
        now = time.time()
        self.channel_last_bot_reply_at[channel_id] = now
        self.channel_active_until[channel_id] = now + self.session_timeout_seconds

    def _get_summary_message(self, channel_id):
        """要約メッセージを取得"""
        summary_text = self.channel_summaries.get(channel_id, "").strip()
        if not summary_text: return None
        return f"以前の会話の要約:\n{summary_text}"

    async def _compress_conversation(self, channel_id):
        """会話履歴をAIで要約して圧縮"""
        history = self._get_conversation(channel_id)
        summarize_count = len(history) - self.summary_keep_recent
        if summarize_count <= 0: return

        messages_to_summarize = history[:summarize_count]
        transcript = "\n".join([
            f"{'ユーザー' if m['role']=='user' else 'アシスタント'}({m.get('display_name','Bot')}): {m['content']}"
            for m in messages_to_summarize
        ])

        prompt = f"以下の会話の流れを日本語で簡潔に要約してください。\n\n{transcript}"
        result = await generate_ai_text(prompt, self.config, prompt_role="system", include_base_system_instruction=False)
        if result.get("success"):
            self.channel_summaries[channel_id] = result["response"].strip()
            del history[:summarize_count]

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author == self.bot.user or message.channel.id not in self.config['channel_ids']: return
        if message.content.startswith(self.bot.command_prefix): return

        channel_id = message.channel.id
        user_record = self._create_user_record(message)
        await self._add_to_conversation(channel_id, user_record)

        # 反応判定
        bot_name = str(self.config.get('bot_name', '')).lower()
        is_priority = any(kw in message.content for kw in self.priority_keywords)
        is_mentioned = self.bot.user in message.mentions
        is_name_called = bot_name in message.content.lower()
        is_reply_to_bot = await self._is_reply_to_bot(message)
        
        now = time.time()
        in_active_session = now < self.channel_active_until.get(channel_id, 0)
        is_question = self._looks_like_question(message.content)
        on_cooldown = now - self.channel_last_bot_reply_at.get(channel_id, 0) < self.reply_cooldown_seconds

        # いずれかの条件を満たせば応答
        should_respond = is_priority or is_mentioned or is_name_called or is_reply_to_bot or (in_active_session and is_question and not on_cooldown)
        if not should_respond: return

        # レートリミット（優先時は無視）
        if not is_priority:
            user_id = message.author.id
            limit_sec, limit_count = self.config.get('rate_limit_seconds', 30), self.config.get('rate_limit_count', 3)
            if user_id not in self.user_history: self.user_history[user_id] = []
            self.user_history[user_id] = [t for t in self.user_history[user_id] if now - t < limit_sec]
            if len(self.user_history[user_id]) >= limit_count: return
            self.user_history[user_id].append(now)

        # --- 最新のサーバー知識を取得してAIに教える ---
        game_cog = self.bot.get_cog("ゲームサーバー管理")
        server_knowledge = ""
        if game_cog:
            res = await game_cog.api.list_servers()
            if res.get("success") or "servers" in res:
                server_knowledge = "【現在のゲームサーバー最新状況】\n"
                for s in res.get("servers", []):
                    players = ", ".join(s.get("players_list", [])) or "なし"
                    server_knowledge += (
                        f"- サーバー名: {s['name']}\n"
                        f"  状態: {s['status']}\n"
                        f"  人数: {s['stats']['players']}\n"
                        f"  オンライン中: {players}\n"
                        f"  経過日数: {s.get('day', 0)}日目\n"
                    )

        # AIへのプロンプト構成
        extra_sys = [self._get_summary_message(channel_id)]
        if server_knowledge:
            extra_sys.append(f"あなたは現在、サーバーについて以下の事実を知っています。質問にはこの情報を元に答えてください。\n{server_knowledge}")

        ai_history = self._get_ai_history(channel_id, self._get_conversation(channel_id)[:-1])
        prompt_text = self._get_latest_user_prompt(user_record)

        result = await generate_ai_response(
            prompt_text, self.config, reply_target=message,
            conversation_history=ai_history, extra_system_messages=extra_sys
        )

        if result.get("success"):
            ai_resp = result["response"]
            # コマンド解析
            if "[COMMAND:" in ai_resp:
                match = re.search(r"\[COMMAND:(START|STOP):(.+?)\]", ai_resp)
                if match and game_cog:
                    action, sid = match.group(1), match.group(2).strip()
                    if action == "START": await game_cog.api.start_server(sid)
                    elif action == "STOP": await game_cog.api.stop_server(sid)

            self._mark_bot_replied(channel_id)
            await self._add_to_conversation(channel_id, self._create_assistant_record(ai_resp))

async def setup(bot):
    await bot.add_cog(Chat(bot, bot.config))