import aiohttp
import logging

logger = logging.getLogger(__name__)

class BlenderMCPClient:
    """Blender MCP Server と通信するクライアント"""

    def __init__(self, mcp_url: str = "http://127.0.0.1:8000/mcp"):
        self.mcp_url = mcp_url
        self.session = None

    async def start(self) -> dict:
        """起動時の初期化およびツールの導出（Discovery）"""
        # 初期化リクエストの例
        payload = {
            "jsonrpc": "2.0",
            "method": "initialize",
            "params": {},
            "id": 1
        }
        try:
            self.session = aiohttp.ClientSession()
            async with self.session.post(self.mcp_url, json=payload, timeout=10) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return {"success": True, "info": data}
                return {"success": False, "error": f"HTTP {resp.status}"}
        except Exception as e:
            logger.warning(f"Blender MCP connection failed on startup: {e}")
            return {"success": False, "error": str(e)}

    async def call_tool(self, tool_name: str, arguments: dict) -> dict:
        """MCPツール呼び出し"""
        if not self.session:
            self.session = aiohttp.ClientSession()

        payload = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments
            },
            "id": 2
        }
        try:
            async with self.session.post(self.mcp_url, json=payload, timeout=30) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if "error" in data:
                        return {"success": False, "error": data["error"].get("message", "MCP Error")}
                    return {"success": True, "result": data.get("result", {})}
                return {"success": False, "error": f"HTTP Error {resp.status}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def close(self):
        """セッション終了"""
        if self.session:
            await self.session.close()