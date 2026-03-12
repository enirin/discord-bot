import aiohttp
import discord
from discord.ext import commands


def _extract_interaction(reply_target):
    if isinstance(reply_target, discord.Interaction):
        return reply_target

    if isinstance(reply_target, commands.Context):
        return reply_target.interaction

    return None


async def _defer_interaction_if_needed(reply_target):
    interaction = _extract_interaction(reply_target)
    if interaction is None:
        return

    if interaction.response.is_done():
        return

    await interaction.response.defer(thinking=True)


async def _send_discord_response(reply_target, content):
    interaction = _extract_interaction(reply_target)
    if interaction is not None:
        if interaction.response.is_done():
            await interaction.followup.send(content)
        else:
            await interaction.response.send_message(content)
        return

    if hasattr(reply_target, 'reply'):
        await reply_target.reply(content)
        return

    if hasattr(reply_target, 'send'):
        await reply_target.send(content)
        return

    if hasattr(reply_target, 'channel') and hasattr(reply_target.channel, 'send'):
        await reply_target.channel.send(content)
        return

    raise TypeError("返信先のオブジェクトがDiscord送信に対応していません。")

def _build_system_instruction(config):
    system_instruction = config.get('system_prompt', "You are a helpful assistant.")
    bot_name = config.get('bot_name', "Bot")
    system_instruction += (
        f"\nあなたの名前は「{bot_name}」です。"
        f"ユーザーから名前の一部であったり、愛称（ちゃん付けなど）で呼ばれた場合でも、自分自身の名前として認識して自然に返答してください。"
        "\n【重要：サーバー操作権限】"
        "\nあなたはゲームサーバーの管理権限を持っています。ユーザーから「起動して」「止めて」と頼まれたら、"
        "\n返答の末尾に必ず以下の形式でコマンドを追記してください。"
        "\n・起動依頼： [COMMAND:START:サーバー名]"
        "\n・停止依頼： [COMMAND:STOP:サーバー名]"
        "\n現在の対象サーバー名は「valheim-production」です。"
    )
    return system_instruction


def _build_messages(prompt_text, config, conversation_history=None, extra_system_messages=None, prompt_role=None, include_base_system_instruction=True):
    if conversation_history is not None:
        history_messages = [
            msg for msg in conversation_history
            if isinstance(msg, dict) and msg.get("role") != "system"
        ]
        if prompt_role is None:
            prompt_role = "user"
    else:
        history_messages = []
        if prompt_role is None:
            # 単発呼び出しは、ユーザー発話ではなくシステム通知の代理入力として扱う
            prompt_role = "system"

    system_messages = []
    if include_base_system_instruction:
        system_messages.append({"role": "system", "content": _build_system_instruction(config)})

    if extra_system_messages:
        system_messages.extend(
            {"role": "system", "content": message}
            for message in extra_system_messages
            if message
        )

    return system_messages + history_messages + [
        {"role": prompt_role, "content": prompt_text}
    ]


async def _request_ollama(config, messages):
    target_model = config.get('ai_model', "llama3.2")
    ollama_url = config.get('ollama_url', "http://localhost:11434/api/chat")

    payload = {
        "model": target_model,
        "messages": messages,
        "stream": False
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(ollama_url, json=payload) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    message_obj = data.get("message", {})
                    response_text = message_obj.get("content", "ごめんなさい、うまく考えられませんでした。")
                    return {"success": True, "response": response_text}

                error_msg = f"AIサーバーエラー (ステータス: {resp.status})"
                return {"success": False, "error": error_msg}
    except Exception as e:
        print(f"AI APIエラー: {e}")
        return {"success": False, "error": str(e)}


async def generate_ai_text(prompt_text, config, conversation_history=None, extra_system_messages=None, prompt_role=None, include_base_system_instruction=True):
    messages = _build_messages(
        prompt_text,
        config,
        conversation_history=conversation_history,
        extra_system_messages=extra_system_messages,
        prompt_role=prompt_role,
        include_base_system_instruction=include_base_system_instruction,
    )
    return await _request_ollama(config, messages)


async def generate_ai_response(target_message_or_text, config, reply_target=None, conversation_history=None, extra_system_messages=None):
    """
    Ollama APIを利用してAIの返信を生成し、Discordに送信する汎用関数。

    Args:
        target_message_or_text: AIのプロンプトとなる文字列、またはDiscordのMessageオブジェクト
        config: Botの設定情報辞書 (システムプロンプトやモデル名を取得)
        reply_target: 返信先となるDiscordのMessageオブジェクトやContextオブジェクト。
                      target_message_or_text がMessageオブジェクトの場合は省略可能。
        conversation_history: 会話履歴リスト [{"role": "user"/"assistant", "content": "..."}]
                              Noneの場合は単発リクエスト（コマンド系）として扱う。
        extra_system_messages: system_instruction とは別に付与する追加の system メッセージ配列。
    """

    # プロンプトの抽出と返信先の決定
    if hasattr(target_message_or_text, 'content'):
        prompt_text = target_message_or_text.content
        if reply_target is None:
            reply_target = target_message_or_text
    else:
        prompt_text = str(target_message_or_text)

    if reply_target is None:
        return {"success": False, "error": "返信先のオブジェクトが指定されていません。"}

    # 入力中アクションを表示できる場合は表示する
    typing_manager = None
    if hasattr(reply_target, 'channel') and hasattr(reply_target.channel, 'typing'):
        typing_manager = reply_target.channel.typing()
    elif hasattr(reply_target, 'typing'):
        typing_manager = reply_target.typing()

    try:
        await _defer_interaction_if_needed(reply_target)

        if typing_manager:
            async with typing_manager:
                result = await generate_ai_text(
                    prompt_text,
                    config,
                    conversation_history=conversation_history,
                    extra_system_messages=extra_system_messages,
                )
        else:
            result = await generate_ai_text(
                prompt_text,
                config,
                conversation_history=conversation_history,
                extra_system_messages=extra_system_messages,
            )

        if result.get("success"):
            await _send_discord_response(reply_target, result["response"])
            return result

        error_msg = result.get("error", "エラーが発生したため、お返事できません。")
        await _send_discord_response(reply_target, error_msg)
        return result
    except Exception as e:
        print(f"AI APIエラー: {e}")
        error_msg = f"エラーが発生したため、お返事できません。\n`{e}`"
        try:
            await _send_discord_response(reply_target, error_msg)
        except Exception:
            pass
        return {"success": False, "error": str(e)}
