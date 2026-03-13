import discord
from discord.ext import commands
import time
import json
from utils.ai import generate_ai_response, generate_ai_text
from utils.game_api import GameServerAPI

# チャンネルごとの会話履歴の最大保持件数（ユーザー発言＋AI返答の合計）
DEFAULT_HISTORY_LIMIT = 20
DEFAULT_SUMMARY_KEEP_RECENT = 8
DEFAULT_SESSION_TIMEOUT_SECONDS = 90
DEFAULT_REPLY_COOLDOWN_SECONDS = 20

class Chat(commands.Cog):
    def __init__(self, bot, config):
        self.bot = bot
        self.config = config
        base_url = self.config.get('game_api_url', 'http://localhost:5000')
        self.game_api = GameServerAPI(base_url)
        self.tools = [
            {
                "type": "function",
                "function": {
                    "name": "get_server_status",
                    "description": "ゲームサーバーの一覧、ステータス、現在ログイン中のプレイヤー情報を取得します。ユーザーから「サーバー動いてる？」「誰か遊んでる？」と聞かれたときに使用します。",
                    "parameters": {
                        "type": "object",
                        "properties": {}
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "start_server",
                    "description": "指定したゲームサーバーを起動します。ユーザーから「サーバーを起動して」と頼まれたときに実行します。",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "server_name": {
                                "type": "string",
                                "description": "起動するサーバーの識別名（name）。分からない場合は事前に get_server_status を実行して正しいnameを確認してください。"
                            }
                        },
                        "required": ["server_name"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "stop_server",
                    "description": "指定したゲームサーバーを停止します。ユーザーから「サーバーを止めて」と頼まれたときに実行します。",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "server_name": {
                                "type": "string",
                                "description": "停止するサーバーの識別名（name）。分からない場合は事前に get_server_status を実行して正しいnameを確認してください。"
                            }
                        },
                        "required": ["server_name"]
                    }
                }
            }
        ]
        # ユーザーごとの発言時間を記録する辞書 {user_id: [timestamp, timestamp, ...]}
        self.user_history = {}
        # コンフィグから優先キーワードを取得（なければ空リスト）
        self.priority_keywords = self.config.get('priority_keywords', [])
        # チャンネルごとの会話履歴 {channel_id: [{"role": "user"/"assistant", "content": "..."}, ...]}
        self.channel_conversations = {}
        # チャンネルごとの要約済み会話
        self.channel_summaries = {}
        # チャンネルごとのBot会話セッション期限
        self.channel_active_until = {}
        # チャンネルごとの最終Bot返信時刻
        self.channel_last_bot_reply_at = {}
        # 会話履歴の最大保持件数
        self.history_limit = self.config.get('conversation_history_limit', DEFAULT_HISTORY_LIMIT)
        configured_keep_recent = self.config.get('conversation_summary_keep_recent', DEFAULT_SUMMARY_KEEP_RECENT)
        self.summary_keep_recent = max(1, min(configured_keep_recent, self.history_limit))
        self.session_timeout_seconds = self.config.get('conversation_session_timeout_seconds', DEFAULT_SESSION_TIMEOUT_SECONDS)
        self.reply_cooldown_seconds = self.config.get('conversation_reply_cooldown_seconds', DEFAULT_REPLY_COOLDOWN_SECONDS)

    def _get_conversation(self, channel_id):
        """チャンネルの会話履歴を取得する（なければ初期化）"""
        if channel_id not in self.channel_conversations:
            self.channel_conversations[channel_id] = []
        return self.channel_conversations[channel_id]

    def _create_user_record(self, message):
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
        return {
            "role": "assistant",
            "content": content,
            "author_id": self.bot.user.id if self.bot.user else None,
            "author_name": self.bot.user.name if self.bot.user else self.config.get('bot_name', 'Bot'),
            "display_name": self.bot.user.display_name if self.bot.user else self.config.get('bot_name', 'Bot'),
            "timestamp": time.strftime('%Y-%m-%dT%H:%M:%S'),
        }

    async def _add_to_conversation(self, channel_id, record):
        """会話履歴にメッセージを追加し、必要に応じて古い履歴を要約に圧縮する"""
        history = self._get_conversation(channel_id)
        history.append(record)

        if len(history) > self.history_limit:
            await self._compress_conversation(channel_id)

    async def _tool_dispatcher(self, tool_call):
        func_name = tool_call.get("function", {}).get("name")
        args = tool_call.get("function", {}).get("arguments", {})
        
        if func_name == "get_server_status":
            res = await self.game_api.list_servers()
            return json.dumps(res, ensure_ascii=False)
        elif func_name == "start_server":
            server_name = args.get("server_name")
            if not server_name:
                return json.dumps({"error": "server_name is missing"}, ensure_ascii=False)
            res = await self.game_api.start_server(server_name)
            return json.dumps(res, ensure_ascii=False)
        elif func_name == "stop_server":
            server_name = args.get("server_name")
            if not server_name:
                return json.dumps({"error": "server_name is missing"}, ensure_ascii=False)
            res = await self.game_api.stop_server(server_name)
            return json.dumps(res, ensure_ascii=False)
        
        return json.dumps({"error": f"Unknown function: {func_name}"}, ensure_ascii=False)

    def _format_history_record_for_ai(self, record):
        role = record.get("role")
        content = str(record.get("content", "")).strip()
        if not content:
            return None

        if role == "assistant":
            return {"role": "assistant", "content": content}

        speaker_name = record.get("display_name") or record.get("author_name") or "ユーザー"
        return {"role": "user", "content": f"{speaker_name}: {content}"}

    def _get_ai_history(self, channel_id, history=None):
        source_history = history if history is not None else self._get_conversation(channel_id)
        formatted_history = []
        for record in source_history:
            formatted_record = self._format_history_record_for_ai(record)
            if formatted_record:
                formatted_history.append(formatted_record)
        return formatted_history

    def _get_latest_user_prompt(self, record):
        speaker_name = record.get("display_name") or record.get("author_name") or "ユーザー"
        content = str(record.get("content", "")).strip()
        return f"{speaker_name}: {content}"

    def _looks_like_question(self, content):
        lowered = content.lower()
        question_markers = ["?", "？", "教えて", "おしえて", "わからない", "なに", "何", "どう", "なんで", "なぜ", "かな", "でしょうか"]
        return any(marker in lowered for marker in question_markers)

    async def _is_reply_to_bot(self, message):
        reference = message.reference
        if reference is None:
            return False

        resolved = reference.resolved
        if resolved is not None and hasattr(resolved, 'author'):
            return resolved.author == self.bot.user

        if reference.message_id is None:
            return False

        try:
            referenced_message = await message.channel.fetch_message(reference.message_id)
        except Exception:
            return False

        return referenced_message.author == self.bot.user

    async def _should_respond(self, message, channel_id, is_priority):
        now = time.time()
        bot_name = str(self.config.get('bot_name', '')).strip().lower()
        content_lower = message.content.lower()
        is_mentioned = self.bot.user in message.mentions if self.bot.user else False
        is_name_called = bool(bot_name) and bot_name in content_lower
        is_reply_to_bot = await self._is_reply_to_bot(message)
        in_active_session = now < self.channel_active_until.get(channel_id, 0)
        on_cooldown = now - self.channel_last_bot_reply_at.get(channel_id, 0) < self.reply_cooldown_seconds
        is_question = self._looks_like_question(message.content)

        if is_priority:
            self.channel_active_until[channel_id] = now + self.session_timeout_seconds
            return True, "priority", True

        if is_mentioned:
            self.channel_active_until[channel_id] = now + self.session_timeout_seconds
            return True, "mention", True

        if is_reply_to_bot:
            self.channel_active_until[channel_id] = now + self.session_timeout_seconds
            return True, "reply_to_bot", True

        if is_name_called:
            self.channel_active_until[channel_id] = now + self.session_timeout_seconds
            return True, "name_called", True

        if in_active_session and is_question and not on_cooldown:
            return True, "active_session_question", False

        return False, "observe_only", False

    def _mark_bot_replied(self, channel_id):
        now = time.time()
        self.channel_last_bot_reply_at[channel_id] = now
        self.channel_active_until[channel_id] = now + self.session_timeout_seconds

    def _get_summary_message(self, channel_id):
        summary_text = self.channel_summaries.get(channel_id, "").strip()
        if not summary_text:
            return None

        return (
            "以下はこのチャンネルでそれ以前に交わされた会話の要約です。"
            "現在の会話の文脈として必要な範囲で参照してください。\n"
            f"{summary_text}"
        )

    async def _compress_conversation(self, channel_id):
        history = self._get_conversation(channel_id)
        summarize_count = len(history) - self.summary_keep_recent
        if summarize_count <= 0:
            summarize_count = len(history) - self.history_limit
        if summarize_count <= 0:
            return

        print(
            f"Starting conversation compression for channel {channel_id}: "
            f"history_count={len(history)}, summarize_count={summarize_count}, "
            f"keep_recent={self.summary_keep_recent}"
        )

        messages_to_summarize = history[:summarize_count]
        existing_summary = self.channel_summaries.get(channel_id, "")

        transcript_lines = []
        for msg in messages_to_summarize:
            if not isinstance(msg, dict):
                continue

            role = "ユーザー" if msg.get("role") == "user" else "アシスタント"
            speaker_name = msg.get("display_name") or msg.get("author_name") or role
            content = str(msg.get("content", "")).strip()
            if content:
                transcript_lines.append(f"{role}({speaker_name}): {content}")

        if not transcript_lines:
            del history[:summarize_count]
            return

        prompt = (
            "以下の会話ログを、今後の応答に必要な文脈メモとして日本語で簡潔に要約してください。"
            "重要な事実、依頼内容、未解決事項、話題の流れを優先し、雑談の細部や言い回しは削ってください。"
            "誰が何を言ったか、誰に向けた質問や依頼かが分かる形を優先してください。"
            "出力は200〜400文字程度、箇条書きではなく1つの自然な文章で返してください。"
        )
        if existing_summary:
            prompt += f"\n\n既存の要約:\n{existing_summary}"
        prompt += "\n\n今回新たに要約へ取り込む会話ログ:\n" + "\n".join(transcript_lines)

        result = await generate_ai_text(
            prompt,
            self.config,
            extra_system_messages=[
                "あなたは会話履歴を圧縮して保持する要約器です。"
                "人格の演技はせず、事実関係を保った要約だけを返してください。"
                "推測や創作はせず、会話にない情報を足さないでください。"
            ],
            prompt_role="system",
            include_base_system_instruction=False,
        )

        if result.get("success"):
            print(f"Generated conversation summary for channel {channel_id}: {result['response']}")
            self.channel_summaries[channel_id] = result["response"].strip()
            del history[:summarize_count]
            return

        print(f"Conversation summary failed for channel {channel_id}: {result.get('error')}")
        overflow = len(history) - self.history_limit
        if overflow > 0:
            del history[:overflow]

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
        user_record = self._create_user_record(message)
        await self._add_to_conversation(channel_id, user_record)

        # --- 優先キーワードの判定 (レートリミット回避) ---
        is_priority = any(kw in message.content for kw in self.priority_keywords)
        should_respond, reason, bypass_rate_limit = await self._should_respond(message, channel_id, is_priority)

        print(
            f"Chat response decision channel={channel_id} author={message.author} "
            f"respond={should_respond} reason={reason}"
        )

        if not should_respond:
            return

        history = self._get_conversation(channel_id)
        ai_history = self._get_ai_history(channel_id, history[:-1])
        prompt_text = self._get_latest_user_prompt(user_record)

        if is_priority:
            result = await generate_ai_response(
                prompt_text,
                self.config,
                reply_target=message,
                conversation_history=ai_history,
                extra_system_messages=[self._get_summary_message(channel_id)],
                tools=self.tools,
                tool_dispatcher=self._tool_dispatcher,
            )
            if result.get("success"):
                self._mark_bot_replied(channel_id)
                await self._add_to_conversation(channel_id, self._create_assistant_record(result["response"]))
            else:
                await message.reply("(優先キーワードでの応答に失敗しました)")
            return

        # --- レートリミットの判定 ---
        user_id = message.author.id
        now = time.time()
        limit_sec = self.config.get('rate_limit_seconds', 30)
        limit_count = self.config.get('rate_limit_count', 3)

        if not bypass_rate_limit:
            if user_id not in self.user_history:
                self.user_history[user_id] = []

            self.user_history[user_id] = [t for t in self.user_history[user_id] if now - t < limit_sec]

            if len(self.user_history[user_id]) >= limit_count:
                print(f"Rate limit exceeded for {message.author}")
                return

            self.user_history[user_id].append(now)

        # --- AIへのリクエスト（会話履歴付き）---
        result = await generate_ai_response(
            prompt_text,
            self.config,
            reply_target=message,
            conversation_history=ai_history,
            extra_system_messages=[self._get_summary_message(channel_id)],
            tools=self.tools,
            tool_dispatcher=self._tool_dispatcher,
        )
        if result.get("success"):
            self._mark_bot_replied(channel_id)
            await self._add_to_conversation(channel_id, self._create_assistant_record(result["response"]))
        else:
            user_id = message.author.id
            history_count = len(self.user_history.get(user_id, []))
            await message.reply(f"(おしゃべり機能履歴: {history_count}件 / {message.author})")

async def setup(bot):
    config = getattr(bot, "config", None)
    if config is None:
        raise RuntimeError("Bot config is not loaded. Please check startup configuration loading.")
    await bot.add_cog(Chat(bot, config))