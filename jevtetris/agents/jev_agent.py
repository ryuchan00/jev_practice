"""Jev (TypeSafe System One) エージェント。

テキストを生成させるのではなく、候補ラベルに対する choice 質問を 1 回投げ、
確率つきの答えを受け取る。あわせて noul で「詰み寸前か」も同じ往復で聞く。
"""

from __future__ import annotations

import os

from ..heuristic import Candidate, board_stats
from ..tetris import Board
from .base import BaseAgent, Decision, fallback

# 2026-09 時点の System One 料金（USD / 1M tokens）。環境変数で上書きできる。
DEFAULT_INPUT_PRICE = float(os.environ.get("JEV_INPUT_PRICE", "0.10"))
DEFAULT_OUTPUT_PRICE = float(os.environ.get("JEV_OUTPUT_PRICE", "0.40"))

INSTRUCTIONS = (
    "Which candidate placement is the best move? "
    "Prefer moves that clear lines, create no new holes, "
    "and keep the stack low and flat."
)


class JevAgent(BaseAgent):
    name = "jev"

    def __init__(self, model: str | None = None, timeout: float = 10.0) -> None:
        super().__init__()
        from typesafe_sdk import TypeSafeClient  # 遅延 import（未設定でも他エージェントは動く）

        if not os.environ.get("TYPESAFE_API_KEY"):
            raise RuntimeError(
                "TYPESAFE_API_KEY が未設定"
                "（TypeSafe 直、またはロリポップ AI ゲートウェイのキー）"
            )
        # model / base_url は未指定なら SDK が TYPESAFE_DEFAULT_MODEL / TYPESAFE_BASE_URL を読む。
        self.model = model or os.environ.get("TYPESAFE_DEFAULT_MODEL", "jev-latest")
        self.client = TypeSafeClient(model=self.model, timeout=timeout)
        self.input_price_per_mtok = DEFAULT_INPUT_PRICE
        self.output_price_per_mtok = DEFAULT_OUTPUT_PRICE
        self.last_danger: float | None = None

    def _decide(self, board: Board, piece: str, candidates: list[Candidate]) -> Decision:
        from typesafe_sdk import Choice, Noul, TypeSafeError

        state = {
            "board": board.to_text(),
            "current_piece": piece,
            "stats": board_stats(board),
            "legend": "'.' is empty, a letter is a settled block. Row 0 is the top.",
        }
        criteria = {c.label: c.describe() for c in candidates}

        try:
            res = self.client.system_one(
                state=state,
                questions={
                    "best": Choice(instructions=INSTRUCTIONS, criteria=criteria),
                    "urgent": Noul(instructions="Is the board close to game over?"),
                },
            )
        except TypeSafeError as exc:
            return fallback(candidates, f"{type(exc).__name__}: {exc}")

        answer = res.choices["best"]
        self.last_danger = res.nouls["urgent"].noul

        label = answer.choice if answer.choice in criteria else None
        if label is None:
            return fallback(candidates, f"unknown label {answer.choice!r}")

        return Decision(
            label=label,
            latency_ms=0.0,
            confidence=answer.confidence,
            probabilities=dict(answer.probabilities),
            input_tokens=res.usage.input_tokens or 0,
            output_tokens=res.usage.output_tokens or 0,
            note=f"urgent={self.last_danger:.2f}",
        )

    def close(self) -> None:
        self.client.close()
