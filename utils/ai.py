import aiohttp

async def generate_ai_response(target_message_or_text, config, reply_target=None):
    """
    Ollama APIを利用してAIの返信を生成し、Discordに送信する汎用関数。

    Args:
        target_message_or_text: AIのプロンプトとなる文字列、またはDiscordのMessageオブジェクト
        config: Botの設定情報辞書 (システムプロンプトやモデル名を取得)
        reply_target: 返信先となるDiscordのMessageオブジェクトやContextオブジェクト。
                      target_message_or_text がMessageオブジェクトの場合は省略可能。
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

    # configからシステムプロンプトとモデル名を取得
    system_instruction = config.get('system_prompt', "You are a helpful assistant.")
    bot_name = config.get('bot_name', "Bot")
    system_instruction += f"\nあなたの名前は {bot_name} です。"

    target_model = config.get('ai_model', "llama3.2")
    ollama_url = config.get('ollama_url', "http://localhost:11434/api/generate")

    payload = {
        "model": target_model, 
        "prompt": prompt_text,
        "system": system_instruction, 
        "stream": False 
    }

    # 入力中アクションを表示できる場合は表示する
    typing_manager = None
    if hasattr(reply_target, 'channel') and hasattr(reply_target.channel, 'typing'):
        typing_manager = reply_target.channel.typing()
    elif hasattr(reply_target, 'typing'):
        typing_manager = reply_target.typing()

    if typing_manager:
        async with typing_manager:
            return await _send_request(ollama_url, payload, reply_target)
    else:
        return await _send_request(ollama_url, payload, reply_target)

async def _send_request(ollama_url, payload, reply_target):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(ollama_url, json=payload) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    response_text = data.get("response", "ごめんなさい、うまく考えられませんでした。")
                    await reply_target.reply(response_text)
                    return {"success": True, "response": response_text}
                else:
                    error_msg = f"AIサーバーエラー (ステータス: {resp.status})"
                    await reply_target.reply(error_msg)
                    return {"success": False, "error": error_msg}
    except Exception as e:
        print(f"AI APIエラー: {e}")
        error_msg = f"エラーが発生したため、お返事できません。\n`{e}`"
        await reply_target.reply(error_msg)
        return {"success": False, "error": str(e)}
