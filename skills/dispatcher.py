from skills.game_server_skill import GameServerSkill
from skills.result import SkillExecutionResult
from skills.system_skill import SystemSkill


class SkillDispatcher:
    def __init__(self, config, game_server_api, game_server_catalog_repository, operation_service):
        self.handlers = [
            GameServerSkill(config, game_server_api, game_server_catalog_repository, operation_service),
            SystemSkill(config),
        ]

    async def try_dispatch(self, message_content: str, request_context=None) -> SkillExecutionResult:
        for handler in self.handlers:
            result = await handler.try_handle(message_content, request_context)
            if result.handled:
                return result
        return SkillExecutionResult(handled=False)