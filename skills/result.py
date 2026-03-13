from dataclasses import dataclass

import discord


@dataclass
class SkillExecutionResult:
    handled: bool
    prompt: str | None = None
    fallback_text: str | None = None
    embed: discord.Embed | None = None