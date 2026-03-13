class GameServerCatalogRepository:
    """ゲームサーバーカタログ操作の手続きを定義するファサード。"""

    def __init__(self, api_client, cache_client):
        self.api_client = api_client
        self.cache_client = cache_client

    async def fetch_latest(self):
        response = await self.api_client.list_servers()
        if response.get("success"):
            servers = response.get("servers", [])
            self.cache_client.write_servers(servers)
            return {
                "success": True,
                "servers": self.cache_client.read_servers(),
                "source": "network",
            }
        return response

    async def get_cached_or_fetch(self):
        cached_servers = self.cache_client.read_servers()
        if cached_servers is None:
            return await self.fetch_latest()

        return {
            "success": True,
            "servers": cached_servers,
            "source": "cache",
        }

    async def get_cached(self):
        cached_servers = self.cache_client.read_servers()
        if cached_servers is None:
            return {
                "success": False,
                "error": "game server catalog cache is empty",
                "status": 404,
            }

        return {
            "success": True,
            "servers": cached_servers,
            "source": "cache",
        }

    async def refresh_after_mutation(self):
        return await self.fetch_latest()