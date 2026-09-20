"""CLI: ゲームとエージェントを指定して走らせ、結果を表で出す。"""

from __future__ import annotations

import argparse
import json
import sys

from .agents import AGENT_NAMES, build
from .games import GAME_NAMES
from .match import MatchConfig, play

COLUMNS = [
    "agent", "game", "seed", "progress", "score", "turns",
    "median_latency_ms", "in_tok", "out_tok", "cost_usd",
    "agreement", "mean_regret", "fallbacks",
]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="jev-bench", description=__doc__)
    parser.add_argument("--game", choices=GAME_NAMES, default="zookeeper")
    parser.add_argument(
        "--agent", action="append", choices=AGENT_NAMES,
        help="走らせるエージェント（複数指定可）。既定は heuristic のみ。",
    )
    parser.add_argument("--seed", type=int, default=0, help="全員に同じ局を配る seed。")
    parser.add_argument("--games", type=int, default=1, help="1 エージェントあたりの局数。")
    parser.add_argument("--goal", type=int, default=None, help="目標ライン数 / スコア。")
    parser.add_argument("--turns", type=int, default=None, help="目標を無視して固定手数で走らせる。")
    parser.add_argument("--max-turns", type=int, default=None)
    parser.add_argument("--step-delay-ms", type=int, default=0, help="1 手ごとに待つ（観賞用）。")
    parser.add_argument("--verbose", action="store_true", help="1 手ごとに JSON を出す。")
    args = parser.parse_args(argv)

    rows = []
    for name in args.agent or ["heuristic"]:
        for game_index in range(args.games):
            try:
                agent = build(name)
            except Exception as exc:  # API キー未設定・SDK 未導入など
                print(f"{name}: スキップ ({exc})", file=sys.stderr)
                break
            seed = args.seed + game_index
            config = MatchConfig(
                game=args.game, seed=seed, goal=args.goal, turns=args.turns,
                max_turns=args.max_turns, step_delay_ms=args.step_delay_ms,
            )
            try:
                for event in play(agent, config):
                    if event["type"] == "turn" and args.verbose:
                        print(json.dumps(event, ensure_ascii=False))
                    elif event["type"] == "summary":
                        rows.append({
                            "seed": seed,
                            "in_tok": event["input_tokens"],
                            "out_tok": event["output_tokens"],
                            **event,
                        })
            finally:
                agent.close()

    _print_table(rows)
    return 0


def _print_table(rows: list[dict]) -> None:
    if not rows:
        print("結果なし")
        return
    widths = {c: max(len(c), *(len(str(r.get(c, ""))) for r in rows)) for c in COLUMNS}
    print("  ".join(c.ljust(widths[c]) for c in COLUMNS))
    print("  ".join("-" * widths[c] for c in COLUMNS))
    for r in rows:
        print("  ".join(str(r.get(c, "")).ljust(widths[c]) for c in COLUMNS))

    for r in rows:
        if r.get("fallbacks"):
            print(
                f"\n! {r['agent']} は {r['fallbacks']}/{r['turns']} 手が API 失敗で"
                f"ヒューリスティックに落ちている: {r['fallback_reason']}"
            )


if __name__ == "__main__":
    raise SystemExit(main())
