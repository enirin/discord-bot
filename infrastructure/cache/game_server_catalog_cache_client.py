from copy import deepcopy


class GameServerCatalogCacheClient:
    """ゲームサーバーカタログのキャッシュ実体を管理するクライアント。"""

    def __init__(self):
        self._cached_servers = None

    def read_servers(self):
        if self._cached_servers is None:
            return None
        return deepcopy(self._cached_servers)

    def write_servers(self, servers):
        self._cached_servers = deepcopy(servers)

    def clear(self):
        self._cached_servers = None