from aiohttp import web

from application.services.ai_response_service import generate_ai_response


class ChannelReplyTarget:
    """generate_ai_response が期待する reply/typing を満たす簡易ラッパー。"""

    def __init__(self, channel):
        self.channel = channel

    async def reply(self, content):
        await self.channel.send(content)

    def typing(self):
        return self.channel.typing()


class WebEndpointServer:
    """外部連携用Webエンドポイントを提供するHTTPサーバー。"""

    def __init__(self, bot, config):
        self.bot = bot
        self.config = config
        self.host = self.config.get("web_endpoint_host", "127.0.0.1")
        self.port = self.config.get("web_endpoint_port", 5050)
        self.token = self.config.get("web_endpoint_token", None)
        self.runner = None
        self.site = None

    async def start(self):
        app = web.Application()
        self._register_routes(app)

        self.runner = web.AppRunner(app)
        await self.runner.setup()
        self.site = web.TCPSite(self.runner, self.host, self.port)
        await self.site.start()
        print(f"Web endpoint server started on http://{self.host}:{self.port}")

    async def stop(self):
        if self.runner is not None:
            await self.runner.cleanup()
            self.runner = None
            self.site = None

    def _register_routes(self, app):
        app.router.add_post("/tell", self._handle_tell)
        app.router.add_post("/catalog/game-servers", self._handle_refresh_game_server_catalog)
        app.router.add_get("/catalog/game-servers", self._handle_get_game_server_catalog)

    def _authorize(self, request):
        if not self.token:
            return None

        provided_token = request.headers.get("X-Send-Token")
        if provided_token != self.token:
            return web.json_response({"success": False, "error": "unauthorized"}, status=401)

        return None

    async def _read_json(self, request):
        try:
            return await request.json(), None
        except Exception:
            return None, web.json_response({"success": False, "error": "invalid json"}, status=400)

    async def _resolve_channel(self, channel_id):
        channel = self.bot.get_channel(channel_id)
        if channel is not None:
            return channel, None

        try:
            channel = await self.bot.fetch_channel(channel_id)
            return channel, None
        except Exception as e:
            return None, web.json_response(
                {"success": False, "error": f"failed to fetch channel: {e}"},
                status=404,
            )

    async def _handle_tell(self, request):
        auth_error = self._authorize(request)
        if auth_error is not None:
            return auth_error

        data, json_error = await self._read_json(request)
        if json_error is not None:
            return json_error

        prompt = str(data.get("prompt", "")).strip()
        if not prompt:
            return web.json_response({"success": False, "error": "prompt is required"}, status=400)

        channel_id = data.get("channel_id")
        if channel_id is None:
            configured_channels = self.config.get("channel_ids", [])
            channel_id = configured_channels[0] if configured_channels else None

        if channel_id is None:
            return web.json_response({"success": False, "error": "channel_id is required"}, status=400)

        if isinstance(channel_id, bool) or not isinstance(channel_id, int):
            return web.json_response(
                {"success": False, "error": "channel_id must be integer (JSON number)"},
                status=400,
            )

        channel, channel_error = await self._resolve_channel(channel_id)
        if channel_error is not None:
            return channel_error

        reply_target = ChannelReplyTarget(channel)
        result = await generate_ai_response(prompt, self.config, reply_target=reply_target)
        status_code = 200 if result.get("success") else 500
        return web.json_response(result, status=status_code)

    async def _handle_refresh_game_server_catalog(self, request):
        auth_error = self._authorize(request)
        if auth_error is not None:
            return auth_error

        repository = getattr(self.bot, "game_server_catalog_repository", None)
        if repository is None:
            return web.json_response(
                {"success": False, "error": "game_server_catalog_repository is not configured"},
                status=500,
            )

        result = await repository.fetch_latest()
        status_code = 200 if result.get("success") else 500
        return web.json_response(result, status=status_code)

    async def _handle_get_game_server_catalog(self, request):
        auth_error = self._authorize(request)
        if auth_error is not None:
            return auth_error

        repository = getattr(self.bot, "game_server_catalog_repository", None)
        if repository is None:
            return web.json_response(
                {"success": False, "error": "game_server_catalog_repository is not configured"},
                status=500,
            )

        result = await repository.get_cached()
        status_code = 200 if result.get("success") else result.get("status", 500)
        return web.json_response(result, status=status_code)