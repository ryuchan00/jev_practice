"""CLI: エージェントを指定して 1 局ずつ走らせ、結果を表で出す。"""

from __future__ import annotations

import argparse
import json
import sys

from .agents import AGENT_NAMES, build
from .match import MatchConfig, play


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="jev-tetris", description=__doc__)
    parser.add_argument(
        "--agent",
        action="append",
        choices=AGENT_NAMES,
        help="走らせるエージェント（複数指定可）。既定は heuristic のみ。",
    )
    parser.add_argument("--seed", type=int, default=0, help="ミノ列の seed。全員に同じ列を配る。")
    parser.add_argument("--games", type=int, default=1, help="1 エージェントあたりの局数。")
    parser.add_argument("--target-lines", type=int, default=20)
    parser.add_argument("--max-pieces", type=int, default=200)
    parser.add_argument(
        "--step-delay-ms", type=int, default=0, help="1 手ごとに待つ（観賞用）。"
    )
    parser.add_argument("--verbose", action="store_true", help="1 手ごとに JSON を出す。")
    args = parser.parse_args(argv)

    agents = args.agent or ["heuristic"]
    rows = []

    for name in agents:
        for game in range(args.games):
            try:
                agent = build(name)
            except Exception as exc:  # API キー未設定・SDK 未導入など
                print(f"{name}: スキップ ({exc})", file=sys.stderr)
                break
            config = MatchConfig(
                seed=args.seed + game,
                max_pieces=args.max_pieces,
                target_lines=args.target_lines,
                step_delay_ms=args.step_delay_ms,
            )
            try:
                for event in play(agent, config):
                    if event["type"] == "turn" and args.verbose:
                        print(json.dumps(event, ensure_ascii=False))
                    elif event["type"] == "summary":
                        rows.append({"game": game, **{k: v for k, v in event.items() if k != "type"}})
            finally:
                agent.close()

    _print_table(rows)
    return 0


def _print_table(rows: list[dict]) -> None:
    if not rows:
        print("結果なし")
        return
    header = [
        "agent", "game", "lines", "pieces", "median_latency_ms",
        "cost_usd", "agreement", "mean_regret", "fallbacks",
    ]
    widths = {h: max(len(h), *(len(str(r.get(h, ""))) for r in rows)) for h in header}
    print("  ".join(h.ljust(widths[h]) for h in header))
    print("  ".join("-" * widths[h] for h in header))
    for r in rows:
        print("  ".join(str(r.get(h, "")).ljust(widths[h]) for h in header))

    for r in rows:
        if r.get("fallbacks"):
            print(
                f"\n! {r['agent']} は {r['fallbacks']}/{r['pieces']} 手が API 失敗で"
                f"ヒューリスティックに落ちている: {r['fallback_reason']}"
            )


if __name__ == "__main__":
    raise SystemExit(main())
