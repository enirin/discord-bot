from skills.game_server_skill import GameServerSkill
from skills.result import SkillExecutionResult
from skills.system_skill import SystemSkill


class SkillDispatcher:
    def __init__(self, config, game_server_api, game_server_catalog_repository):
        self.handlers = [
            GameServerSkill(config, game_server_api, game_server_catalog_repository),
            SystemSkill(config),
        ]

    async def try_dispatch(self, message_content: str) -> SkillExecutionResult:
        for handler in self.handlers:
            result = await handler.try_handle(message_content)
            if result.handled:
                return result
        return SkillExecutionResult(handled=False)