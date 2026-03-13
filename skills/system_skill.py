import subprocess

from skills.result import SkillExecutionResult
from skills.text_utils import normalize_text


LOAD_KEYWORDS = ("負荷", "load", "cpu", "メモリ", "memory", "uptime", "リソース")
PING_KEYWORDS = ("ping", "疎通", "生存確認", "元気", "生きてる", "応答")
SERVER_HINTS = ("サーバー", "server")


class SystemSkill:
    def __init__(self, config):
        self.config = config

    async def try_handle(self, message_content: str) -> SkillExecutionResult:
        normalized = normalize_text(message_content)

        if any(keyword in normalized for keyword in LOAD_KEYWORDS):
            return await self.load_result()

        if any(keyword in normalized for keyword in PING_KEYWORDS):
            has_server_hint = any(keyword in normalized for keyword in SERVER_HINTS)
            if not has_server_hint:
                return await self.ping_result()

        return SkillExecutionResult(handled=False)

    async def load_result(self) -> SkillExecutionResult:
        try:
            uptime_res = subprocess.run(["uptime"], capture_output=True, text=True, check=False)
            free_res = subprocess.run(["free", "-h"], capture_output=True, text=True, check=False)
            return SkillExecutionResult(
                handled=True,
                prompt=(
                    "システム情報: ユーザーからサーバー負荷情報の確認依頼が来ました。"
                    f"現在の Uptime 情報は「{uptime_res.stdout.strip()}」、"
                    f"Memory 使用状況は「{free_res.stdout.strip()}」です。"
                    "この情報を元に、現在のサーバーの調子を自然に報告してください。"
                ),
                fallback_text=(
                    "現在のサーバー負荷情報です。\n"
                    f"uptime: {uptime_res.stdout.strip()}\n"
                    f"memory: {free_res.stdout.strip()}"
                ),
            )
        except Exception as error:
            return SkillExecutionResult(
                handled=True,
                prompt=(
                    f"システム情報: サーバー負荷情報の取得中にエラーが発生しました（内容: {error}）。"
                    "ユーザーに謝って伝えてください。"
                ),
                fallback_text=f"サーバー負荷情報の取得中にエラーが発生しました。 {error}",
            )

    async def ping_result(self) -> SkillExecutionResult:
        return SkillExecutionResult(
            handled=True,
            prompt="システム情報: ユーザーが生存確認を行いました。元気に反応できることを自然に伝えてください。",
            fallback_text="応答できます。Bot は稼働中です。",
        )