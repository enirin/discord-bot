import aiohttp


class OllamaChatClient:
    def __init__(self, config):
        self.target_model = config.get('ai_model', "llama3.2")
        self.ollama_url = config.get('ollama_url', "http://localhost:11434/api/chat")

    async def request_chat(self, messages):
        payload = {
            "model": self.target_model,
            "messages": messages,
            "stream": False,
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(self.ollama_url, json=payload) as resp:
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