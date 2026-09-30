"""Core relay primitives.

The first milestone intentionally keeps routing policy separate from Discord and
Codex transports so each integration can be proven independently.
"""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Agent:
    key: str
    display_name: str
    role: str


class Relay:
    """Minimal in-process registry for named collaborators."""

    def __init__(self, agents: list[Agent]) -> None:
        self._agents = {agent.key: agent for agent in agents}

    def resolve(self, key: str) -> Agent:
        try:
            return self._agents[key]
        except KeyError as exc:
            raise ValueError(f"Unknown agent: {key}") from exc

    @property
    def agent_keys(self) -> tuple[str, ...]:
        return tuple(self._agents)
