"""エージェント共通のインタフェースと計測用の型。"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from statistics import median
from typing import Protocol

from ..heuristic import Candidate
from ..tetris import Board


@dataclass
class Decision:
    """1 手ぶんの決定と、その手にかかったコスト。"""

    label: str
    latency_ms: float
    confidence: float | None = None
    probabilities: dict[str, float] = field(default_factory=dict)
    input_tokens: int = 0
    output_tokens: int = 0
    note: str = ""


@dataclass
class Turn:
    """盤面・候補・エージェントの決定をまとめた 1 手ぶんの記録。"""

    index: int
    piece: str
    candidates: list[Candidate]
    decision: Decision
    chosen: Candidate
    best: Candidate

    @property
    def agreed_with_heuristic(self) -> bool:
        return self.chosen.label == self.best.label

    @property
    def regret(self) -> float:
        """最善手との評価値の差。0 なら最善手を選べている。"""
        return self.best.score - self.chosen.score


class Agent(Protocol):
    name: str

    def choose(self, board: Board, piece: str, candidates: list[Candidate]) -> Decision:
        ...

    def close(self) -> None:
        ...


class BaseAgent:
    """レイテンシ計測とコスト集計だけを持つ土台。"""

    name = "base"
    input_price_per_mtok = 0.0
    output_price_per_mtok = 0.0

    def __init__(self) -> None:
        self.latencies: list[float] = []
        self.input_tokens = 0
        self.output_tokens = 0

    def choose(self, board: Board, piece: str, candidates: list[Candidate]) -> Decision:
        started = time.perf_counter()
        decision = self._decide(board, piece, candidates)
        decision.latency_ms = (time.perf_counter() - started) * 1000
        self.latencies.append(decision.latency_ms)
        self.input_tokens += decision.input_tokens
        self.output_tokens += decision.output_tokens
        return decision

    def _decide(self, board: Board, piece: str, candidates: list[Candidate]) -> Decision:
        raise NotImplementedError

    @property
    def median_latency_ms(self) -> float:
        return median(self.latencies) if self.latencies else 0.0

    @property
    def cost_usd(self) -> float:
        return (
            self.input_tokens / 1_000_000 * self.input_price_per_mtok
            + self.output_tokens / 1_000_000 * self.output_price_per_mtok
        )

    def close(self) -> None:
        return None


def fallback(candidates: list[Candidate], reason: str, latency_ms: float = 0.0) -> Decision:
    """API が失敗したときはヒューリスティック最善手に落とす（局を止めない）。"""
    best = max(candidates, key=lambda c: c.score)
    return Decision(label=best.label, latency_ms=latency_ms, note=f"fallback: {reason}")
