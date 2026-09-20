"""API を叩かないベースライン。評価式の最善手をそのまま選ぶ。"""

from __future__ import annotations

from typing import Any

from ..core import BaseAgent, Candidate, Decision


class HeuristicAgent(BaseAgent):
    name = "heuristic"

    def _decide(self, state: dict[str, Any], candidates: list[Candidate]) -> Decision:
        best = max(candidates, key=lambda c: c.score)
        return Decision(label=best.label, latency_ms=0.0, confidence=1.0)
