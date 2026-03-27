import difflib
import re

import discord

from application.services import GameServerRequestContext
from skills.result import SkillExecutionResult
from skills.text_utils import compact_text, normalize_text


START_KEYWORDS = ("起動", "立ち上げ", "立ちあげ", "start", "オンに")
STOP_KEYWORDS = ("停止", "止め", "とめ", "stop", "落として", "シャットダウン", "オフに")
LIST_KEYWORDS = ("一覧", "リスト", "list", "全部", "全体")
STATUS_KEYWORDS = ("状態", "status", "動いてる", "動作", "稼働", "オンライン", "オフライン")
MAINTENANCE_KEYWORDS = ("保守", "メンテ", "メンテナンス", "maintenance")
SERVER_HINTS = ("サーバー", "server")
CONFIRM_KEYWORDS = ("はい", "実行", "実行して", "お願い", "おねがい", "ok", "okay", "yes")
CANCEL_KEYWORDS = ("いいえ", "やめて", "キャンセル", "中止", "no")

COMMON_QUERY_WORDS = {
    "いま",
    "今",
    "現在",
    "サーバー",
    "server",
    "ゲーム",
    "を",
    "は",
    "の",
    "して",
    "ください",
    "くれる",
    "お願い",
    "お願いね",
    "見せて",
    "教えて",
    "おしえて",
    "確認",
    "状態",
    "status",
    "起動",
    "停止",
    "立ち上げ",
    "立ちあげ",
    "止め",
    "とめ",
    "動いてる",
    "動作",
    "稼働",
    "オンライン",
    "オフライン",
    "一覧",
    "リスト",
    "全部",
    "全体",
    "保守",
    "メンテ",
    "メンテナンス",
}


class GameServerSkill:
    def __init__(self, config, api_client, catalog_repository, operation_service):
        self.config = config
        self.api = api_client
        self.catalog_repository = catalog_repository
        self.operation_service = operation_service

    async def try_handle(self, message_content: str, request_context: GameServerRequestContext | None = None) -> SkillExecutionResult:
        pending_result = await self._maybe_handle_pending_operation(message_content, request_context)
        if pending_result.handled:
            return pending_result

        action = self._detect_action(message_content)
        if action is None:
            return SkillExecutionResult(handled=False)

        if action == "list":
            return await self.list_servers_result()
        if action == "status":
            return await self.status_result(message_content)
        if action == "maintenance":
            return await self.maintenance_result(message_content)
        if action == "start":
            return await self.start_server_result(message_content, request_context)
        if action == "stop":
            return await self.stop_server_result(message_content, request_context)

        return SkillExecutionResult(handled=False)

    async def list_servers_result(self) -> SkillExecutionResult:
        res = await self.catalog_repository.fetch_latest()
        if not res["success"]:
            error = res.get("error", "不明なエラー")
            return SkillExecutionResult(
                handled=True,
                prompt=(
                    f"システム情報: ゲームサーバー一覧の取得中にエラーが発生しました"
                    f"（内容: {error}）。ユーザーに謝って状況を報告してください。"
                ),
                fallback_text=f"ゲームサーバー一覧を取得できませんでした。 {error}",
            )

        servers = res.get("servers", [])
        if not servers:
            return SkillExecutionResult(
                handled=True,
                prompt="システム情報: 登録されているゲームサーバーが一つも見つかりませんでした。ユーザーに教えてあげてください。",
                fallback_text="管理対象のゲームサーバーはまだ登録されていません。",
            )

        server_names = ", ".join(server.get("name", "unknown") for server in servers)
        return SkillExecutionResult(
            handled=True,
            prompt=(
                f"システム情報: 現在 {len(servers)} 個のゲームサーバーを確認しました。"
                f"対象は {server_names} です。これから一覧と詳細を表示するので、"
                "ユーザーに短く案内してください。"
            ),
            fallback_text="現在のゲームサーバー一覧です。",
            embed=self._build_servers_embed(servers),
        )

    async def status_result(self, query_text: str | None) -> SkillExecutionResult:
        res = await self.catalog_repository.fetch_latest()
        if not res["success"]:
            error = res.get("error", "不明なエラー")
            return SkillExecutionResult(
                handled=True,
                prompt=(
                    f"システム情報: ゲームサーバー状態の確認中にエラーが発生しました"
                    f"（内容: {error}）。ユーザーに状況を伝えてください。"
                ),
                fallback_text=f"ゲームサーバーの状態を確認できませんでした。 {error}",
            )

        servers = res.get("servers", [])
        resolved_server, resolution_error, has_server_candidate = self._resolve_server_from_raw_query(query_text, servers)
        if not has_server_candidate:
            online_count = sum(1 for server in servers if server.get("status") == "online")
            return SkillExecutionResult(
                handled=True,
                prompt=(
                    f"システム情報: ゲームサーバー全体の状態を確認しました。"
                    f"{len(servers)} 台中 {online_count} 台が online です。"
                    "これから詳細一覧を表示するので、ユーザーに自然に伝えてください。"
                ),
                fallback_text=f"{len(servers)} 台中 {online_count} 台が稼働中です。",
                embed=self._build_servers_embed(servers),
            )

        if resolved_server is None:
            return SkillExecutionResult(
                handled=True,
                prompt=(
                    f"システム情報: ユーザーはゲームサーバーの状態確認を求めていますが、"
                    f"対象サーバーを特定できませんでした。{resolution_error}。"
                    "ユーザーに確認したいサーバー名を聞き返してください。"
                ),
                fallback_text=resolution_error,
            )

        status_response = await self.api.get_server_status(resolved_server.get("name"))
        if status_response.get("success") and status_response.get("server"):
            resolved_server = status_response["server"]

        status = resolved_server.get("status", "unknown")
        stats = resolved_server.get("stats", {})
        return SkillExecutionResult(
            handled=True,
            prompt=(
                f"システム情報: ゲームサーバー「{resolved_server.get('name')}」の状態は {status} です。"
                f"接続先は {resolved_server.get('address')}、プレイヤー数は {stats.get('players')}、"
                f"CPU 使用率は {stats.get('cpu')}%、メモリ使用量は {stats.get('memory')}GB、"
                f"ゲーム内経過日は {resolved_server.get('day')} 日目です。"
                "この状況をユーザーに自然に回答してください。"
            ),
            fallback_text=self._build_status_fallback(resolved_server),
            embed=self._build_single_server_embed(resolved_server),
        )

    async def maintenance_result(self, query_text: str | None) -> SkillExecutionResult:
        res = await self.catalog_repository.get_cached_or_fetch()
        if not res["success"]:
            error = res.get("error", "不明なエラー")
            return SkillExecutionResult(
                handled=True,
                response_text=f"保守情報を確認する前にサーバー一覧を取得できませんでした。 {error}",
            )

        servers = res.get("servers", [])
        resolved_server, resolution_error, has_server_candidate = self._resolve_server_from_raw_query(query_text, servers)
        if not has_server_candidate:
            server_names = ", ".join(f"「{server.get('name')}」" for server in servers)
            return SkillExecutionResult(
                handled=True,
                response_text=f"どのサーバーの保守情報を見るか教えてください。対象は {server_names} です。",
            )

        if resolved_server is None:
            return SkillExecutionResult(handled=True, response_text=resolution_error)

        maintenance = await self.api.get_server_maintenance_notes(resolved_server.get("name"))
        if not maintenance.get("success"):
            return SkillExecutionResult(
                handled=True,
                response_text=self._build_mcp_error_message(maintenance, resolved_server.get("name"), "保守情報の取得"),
            )

        data = maintenance.get("data", {})
        return SkillExecutionResult(
            handled=True,
            response_text=f"{resolved_server.get('name')} の保守情報です。",
            embed=self._build_maintenance_embed(data),
        )

    async def start_server_result(self, query_text: str | None, request_context: GameServerRequestContext | None) -> SkillExecutionResult:
        return await self._prepare_action_result("start_server", "起動", query_text, request_context)

    async def stop_server_result(self, query_text: str | None, request_context: GameServerRequestContext | None) -> SkillExecutionResult:
        return await self._prepare_action_result("stop_server", "停止", query_text, request_context)

    async def confirm_pending_result(self, request_context: GameServerRequestContext | None) -> SkillExecutionResult:
        pending = self.operation_service.consume_pending(request_context)
        if pending is None:
            return SkillExecutionResult(handled=True, response_text="確認待ちの操作はありません。")

        if pending.operation == "start_server":
            action_response = await self.api.start_server(pending.server_id)
            action_name = "起動"
        else:
            action_response = await self.api.stop_server(pending.server_id)
            action_name = "停止"

        if action_response.get("success"):
            await self.catalog_repository.refresh_after_mutation()

        return self._build_action_response(action_name, pending.server_id, action_response)

    async def cancel_pending_result(self, request_context: GameServerRequestContext | None) -> SkillExecutionResult:
        pending = self.operation_service.cancel_pending(request_context)
        if pending is None:
            return SkillExecutionResult(handled=True, response_text="確認待ちの操作はありません。")

        action_name = "起動" if pending.operation == "start_server" else "停止"
        return SkillExecutionResult(
            handled=True,
            response_text=f"{pending.server_id} の{action_name}はキャンセルしました。",
        )

    def _detect_action(self, message_content: str) -> str | None:
        normalized = normalize_text(message_content)
        has_server_hint = any(keyword in normalized for keyword in SERVER_HINTS)

        if any(keyword in normalized for keyword in START_KEYWORDS):
            return "start"
        if any(keyword in normalized for keyword in STOP_KEYWORDS):
            return "stop"
        if any(keyword in normalized for keyword in MAINTENANCE_KEYWORDS):
            return "maintenance"
        if any(keyword in normalized for keyword in LIST_KEYWORDS) and has_server_hint:
            return "list"
        if any(keyword in normalized for keyword in STATUS_KEYWORDS) and has_server_hint:
            return "status"

        return None

    async def _prepare_action_result(self, operation: str, action_name: str, query_text: str | None, request_context: GameServerRequestContext | None) -> SkillExecutionResult:
        res = await self.catalog_repository.get_cached_or_fetch()
        if not res["success"]:
            error = res.get("error", "不明なエラー")
            return SkillExecutionResult(
                handled=True,
                response_text=f"サーバー一覧を取得できないため、{action_name}対象を確認できません。 {error}",
            )

        servers = res.get("servers", [])
        resolved_server, resolution_error, has_server_candidate = self._resolve_server_from_raw_query(query_text, servers)
        if not has_server_candidate:
            server_names = ", ".join(f"「{server.get('name')}」" for server in servers)
            return SkillExecutionResult(
                handled=True,
                response_text=f"どのサーバーを{action_name}するか教えてください。対象は {server_names} です。",
            )

        if resolved_server is None:
            return SkillExecutionResult(handled=True, response_text=resolution_error)

        server_name = resolved_server.get("name")
        is_allowed, denial_reason = self.operation_service.authorize(request_context, operation, server_name)
        if not is_allowed:
            return SkillExecutionResult(
                handled=True,
                response_text=denial_reason or f"{server_name} の{action_name}は許可されていません。",
            )

        pending = self.operation_service.create_pending(operation, server_name, request_context)
        if pending is None:
            return SkillExecutionResult(
                handled=True,
                response_text=f"{server_name} の{action_name}確認を開始できませんでした。もう一度お試しください。",
            )

        return SkillExecutionResult(
            handled=True,
            response_text=f"`{server_name}` を{action_name}します。実行しますか？",
        )

    async def _maybe_handle_pending_operation(self, message_content: str, request_context: GameServerRequestContext | None) -> SkillExecutionResult:
        pending = self.operation_service.peek_pending(request_context)
        if pending is None:
            return SkillExecutionResult(handled=False)

        normalized = normalize_text(message_content)
        if any(keyword in normalized for keyword in CONFIRM_KEYWORDS):
            return await self.confirm_pending_result(request_context)
        if any(keyword in normalized for keyword in CANCEL_KEYWORDS):
            return await self.cancel_pending_result(request_context)
        return SkillExecutionResult(handled=False)

    def _build_action_response(self, action_name: str, server_name: str, response: dict) -> SkillExecutionResult:
        if not response.get("success") and response.get("is_connection_error"):
            error = response.get("error", "接続エラー")
            return SkillExecutionResult(
                handled=True,
                response_text=f"{server_name} の{action_name}中に接続エラーが発生しました。 {error}",
            )

        if not response.get("success"):
            return SkillExecutionResult(
                handled=True,
                response_text=self._build_mcp_error_message(response, server_name, f"{action_name}処理"),
            )

        data = response.get("data", {})
        message = data.get("message", "不明な応答")
        return SkillExecutionResult(
            handled=True,
            response_text=f"{server_name} を{action_name}しました。 {message}",
        )

    def _build_mcp_error_message(self, response: dict, server_name: str, operation_label: str) -> str:
        error_code = response.get("error_code")
        error_message = response.get("error") or "不明なエラー"
        if error_code == "not_found":
            return f"{server_name} は見つかりませんでした。"
        if error_code == "invalid_state":
            return f"{server_name} は現在の状態では {operation_label} を実行できません。 {error_message}"
        if error_code == "runtime_unavailable":
            return f"ゲーム管理サーバーが一時的に利用できません。少し待ってから再試行してください。 {error_message}"
        if error_code == "configuration_error":
            return f"ゲーム管理サーバー側の設定に問題があるため、{operation_label} を続行できません。 {error_message}"
        return f"{server_name} の{operation_label}に失敗しました。 {error_message}"

    def _extract_server_query(self, query_text: str | None) -> str:
        normalized = normalize_text(query_text)
        if not normalized:
            return ""

        stripped = normalized
        for keyword in START_KEYWORDS + STOP_KEYWORDS + LIST_KEYWORDS + STATUS_KEYWORDS + MAINTENANCE_KEYWORDS + SERVER_HINTS:
            stripped = stripped.replace(keyword, " ")

        for word in COMMON_QUERY_WORDS:
            stripped = stripped.replace(word.lower(), " ")

        stripped = re.sub(r"[^0-9a-zぁ-んァ-ヶ一-龠ー]+", " ", stripped)
        return " ".join(part for part in stripped.split() if part)

    def _resolve_server_from_raw_query(self, query_text: str | None, servers: list[dict]) -> tuple[dict | None, str, bool]:
        if not servers:
            return None, "現在は管理対象のゲームサーバーが登録されていません", False

        direct_server, direct_error = self._resolve_server_directly(query_text, servers)
        if direct_server is not None or direct_error:
            return direct_server, direct_error, True

        query_key = self._extract_server_query(query_text)
        if not query_key:
            return None, "", False

        resolved_server, resolution_error = self._resolve_server(query_key, servers)
        return resolved_server, resolution_error, True

    def _resolve_server_directly(self, query_text: str | None, servers: list[dict]) -> tuple[dict | None, str]:
        normalized_query = normalize_text(query_text)
        compact_query = compact_text(query_text)
        if not normalized_query or not compact_query:
            return None, ""

        ranked = []
        for server in servers:
            score = self._score_direct_match(normalized_query, compact_query, server)
            if score > 0:
                ranked.append((score, server))

        if not ranked:
            return None, ""

        ranked.sort(key=lambda item: item[0], reverse=True)
        best_score, best_server = ranked[0]

        if len(ranked) > 1 and ranked[1][0] >= best_score - 0.05:
            candidates = ", ".join(server.get("name", "unknown") for _, server in ranked[:2])
            return None, f"候補が複数あります。対象をもう少し具体的に指定してください: {candidates}"

        return best_server, ""

    def _resolve_server(self, query_key: str, servers: list[dict]) -> tuple[dict | None, str]:
        if not servers:
            return None, "現在は管理対象のゲームサーバーが登録されていません"

        compact_query = compact_text(query_key)
        if not compact_query:
            return None, "確認したいゲームサーバー名が読み取れませんでした"

        ranked = []
        for server in servers:
            score = self._score_server_match(compact_query, server)
            ranked.append((score, server))

        ranked.sort(key=lambda item: item[0], reverse=True)
        best_score, best_server = ranked[0]

        if best_score < 0.72:
            candidates = ", ".join(server.get("name", "unknown") for _, server in ranked[:3])
            return None, f"候補を特定できませんでした。候補: {candidates}"

        if len(ranked) > 1 and ranked[1][0] >= best_score - 0.05 and best_score < 1.5:
            candidates = ", ".join(server.get("name", "unknown") for _, server in ranked[:2])
            return None, f"候補が複数あります。対象をもう少し具体的に指定してください: {candidates}"

        return best_server, ""

    def _score_direct_match(self, normalized_query: str, compact_query: str, server: dict) -> float:
        best_score = 0.0
        for alias in self._build_aliases(server):
            if not alias:
                continue

            if alias == compact_query:
                best_score = max(best_score, 3.0 + (len(alias) / 100.0))
                continue

            if len(alias) >= 2 and alias in compact_query:
                best_score = max(best_score, 2.0 + (len(alias) / 100.0))

        display_name = normalize_text(server.get("name", ""))
        if display_name and display_name in normalized_query:
            best_score = max(best_score, 2.5 + (len(display_name) / 100.0))

        raw_aliases = server.get("server_aliases", [])
        if isinstance(raw_aliases, str):
            raw_aliases = [raw_aliases]
        for alias in raw_aliases:
            normalized_alias = normalize_text(alias)
            if normalized_alias and normalized_alias in normalized_query:
                best_score = max(best_score, 2.5 + (len(normalized_alias) / 100.0))

        return best_score

    def _score_server_match(self, query_key: str, server: dict) -> float:
        aliases = self._build_aliases(server)
        best_score = 0.0
        for alias in aliases:
            if alias == query_key:
                best_score = max(best_score, 2.0 + (len(alias) / 100.0))
                continue

            if alias and (alias in query_key or query_key in alias):
                best_score = max(best_score, 1.5 + (min(len(alias), len(query_key)) / 100.0))
                continue

            similarity = difflib.SequenceMatcher(None, query_key, alias).ratio()
            best_score = max(best_score, similarity)

        return best_score

    def _build_aliases(self, server: dict) -> set[str]:
        server_name = server.get("name", "")
        aliases = {compact_text(server_name)}
        parts = re.split(r"[^0-9a-zA-Zぁ-んァ-ヶ一-龠ー]+", normalize_text(server_name))
        for part in parts:
            compact_part = compact_text(part)
            if compact_part and compact_part not in {"server", "srv"}:
                aliases.add(compact_part)

        server_aliases = server.get("server_aliases", [])
        if isinstance(server_aliases, str):
            server_aliases = [server_aliases]
        for alias in server_aliases:
            compact_alias = compact_text(alias)
            if compact_alias:
                aliases.add(compact_alias)

        return aliases

    def _build_servers_embed(self, servers: list[dict]) -> discord.Embed:
        embed = discord.Embed(title="ゲームサーバー一覧", color=discord.Color.blue())
        for server in servers:
            embed.add_field(
                name=server.get("name", "unknown"),
                value=self._build_server_detail_text(server),
                inline=False,
            )
        return embed

    def _build_single_server_embed(self, server: dict) -> discord.Embed:
        embed = discord.Embed(title=f"{server.get('name', 'unknown')} の状態", color=discord.Color.blue())
        embed.add_field(name="詳細", value=self._build_server_detail_text(server), inline=False)
        return embed

    def _build_maintenance_embed(self, data: dict) -> discord.Embed:
        game = data.get("game", "unknown")
        path = data.get("path", "unknown")
        content = str(data.get("content", "")).strip() or "保守情報は空でした。"
        truncated = content[:3800]
        if len(content) > len(truncated):
            truncated += "\n..."

        embed = discord.Embed(title=f"{game} 保守情報", color=discord.Color.orange())
        embed.add_field(name="server", value=str(data.get("server_id", "unknown")), inline=False)
        embed.add_field(name="path", value=path, inline=False)
        embed.description = truncated
        return embed

    def _build_server_detail_text(self, server: dict) -> str:
        status = server.get("status", "unknown")
        status_emoji = "🟢" if status == "online" else "🔴" if status == "offline" else "🟡"
        stats = server.get("stats", {})
        return (
            f"Status: {status_emoji} {status}\n"
            f"Address: `{server.get('address')}`\n"
            f"Players: {stats.get('players')}\n"
            f"Day: {server.get('day')}\n"
            f"Resources: CPU {stats.get('cpu')}% / Mem {stats.get('memory')}GB"
        )

    def _build_status_fallback(self, server: dict) -> str:
        status = server.get("status", "unknown")
        stats = server.get("stats", {})
        return (
            f"{server.get('name')} は現在 {status} です。"
            f" プレイヤー数は {stats.get('players')}、CPU は {stats.get('cpu')}%、"
            f"メモリは {stats.get('memory')}GB です。"
        )