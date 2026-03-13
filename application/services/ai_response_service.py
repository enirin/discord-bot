import discord
from discord.ext import commands

from infrastructure.clients.ollama_chat_client import OllamaChatClient


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


async def _send_discord_embed(reply_target, embed):
    interaction = _extract_interaction(reply_target)
    if interaction is not None:
        if interaction.response.is_done():
            await interaction.followup.send(embed=embed)
        else:
            await interaction.response.send_message(embed=embed)
        return

    if hasattr(reply_target, 'send'):
        await reply_target.send(embed=embed)
        return

    if hasattr(reply_target, 'channel') and hasattr(reply_target.channel, 'send'):
        await reply_target.channel.send(embed=embed)
        return

    raise TypeError("返信先のオブジェクトがDiscord埋め込み送信に対応していません。")


def _build_system_instruction(config):
    system_instruction = config.get('system_prompt', "You are a helpful assistant.")
    bot_name = config.get('bot_name', "Bot")
    system_instruction += (
        f"\nあなたの名前は「{bot_name}」です。"
        f"ユーザーから名前の一部であったり、愛称（ちゃん付けなど）で呼ばれた場合でも、自分自身の名前として認識して自然に返答してください。"
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


async def generate_ai_text(prompt_text, config, conversation_history=None, extra_system_messages=None, prompt_role=None, include_base_system_instruction=True):
    messages = _build_messages(
        prompt_text,
        config,
        conversation_history=conversation_history,
        extra_system_messages=extra_system_messages,
        prompt_role=prompt_role,
        include_base_system_instruction=include_base_system_instruction,
    )
    client = OllamaChatClient(config)
    return await client.request_chat(messages)


async def generate_ai_response(target_message_or_text, config, reply_target=None, conversation_history=None, extra_system_messages=None):
    if hasattr(target_message_or_text, 'content'):
        prompt_text = target_message_or_text.content
        if reply_target is None:
            reply_target = target_message_or_text
    else:
        prompt_text = str(target_message_or_text)

    if reply_target is None:
        return {"success": False, "error": "返信先のオブジェクトが指定されていません。"}

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


async def deliver_ai_response(prompt_text, config, reply_target, fallback_text=None, embed=None, conversation_history=None, extra_system_messages=None):
    try:
        await _defer_interaction_if_needed(reply_target)
        result = await generate_ai_text(
            prompt_text,
            config,
            conversation_history=conversation_history,
            extra_system_messages=extra_system_messages,
        )

        if result.get("success"):
            response_text = result["response"]
        else:
            response_text = fallback_text or result.get("error", "エラーが発生したため、お返事できません。")

        await _send_discord_response(reply_target, response_text)

        if embed is not None:
            await _send_discord_embed(reply_target, embed)

        return {"success": True, "response": response_text}
    except Exception as e:
        error_text = fallback_text or f"エラーが発生したため、お返事できません。\n`{e}`"
        try:
            await _send_discord_response(reply_target, error_text)
            if embed is not None:
                await _send_discord_embed(reply_target, embed)
        except Exception:
            pass
        return {"success": False, "error": str(e), "response": error_text}