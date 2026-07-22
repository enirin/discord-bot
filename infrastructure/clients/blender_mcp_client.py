import asyncio
import os
from contextlib import AsyncExitStack

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


class BlenderMCPClient:
    """Blender MCP (stdio / uvx 中継) 専用のアダプタークライアント。

    中継プロセス(uvx)内部でのタイムアウトや例外発生時に、
    Bot プロセス全体が道連れで終了しないよう堅牢化しています。
    """

    def __init__(self, mcp_url_or_host: str = "192.168.100.2", port: int = 9876):
        host = mcp_url_or_host.replace("http://", "").replace("https://", "").split(":")[0].split("/")[0]
        self.host = host if host else "192.168.100.2"
        self.port = str(port)

        self._exit_stack: AsyncExitStack | None = None
        self._session: ClientSession | None = None
        self._lock = asyncio.Lock()
        self._discovery_cache: dict[str, object] | None = None

    async def start(self) -> dict:
        async with self._lock:
            return await self._connect_locked(force=False)

    async def close(self):
        async with self._lock:
            await self._close_locked()

    async def _connect_locked(self, force: bool) -> dict:
        if force:
            await self._close_locked()

        if self._session is None:
            self._exit_stack = AsyncExitStack()

            env = os.environ.copy()
            env["BLENDER_HOST"] = self.host
            env["BLENDER_PORT"] = self.port

            server_params = StdioServerParameters(
                command="uvx",
                args=["blender-mcp"],
                env=env,
            )

            try:
                read_stream, write_stream = await self._exit_stack.enter_async_context(
                    stdio_client(server_params)
                )
                self._session = await self._exit_stack.enter_async_context(
                    ClientSession(read_stream, write_stream)
                )
                await self._session.initialize()
            except Exception as e:
                await self._close_locked()
                return {"success": False, "error": f"Failed to initialize stdio client: {e}"}

        assert self._session is not None

        # ツール一覧取得のリトライ（エラー保護）
        tools_response = None
        for attempt in range(5):
            try:
                tools_response = await asyncio.wait_for(self._session.list_tools(), timeout=5.0)
                if tools_response:
                    break
            except (asyncio.TimeoutError, Exception):
                if attempt == 4:
                    break
                await asyncio.sleep(1.0)

        tool_names = [tool.name for tool in tools_response.tools] if tools_response else []

        self._discovery_cache = {
            "success": True,
            "url": f"http://{self.host}:{self.port}",
            "tools": tool_names,
        }
        return dict(self._discovery_cache)

    async def _close_locked(self):
        if self._exit_stack is not None:
            try:
                await self._exit_stack.aclose()
            except Exception:
                pass
        self._exit_stack = None
        self._session = None
        self._discovery_cache = None

    async def call_tool(self, tool_name: str, arguments: dict | None = None) -> dict:
        async with self._lock:
            if self._session is None:
                res = await self._connect_locked(force=False)
                if not res.get("success"):
                    return res

            assert self._session is not None
            try:
                result = await self._session.call_tool(
                    tool_name, arguments=arguments or {}
                )
                return {"success": True, "result": result}
            except Exception as e:
                # 途中で接続が切れた場合はセッションをクリアして再試行可能に
                await self._close_locked()
                return {"success": False, "error": f"Tool execution failed: {e}"}