"""エージェント一式。API キーが無い環境でも heuristic だけは必ず作れる。"""

from __future__ import annotations

from .base import Agent, BaseAgent, Decision, Turn
from .heuristic_agent import HeuristicAgent

AGENT_NAMES = ("heuristic", "jev", "claude", "haiku-cli", "operator")


def build(name: str) -> Agent:
    if name == "heuristic":
        return HeuristicAgent()
    if name == "jev":
        from .jev_agent import JevAgent

        return JevAgent()
    if name == "claude":
        from .claude_agent import ClaudeAgent

        return ClaudeAgent()
    if name == "haiku-cli":
        from .claude_cli_agent import ClaudeCliAgent

        return ClaudeCliAgent()
    if name == "operator":
        from .operator_agent import OperatorAgent

        return OperatorAgent()
    raise ValueError(f"unknown agent: {name} (expected one of {', '.join(AGENT_NAMES)})")


__all__ = ["Agent", "BaseAgent", "Decision", "Turn", "HeuristicAgent", "AGENT_NAMES", "build"]
