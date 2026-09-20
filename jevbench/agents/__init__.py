"""エージェント一式。API キーが無い環境でも heuristic だけは必ず作れる。"""

from __future__ import annotations

from .base import Agent, BaseAgent, Decision, Turn
from .heuristic_agent import HeuristicAgent

AGENT_NAMES = ("heuristic", "jev", "claude")


def build(name: str) -> Agent:
    if name == "heuristic":
        return HeuristicAgent()
    if name == "jev":
        from .jev_agent import JevAgent

        return JevAgent()
    if name == "claude":
        from .claude_agent import ClaudeAgent

        return ClaudeAgent()
    raise ValueError(f"unknown agent: {name} (expected one of {', '.join(AGENT_NAMES)})")


__all__ = ["Agent", "BaseAgent", "Decision", "Turn", "HeuristicAgent", "AGENT_NAMES", "build"]
