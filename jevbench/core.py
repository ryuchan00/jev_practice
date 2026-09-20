"""ゲームに依らない土台。候補手・決定・1 手の記録・エージェントの基底。"""

from __future__ import annotations

import random
import re
import string
import time
from collections.abc import Collection
from dataclasses import dataclass, field
from statistics import median
from typing import Any, Protocol

LABELS = string.ascii_uppercase


def pick_label(text: str, labels: Collection[str]) -> str | None:
    """ASCII の単語に埋もれていない最後の候補ラベルを返す。"""
    if not labels:
        return None

    label_pattern = "|".join(re.escape(label) for label in sorted(labels, key=len, reverse=True))
    # 単純な包含判定では、説明文の単語に含まれるラベルを回答と誤認するため。
    matches = re.findall(rf"(?<![A-Za-z])(?:{label_pattern})(?![A-Za-z])", text)
    return matches[-1] if matches else None


@dataclass(frozen=True)
class Candidate:
    """ラベルを振った着手候補。`move` の中身はゲーム側にしか分からない。"""

    label: str
    score: float
    summary: str
    """モデルに見せる 1 行の説明。"""
    detail: dict[str, Any]
    """同じ内容の構造化版。"""
    move: Any

    def describe(self) -> str:
        return self.summary


def label_candidates(
    scored: list[tuple[float, str, dict[str, Any], Any]],
    limit: int,
    rng: random.Random | None = None,
) -> list[Candidate]:
    """評価上位 limit 件を取り、順番をシャッフルしてから A.. のラベルを振る。

    シャッフルしないとラベル A が常に最善手になり、盤面を読まずに A と
    答えるだけで当たってしまう。評価順は Candidate.score に残る。
    """
    ranked = sorted(scored, key=lambda item: item[0], reverse=True)[:limit]
    order = list(range(len(ranked)))
    (rng or random).shuffle(order)
    return [
        Candidate(
            label=LABELS[i],
            score=ranked[j][0],
            summary=ranked[j][1],
            detail=ranked[j][2],
            move=ranked[j][3],
        )
        for i, j in enumerate(order)
    ]


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

    @property
    def fell_back(self) -> bool:
        return self.note.startswith("fallback: ")

    @property
    def fallback_reason(self) -> str:
        return self.note[len("fallback: "):] if self.fell_back else ""


@dataclass
class Turn:
    index: int
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

    def choose(self, state: dict[str, Any], candidates: list[Candidate]) -> Decision:
        ...

    def close(self) -> None:
        ...


class BaseAgent:
    """レイテンシ計測とトークン / コスト集計だけを持つ土台。"""

    name = "base"
    input_price_per_mtok = 0.0
    output_price_per_mtok = 0.0

    def __init__(self) -> None:
        self.latencies: list[float] = []
        self.input_tokens = 0
        self.output_tokens = 0

    def choose(self, state: dict[str, Any], candidates: list[Candidate]) -> Decision:
        started = time.perf_counter()
        decision = self._decide(state, candidates)
        decision.latency_ms = (time.perf_counter() - started) * 1000
        self.latencies.append(decision.latency_ms)
        self.input_tokens += decision.input_tokens
        self.output_tokens += decision.output_tokens
        return decision

    def _decide(self, state: dict[str, Any], candidates: list[Candidate]) -> Decision:
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


def fallback(candidates: list[Candidate], reason: str) -> Decision:
    """API が失敗したときはヒューリスティック最善手に落として局を止めない。"""
    best = max(candidates, key=lambda c: c.score)
    return Decision(label=best.label, latency_ms=0.0, note=f"fallback: {reason}")
