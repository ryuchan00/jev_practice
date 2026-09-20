"""1 エージェントに 1 局プレイさせ、1 手ごとにイベントを吐き出すループ。

ゲームの中身は見ない。games.Game の形だけを使う。
"""

from __future__ import annotations

import random
import time
from dataclasses import dataclass
from typing import Iterator

from .core import Agent, BaseAgent, Turn
from .games import Game, build as build_game


@dataclass
class MatchConfig:
    game: str = "zookeeper"
    seed: int = 0
    max_turns: int | None = None
    goal: int | None = None
    turns: int | None = None
    candidate_limit: int = 12
    step_delay_ms: int = 0
    """1 手ごとに待つ時間。API が速すぎて目で追えないときの観賞用。"""


@dataclass
class MatchResult:
    agent: str
    game: str
    goal_label: str
    progress: int
    score: int
    reached_goal: bool
    turns: int
    stuck: bool
    median_latency_ms: float
    input_tokens: int
    output_tokens: int
    cost_usd: float
    agreement: float
    mean_regret: float
    fallbacks: int
    fallback_reason: str


def play(agent: Agent, config: MatchConfig | None = None) -> Iterator[dict]:
    """1 局を進めながら手ごとのイベントを yield し、最後に summary を 1 回返す。

    seed が同じなら、どのエージェントでも同じ初期盤面・同じ候補ラベルになる。
    """
    cfg = config or MatchConfig()
    game: Game = build_game(cfg.game)
    goal = cfg.goal if cfg.goal is not None else game.default_goal
    turn_limit = (
        cfg.turns
        if cfg.turns is not None
        else cfg.max_turns if cfg.max_turns is not None else game.default_max_turns
    )

    meter = agent if isinstance(agent, BaseAgent) else None
    rng = random.Random(cfg.seed)
    state = game.start(cfg.seed)
    turns: list[Turn] = []
    stuck = False

    for index in range(turn_limit):
        candidates = game.candidates(state, cfg.candidate_limit, rng)
        if not candidates:
            stuck = True
            break

        decision = agent.choose(game.view(state), candidates)
        by_label = {c.label: c for c in candidates}
        chosen = by_label[decision.label]
        best = max(candidates, key=lambda c: c.score)

        state = game.apply(state, chosen)
        turn = Turn(index=index, candidates=candidates, decision=decision, chosen=chosen, best=best)
        turns.append(turn)

        yield {
            "type": "turn",
            "agent": getattr(agent, "name", "agent"),
            "game": game.name,
            "index": index,
            "board": game.rows(state),
            "goal_label": game.goal_label,
            "progress": game.progress(state),
            "hud": game.hud(state),
            "chosen": chosen.label,
            "chosen_summary": chosen.summary,
            "latency_ms": round(decision.latency_ms, 1),
            "confidence": decision.confidence,
            "agreed": turn.agreed_with_heuristic,
            "regret": round(turn.regret, 2),
            "note": decision.note,
            # ここまでの累計。UI で使用トークンと料金を常時出すために毎手送る。
            "input_tokens": meter.input_tokens if meter else 0,
            "output_tokens": meter.output_tokens if meter else 0,
            "cost_usd": round(meter.cost_usd, 6) if meter else 0.0,
        }

        # 固定長では、異なるエージェントを同じ手数で比較するため目標を終了条件にしない。
        if cfg.turns is None and game.progress(state) >= goal:
            break
        if game.hud(state).get("over"):
            stuck = True
            break
        if cfg.step_delay_ms:
            time.sleep(cfg.step_delay_ms / 1000)

    yield {
        "type": "summary",
        **_summarize(
            agent, game, turns, game.progress(state), game.score(state), goal, stuck
        ).__dict__,
    }


def _summarize(
    agent: Agent,
    game: Game,
    turns: list[Turn],
    progress: int,
    score: int,
    goal: int,
    stuck: bool,
) -> MatchResult:
    agreed = sum(1 for t in turns if t.agreed_with_heuristic)
    regrets = [t.regret for t in turns]
    # API が落ちた手はヒューリスティックに逃がしている。全手そうなった局を
    # 「計測できた」と読み違えないよう、件数と最初の理由を残す。
    fell_back = [t for t in turns if t.decision.fell_back]
    base = agent if isinstance(agent, BaseAgent) else None
    return MatchResult(
        agent=getattr(agent, "name", "agent"),
        game=game.name,
        goal_label=game.goal_label,
        progress=progress,
        score=score,
        reached_goal=progress >= goal,
        turns=len(turns),
        stuck=stuck,
        median_latency_ms=round(base.median_latency_ms, 1) if base else 0.0,
        input_tokens=base.input_tokens if base else 0,
        output_tokens=base.output_tokens if base else 0,
        cost_usd=round(base.cost_usd, 6) if base else 0.0,
        agreement=round(agreed / len(turns), 3) if turns else 0.0,
        mean_regret=round(sum(regrets) / len(regrets), 3) if regrets else 0.0,
        fallbacks=len(fell_back),
        fallback_reason=fell_back[0].decision.fallback_reason if fell_back else "",
    )
