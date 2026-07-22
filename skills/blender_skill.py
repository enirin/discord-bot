import logging
import re
import json
import aiohttp
from skills.result import SkillExecutionResult

logger = logging.getLogger(__name__)

BLENDER_CODE_PROMPT = """You are a pure Python code generator for Blender (bpy).
CRITICAL INSTRUCTION: You MUST output ONLY raw executable Python code. NO intro, NO explanation, NO chatter, NO markdown blocks.

Rules:
1. Start directly with import statements (import bpy, import random, import math).
2. ALWAYS use this SAFE method to find BSDF and set random colors (NEVER use nodes["Principled BSDF"]):

   mat = bpy.data.materials.new(name="Mat")
   mat.use_nodes = True
   # Safe BSDF lookup by type
   bsdf = next((n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'), None)
   if bsdf:
       bsdf.inputs[0].default_value = (random.random(), random.random(), random.random(), 1.0)
   obj.data.materials.append(mat)

3. Write complete loops to create multiple objects as requested.
"""

class BlenderSkill:
    """BLキーワードでBlenderを自動操作するスキル"""

    def __init__(self, config: dict, blender_mcp_client=None, ai_service=None):
        self.config = config
        self.client = blender_mcp_client
        self.ai_service = ai_service
        
        # URLの正規化
        raw_url = str(config.get("ollama_url", "http://127.0.0.1:11434/api/generate"))
        match = re.search(r'(https?://[^\s\]\)]+)', raw_url)
        if match:
            self.ollama_url = match.group(1).rstrip("/")
        else:
            self.ollama_url = "http://127.0.0.1:11434/api/generate"
            
        self.model_name = config.get("ai_model", "qwen2.5-coder:7b")

    def can_handle(self, text: str) -> bool:
        # メッセージの中に 「BL」 または 「bl」 が含まれているか判定
        return "bl" in text.lower()

    async def try_handle(self, message_content: str, request_context=None) -> SkillExecutionResult:
        if not self.can_handle(message_content):
            return SkillExecutionResult(handled=False)

        output_text = await self.execute_instruction_result(message_content, request_context)
        return SkillExecutionResult(handled=True, response_text=output_text)

    async def execute_instruction_result(self, message_content: str, request_context=None) -> str:
        if not self.client:
            return "Blender Client が初期化されていません。"

        try:
            generated_code = await self._generate_code_with_llm(message_content)
            
            logger.info(f"[BlenderSkill] LLM生成コード:\n{generated_code}")

            if not generated_code:
                return "コードがうまく生成できなかったよ…！"

            res = await self.client.call_tool("execute_blender_code", {"code": generated_code})

            return (
                f"Blenderで実行したよ！✨\n"
                f"```python\n{generated_code}\n```"
            )

        except Exception as e:
            logger.error(f"Blender操作中にエラーが発生しました: {e}", exc_info=True)
            return f"Blenderの操作中にエラーが出ちゃった: {e}"

    async def _generate_code_with_llm(self, user_instruction: str) -> str:
        # プロンプトの語尾に import bpy を置くことで雑談を封じる！
        prompt_text = (
            f"{BLENDER_CODE_PROMPT}\n\n"
            f"User request: {user_instruction}\n\n"
            f"Python Code:\nimport bpy\n"
        )
        
        payload = {
            "model": self.model_name,
            "prompt": prompt_text,
            "stream": False,
            "options": {
                "temperature": 0.2
            }
        }

        async with aiohttp.ClientSession() as session:
            try:
                logger.info(f"[BlenderSkill] Ollamaへリクエスト送信中... URL: {self.ollama_url}")
                async with session.post(
                    self.ollama_url, 
                    json=payload, 
                    timeout=aiohttp.ClientTimeout(total=60)
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        response_text = result.get("response", "")

                        # 先頭に強制付加した import bpy を補完
                        full_code = "import bpy\n" + response_text

                        clean_code = re.sub(r"```(?:python)?\s*", "", full_code, flags=re.IGNORECASE)
                        clean_code = re.sub(r"```\s*", "", clean_code).strip()

                        if "import bpy" in clean_code:
                            return clean_code
                    else:
                        logger.warning(f"[BlenderSkill] URL {self.ollama_url} returned status {response.status}")
            except Exception as e:
                logger.warning(f"[BlenderSkill] Request to {self.ollama_url} failed: {e}")

        return self._fallback_code_generator(user_instruction)

    def _fallback_code_generator(self, text: str) -> str:
        normalized = text.lower()
        if "スザンヌ" in normalized or "サル" in normalized:
            return "import bpy; bpy.ops.mesh.primitive_monkey_add(size=2.0, location=(0, 0, 1))"
        elif "消" in normalized or "削除" in normalized:
            return "import bpy; [bpy.data.objects.remove(o, do_unlink=True) for o in bpy.context.scene.objects if o.type == 'MESH']"
        else:
            return "import bpy; bpy.ops.mesh.primitive_uv_sphere_add(radius=1.0, location=(0, 0, 1))"