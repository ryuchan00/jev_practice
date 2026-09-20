"""1 エージェントに 1 局プレイさせ、1 手ごとにイベントを吐き出すループ。"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Iterator

from .agents.base import Agent, BaseAgent, Turn
from .heuristic import Candidate, top_candidates
from .tetris import Board, SevenBag, placements


@dataclass
class MatchConfig:
    seed: int = 0
    max_pieces: int = 200
    target_lines: int = 20
    candidate_limit: int = 12


@dataclass
class MatchResult:
    agent: str
    lines: int
    pieces: int
    reached_target: bool
    topped_out: bool
    median_latency_ms: float
    cost_usd: float
    agreement: float
    mean_regret: float
    fallbacks: int
    fallback_reason: str


def play(agent: Agent, config: MatchConfig | None = None) -> Iterator[dict]:
    """1 局を進めながら手ごとのイベントを yield する。最後に summary を 1 回返す。

    seed が同じなら、どのエージェントでも同じミノ列・同じ候補ラベルになる。
    """
    cfg = config or MatchConfig()
    bag = SevenBag(cfg.seed)
    rng = random.Random(cfg.seed)
    board = Board()
    turns: list[Turn] = []
    lines = 0
    topped_out = False

    for index in range(cfg.max_pieces):
        piece = bag.next()
        options = placements(board, piece)
        if not options:
            topped_out = True
            break

        candidates = top_candidates(options, cfg.candidate_limit, rng)
        decision = agent.choose(board, piece, candidates)
        by_label = {c.label: c for c in candidates}
        chosen = by_label[decision.label]
        best = max(candidates, key=lambda c: c.score)

        board = Board([list(row) for row in chosen.placement.board_after])
        lines += chosen.placement.cleared

        turn = Turn(
            index=index,
            piece=piece,
            candidates=candidates,
            decision=decision,
            chosen=chosen,
            best=best,
        )
        turns.append(turn)

        yield {
            "type": "turn",
            "agent": getattr(agent, "name", "agent"),
            "index": index,
            "piece": piece,
            "board": board.to_rows(),
            "lines": lines,
            "chosen": chosen.label,
            "chosen_column": chosen.placement.col,
            "cleared": chosen.placement.cleared,
            "latency_ms": round(decision.latency_ms, 1),
            "confidence": decision.confidence,
            "agreed": turn.agreed_with_heuristic,
            "regret": round(turn.regret, 2),
            "note": decision.note,
        }

        if lines >= cfg.target_lines:
            break

    yield {
        "type": "summary",
        **_summarize(agent, turns, lines, topped_out, cfg).__dict__,
    }


def _summarize(
    agent: Agent, turns: list[Turn], lines: int, topped_out: bool, cfg: MatchConfig
) -> MatchResult:
    agreed = sum(1 for t in turns if t.agreed_with_heuristic)
    regrets = [t.regret for t in turns]
    # API が落ちた手はヒューリスティックに逃がしている。全手そうなった局を
    # 「計測できた」と読み違えないよう、件数と最初の理由を残す。
    fell_back = [t for t in turns if t.decision.note.startswith("fallback: ")]
    base = agent if isinstance(agent, BaseAgent) else None
    return MatchResult(
        agent=getattr(agent, "name", "agent"),
        lines=lines,
        pieces=len(turns),
        reached_target=lines >= cfg.target_lines,
        topped_out=topped_out,
        median_latency_ms=round(base.median_latency_ms, 1) if base else 0.0,
        cost_usd=round(base.cost_usd, 6) if base else 0.0,
        agreement=round(agreed / len(turns), 3) if turns else 0.0,
        mean_regret=round(sum(regrets) / len(regrets), 3) if regrets else 0.0,
        fallbacks=len(fell_back),
        fallback_reason=fell_back[0].decision.note[len("fallback: "):] if fell_back else "",
    )
