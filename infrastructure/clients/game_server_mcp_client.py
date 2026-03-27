import asyncio
import json
from contextlib import AsyncExitStack

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from mcp.types import EmbeddedResource, TextContent, TextResourceContents


DEFAULT_MCP_URL = "http://127.0.0.1:8000/mcp"
REQUIRED_TOOLS = {
    "list_servers",
    "get_server_status",
    "get_server_maintenance_notes",
    "start_server",
    "stop_server",
}
REQUIRED_RESOURCES = {
    "servers://catalog",
    "servers://status",
}
REQUIRED_RESOURCE_TEMPLATES = {
    "servers://status/{server_id}",
    "games://maintenance/{game}",
}
ERROR_CODE_TO_STATUS = {
    "not_found": 404,
    "invalid_state": 409,
    "runtime_unavailable": 503,
    "configuration_error": 500,
    "internal_error": 500,
}


class GameServerMCPClient:
    def __init__(self, mcp_url: str | None = None):
        self.mcp_url = (mcp_url or DEFAULT_MCP_URL).rstrip("/")
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

    async def get_discovery_summary(self, refresh: bool = False) -> dict:
        async with self._lock:
            if refresh or self._discovery_cache is None:
                await self._connect_locked(force=refresh)
            return dict(self._discovery_cache or {})

    async def list_servers(self) -> dict:
        payload = await self._call_tool("list_servers")
        if not payload.get("success"):
            return payload
        return {
            "success": True,
            "servers": payload.get("data", {}).get("servers", []),
        }

    async def get_server_status(self, server_id: str) -> dict:
        payload = await self._call_tool("get_server_status", {"server_id": server_id})
        if not payload.get("success"):
            return payload
        return {
            "success": True,
            "server": payload.get("data", {}).get("server"),
        }

    async def get_server_maintenance_notes(self, server_id: str) -> dict:
        payload = await self._call_tool("get_server_maintenance_notes", {"server_id": server_id})
        if not payload.get("success"):
            return payload
        return {
            "success": True,
            "data": payload.get("data", {}),
        }

    async def start_server(self, server_id: str) -> dict:
        return await self._call_tool("start_server", {"server_id": server_id})

    async def stop_server(self, server_id: str) -> dict:
        return await self._call_tool("stop_server", {"server_id": server_id})

    async def _call_tool(self, tool_name: str, arguments: dict | None = None) -> dict:
        async with self._lock:
            try:
                await self._connect_locked(force=False)
                assert self._session is not None
                result = await self._session.call_tool(tool_name, arguments=arguments or {})
            except Exception as error:
                await self._close_locked()
                return {
                    "success": False,
                    "error": f"MCP 接続エラー: {error}",
                    "is_connection_error": True,
                }

        payload = self._extract_result_payload(result)
        if result.isError:
            error_payload = payload.get("error") if isinstance(payload, dict) else None
            error_code = None
            error_message = "MCP ツールの実行に失敗しました。"
            error_details = None
            if isinstance(error_payload, dict):
                error_code = error_payload.get("code")
                error_message = error_payload.get("message", error_message)
                error_details = error_payload.get("details")
            elif isinstance(payload, dict):
                error_code = payload.get("code")
                error_message = payload.get("message", error_message)
                error_details = payload.get("details")
            elif isinstance(payload, str) and payload:
                error_message = payload

            return {
                "success": False,
                "error": error_message,
                "error_code": error_code,
                "details": error_details,
                "status": ERROR_CODE_TO_STATUS.get(error_code, 500),
            }

        if isinstance(payload, dict):
            tool_success = bool(payload.get("success", True))
            return {
                "success": tool_success,
                "data": payload,
                "status": 200 if tool_success else 500,
                "error": payload.get("message") if not tool_success else None,
            }

        return {
            "success": True,
            "data": {"result": payload},
            "status": 200,
        }

    async def _connect_locked(self, force: bool) -> dict:
        if force:
            await self._close_locked()

        if self._session is None:
            self._exit_stack = AsyncExitStack()
            read_stream, write_stream, _ = await self._exit_stack.enter_async_context(
                streamable_http_client(self.mcp_url)
            )
            self._session = await self._exit_stack.enter_async_context(ClientSession(read_stream, write_stream))
            await self._session.initialize()

        assert self._session is not None
        tools_response = await self._session.list_tools()
        resources_response = await self._session.list_resources()
        templates_response = await self._session.list_resource_templates()

        tool_names = [tool.name for tool in tools_response.tools]
        resource_uris = [str(resource.uri) for resource in resources_response.resources]
        template_uris = [template.uriTemplate for template in templates_response.resourceTemplates]
        missing_tools = sorted(REQUIRED_TOOLS - set(tool_names))
        missing_resources = sorted(REQUIRED_RESOURCES - set(resource_uris))
        missing_templates = sorted(REQUIRED_RESOURCE_TEMPLATES - set(template_uris))

        self._discovery_cache = {
            "success": not (missing_tools or missing_resources or missing_templates),
            "url": self.mcp_url,
            "tools": tool_names,
            "resources": resource_uris,
            "resource_templates": template_uris,
            "missing_tools": missing_tools,
            "missing_resources": missing_resources,
            "missing_resource_templates": missing_templates,
        }
        return dict(self._discovery_cache)

    async def _close_locked(self):
        if self._exit_stack is not None:
            await self._exit_stack.aclose()
        self._exit_stack = None
        self._session = None
        self._discovery_cache = None

    def _extract_result_payload(self, result) -> dict | str | None:
        structured = getattr(result, "structuredContent", None)
        if structured:
            return structured

        if not getattr(result, "content", None):
            return None

        for content in result.content:
            if isinstance(content, TextContent):
                text = content.text.strip()
                if not text:
                    continue
                parsed = self._maybe_parse_json(text)
                if parsed is not None:
                    return parsed
                return text

            if isinstance(content, EmbeddedResource):
                resource = content.resource
                if isinstance(resource, TextResourceContents):
                    parsed = self._maybe_parse_json(resource.text)
                    if parsed is not None:
                        return parsed
                    return resource.text

        return None

    def _maybe_parse_json(self, text: str) -> dict | list | None:
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            return None
        if isinstance(parsed, (dict, list)):
            return parsed
        return None