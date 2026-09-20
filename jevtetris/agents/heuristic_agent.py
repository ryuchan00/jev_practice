"""API を叩かないベースライン。評価式の最善手をそのまま選ぶ。"""

from __future__ import annotations

from ..heuristic import Candidate
from ..tetris import Board
from .base import BaseAgent, Decision


class HeuristicAgent(BaseAgent):
    name = "heuristic"

    def _decide(self, board: Board, piece: str, candidates: list[Candidate]) -> Decision:
        best = max(candidates, key=lambda c: c.score)
        return Decision(label=best.label, latency_ms=0.0, confidence=1.0)
