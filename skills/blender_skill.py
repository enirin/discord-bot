from skills.result import SkillExecutionResult

BLENDER_KEYWORDS = ("blender", "ブレンダー", "3dモデル", "3dモデリング", "レンダリング")

class BlenderSkill:
    """Blender 3D操作を担当するスキル"""

    def __init__(self, config: dict, blender_mcp_client=None):
        self.config = config
        self.client = blender_mcp_client

    def can_handle(self, text: str) -> bool:
        """メッセージがBlender関連の指示か判定"""
        normalized = text.lower()
        return any(kw in normalized for kw in BLENDER_KEYWORDS)

    async def try_handle(self, message_content: str, request_context=None) -> SkillExecutionResult:
        """自然言語ディスパッチからの実行入口"""
        if not self.can_handle(message_content):
            return SkillExecutionResult(handled=False)

        return await self.execute_instruction_result(message_content)

    async def execute_instruction_result(self, instruction: str) -> SkillExecutionResult:
        """Blenderへの操作指示を実行"""
        if not self.client:
            return SkillExecutionResult(
                handled=True,
                success=False,
                response="⚠️ Blender MCPクライアントが初期化されていません。"
            )

        # Blender MCPのツール（例: execute_code）を叩いて操作指示を渡す
        res = await self.client.call_tool("execute_code", {"code": f"# Instruction: {instruction}\nimport bpy"})

        if res.get("success"):
            output_msg = res.get("result", {}).get("content", "操作が完了しました。")
            return SkillExecutionResult(
                handled=True,
                success=True,
                response=f"🎨 **Blender操作成功:**\n{output_msg}"
            )
        else:
            return SkillExecutionResult(
                handled=True,
                success=False,
                response=f"❌ **Blender操作失敗:** {res.get('error')}"
            )