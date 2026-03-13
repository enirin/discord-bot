import aiohttp
import discord
from discord.ext import commands
import json
import re


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
    )
    return system_instruction


def _build_messages(prompt_text, config, conversation_history=None, extra_system_messages=None, prompt_role=None, include_base_system_instruction=True, tools=None):
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

    final_extra_system_messages = list(extra_system_messages) if extra_system_messages else []
    
    if tools:
        # モデルがネイティブTools対応していない場合のためのプロンプト注入
        tools_list_json = json.dumps(tools, ensure_ascii=False, indent=2)
        tool_prompt = (
            "\n\n[システムルール: ツール呼び出し]\n"
            "あなたは以下の外部ツールを実行することができます。\n"
            f"{tools_list_json}\n\n"
            "ツールを実行して情報を取得したい場合は、回答に他の文章を一切含めず、必ず以下のXMLタグで囲んだJSONフォーマットのみを絶対に出力してください。\n"
            "<tool_call>\n"
            "{\"name\": \"指定するツール名\", \"arguments\": {\"引数名\": \"値\"}}\n"
            "</tool_call>\n"
        )
        final_extra_system_messages.append(tool_prompt)

    if final_extra_system_messages:
        system_messages.extend(
            {"role": "system", "content": message}
            for message in final_extra_system_messages
            if message
        )

    return system_messages + history_messages + [
        {"role": prompt_role, "content": prompt_text}
    ]


async def _request_ollama(config, messages, tools=None):
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
                    response_text = message_obj.get("content", "")
                    tool_calls = message_obj.get("tool_calls", [])
                    
                    # ネイティブサポートがないモデル向けに手動パースする
                    if not tool_calls and tools:
                        match = re.search(r'<tool_call>\s*({.*?})\s*</tool_call>', response_text, re.DOTALL)
                        if match:
                            try:
                                parsed = json.loads(match.group(1))
                                if "name" in parsed:
                                    if "arguments" not in parsed:
                                        parsed["arguments"] = {}
                                    tool_calls.append({"function": parsed})
                                # ユーザーに見えないようにレスポンスからタグごと削除
                                response_text = re.sub(r'<tool_call>.*?</tool_call>', '', response_text, flags=re.DOTALL).strip()
                            except Exception as e:
                                print(f"Manual tool parse error: {e}")

                    return {"success": True, "response": response_text, "tool_calls": tool_calls}

                error_msg = f"AIサーバーエラー (ステータス: {resp.status})"
                return {"success": False, "error": error_msg}
    except Exception as e:
        print(f"AI APIエラー: {e}")
        return {"success": False, "error": str(e)}


async def generate_ai_text(prompt_text, config, conversation_history=None, extra_system_messages=None, prompt_role=None, include_base_system_instruction=True, tools=None):
    messages = _build_messages(
        prompt_text,
        config,
        conversation_history=conversation_history,
        extra_system_messages=extra_system_messages,
        prompt_role=prompt_role,
        include_base_system_instruction=include_base_system_instruction,
        tools=tools,
    )
    return await _request_ollama(config, messages, tools=tools)


async def generate_ai_response(target_message_or_text, config, reply_target=None, conversation_history=None, extra_system_messages=None, tools=None, tool_dispatcher=None):
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
        tools: Ollamaに渡すツールの定義リスト。
        tool_dispatcher: ツール呼び出しを処理し、結果の文字列を返す非同期コールバック関数 (tool_call) -> str
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

        # ツール呼び出しのループ処理用履歴
        current_history = list(conversation_history) if conversation_history else []
        current_prompt = prompt_text
        prompt_role = "user"
        
        # 最大5回ループしてツールを解決する
        for _ in range(5):
            if typing_manager:
                async with typing_manager:
                    result = await generate_ai_text(
                        current_prompt,
                        config,
                        conversation_history=current_history,
                        extra_system_messages=extra_system_messages,
                        prompt_role=prompt_role,
                        tools=tools,
                    )
            else:
                result = await generate_ai_text(
                    current_prompt,
                    config,
                    conversation_history=current_history,
                    extra_system_messages=extra_system_messages,
                    prompt_role=prompt_role,
                    tools=tools,
                )

            if not result.get("success"):
                break

            tool_calls = result.get("tool_calls", [])
            response_text = result.get("response", "")

            # ツール呼び出しがない場合はループ終了して返信
            if not tool_calls or tool_dispatcher is None:
                if not response_text:
                    response_text = "ごめんなさい、うまく考えられませんでした。"
                await _send_discord_response(reply_target, response_text)
                result["response"] = response_text
                return result

            # ツール呼び出しがある場合
            # アシスタントの返答（tool_calls含む）を履歴に追加
            current_history.append({
                "role": "user", "content": current_prompt
            })
            assistant_message = {"role": "assistant", "content": response_text}
            if tool_calls:
                assistant_message["tool_calls"] = tool_calls
            current_history.append(assistant_message)
            
            # 各ツールを実行し、その結果をプロンプトとして追加する（Ollamaフォーマットに準拠して role: tool とする）
            tool_results_texts = []
            for tool_call in tool_calls:
                tool_res = await tool_dispatcher(tool_call)
                # 結果をより明確にパースしやすく伝える
                try:
                    res_json = json.loads(tool_res)
                    success_str = "成功" if res_json.get("success") else "失敗"
                    detail_msg = res_json.get("message") or res_json.get("error") or tool_res
                    content_msg = f"[外部ツール実行結果]\nステータス: {success_str}\n詳細内容: {detail_msg}\n\n上記の結果が事実です。嘘をつかずに、この内容をユーザーに報告してください。"
                except:
                    content_msg = f"[外部ツール実行結果]\n実行結果: {tool_res}"

                current_history.append({
                    "role": "user",
                    "content": content_msg,
                })
            
            # 次のプロンプトを空文字または特定の内容にして再リクエスト
            current_prompt = ""
            # role が user でないとエラーになるか、履歴だけで継続できるか依存するため、
            # historyの末尾にtool応答が追加されたので、改めて空のプロンプト（role: user）で要求する。
            prompt_role = "user"
        
        # ループを抜けてしまった場合（エラー含む）
        if result.get("success"):
            response_text = result.get("response", "ツール呼び出しの処理が上限に達しました。")
            await _send_discord_response(reply_target, response_text)
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
