import aiohttp

class GameServerAPI:
    """ゲームサーバー管理API（Flask）との通信を担当するクラス"""

    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip('/')

    async def list_servers(self):
        """GET /list"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.base_url}/list") as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return {"success": True, "servers": data.get("servers", [])}
                    return {"success": False, "error": f"APIエラー (Status: {resp.status})", "status": resp.status}
        except Exception as e:
            return {"success": False, "error": f"接続エラー: {e}", "is_connection_error": True}

    async def start_server(self, server_name: str):
        """POST /start/{server_name}"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(f"{self.base_url}/start/{server_name}") as resp:
                    data = await resp.json()
                    return {"success": resp.status == 200, "status": resp.status, "data": data}
        except Exception as e:
            return {"success": False, "error": f"接続エラー: {e}", "is_connection_error": True}

    async def stop_server(self, server_name: str):
        """POST /stop/{server_name}"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(f"{self.base_url}/stop/{server_name}") as resp:
                    data = await resp.json()
                    return {"success": resp.status == 200, "status": resp.status, "data": data}
        except Exception as e:
            return {"success": False, "error": f"接続エラー: {e}", "is_connection_error": True}
