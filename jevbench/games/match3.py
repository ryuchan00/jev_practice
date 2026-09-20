"""8x8・6 色のマッチ3。隣り合う 2 マスを入れ替えて 3 つ以上を揃える。

テトリスより候補手が多く（毎手 10〜40 手前後）、連鎖が絡むぶん
「どれが最善か」の判断が効く。System One に投げる質問の形は同じ。
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any, Iterable

from ..core import Candidate, label_candidates

SIZE = 8
COLORS = "RGBYPC"  # Red Green Blue Yellow Purple Cyan
MIN_MATCH = 3

# 1 手の評価式。消した数を基本に、連鎖と 4 個以上の直線を上乗せする。
CLEARED_WEIGHT = 1.0
CASCADE_WEIGHT = 3.0
LONG_MATCH_WEIGHT = 2.0
MOBILITY_WEIGHT = 0.3
"""打てる手が減る一手は、後で詰まるので少し嫌う。"""


Grid = tuple[tuple[str, ...], ...]


@dataclass
class State:
    grid: Grid
    score: int = 0
    turn: int = 0
    rng: random.Random = field(default_factory=random.Random)
    last_cleared: int = 0
    last_cascades: int = 0

    def copy_grid(self) -> list[list[str]]:
        return [list(row) for row in self.grid]


def _freeze(grid: list[list[str]]) -> Grid:
    return tuple(tuple(row) for row in grid)


def _matches(grid: list[list[str]]) -> set[tuple[int, int]]:
    """3 つ以上並んでいるマスの集合。縦横それぞれ走査する。"""
    hit: set[tuple[int, int]] = set()
    for r in range(SIZE):
        run_start = 0
        for c in range(1, SIZE + 1):
            same = c < SIZE and grid[r][c] and grid[r][c] == grid[r][run_start]
            if not same:
                if c - run_start >= MIN_MATCH and grid[r][run_start]:
                    hit |= {(r, x) for x in range(run_start, c)}
                run_start = c
    for c in range(SIZE):
        run_start = 0
        for r in range(1, SIZE + 1):
            same = r < SIZE and grid[r][c] and grid[r][c] == grid[run_start][c]
            if not same:
                if r - run_start >= MIN_MATCH and grid[run_start][c]:
                    hit |= {(y, c) for y in range(run_start, r)}
                run_start = r
    return hit


def _longest_run(grid: list[list[str]], cells: set[tuple[int, int]]) -> int:
    """消えた塊の中で一番長い直線の長さ。4 以上なら手柄が大きい。"""
    if not cells:
        return 0
    best = 0
    for r, c in cells:
        for dr, dc in ((0, 1), (1, 0)):
            length = 1
            for sign in (1, -1):
                y, x = r + dr * sign, c + dc * sign
                while (y, x) in cells and grid[y][x] == grid[r][c]:
                    length += 1
                    y, x = y + dr * sign, x + dc * sign
            best = max(best, length)
    return best


def _collapse(grid: list[list[str]]) -> None:
    """消えたマス（""）を下詰めする。上に空きが残る。"""
    for c in range(SIZE):
        column = [grid[r][c] for r in range(SIZE) if grid[r][c]]
        pad = SIZE - len(column)
        for r in range(SIZE):
            grid[r][c] = "" if r < pad else column[r - pad]


def _refill(grid: list[list[str]], rng: random.Random) -> None:
    for r in range(SIZE):
        for c in range(SIZE):
            if not grid[r][c]:
                grid[r][c] = rng.choice(COLORS)


def resolve(
    grid: list[list[str]], rng: random.Random | None = None
) -> tuple[int, int, int]:
    """消える限り消し続ける。(消した総数, 連鎖回数, 最長の直線) を返す。

    rng を渡すと補充する（本番の 1 手）。渡さないと補充しないので、
    結果が乱数に左右されない（候補手の評価に使う）。
    """
    total = 0
    cascades = 0
    longest = 0
    while True:
        hit = _matches(grid)
        if not hit:
            break
        longest = max(longest, _longest_run(grid, hit))
        total += len(hit)
        cascades += 1
        for r, c in hit:
            grid[r][c] = ""
        _collapse(grid)
        if rng is None:
            break  # 補充しないなら連鎖は追えないので 1 段で打ち切る
        _refill(grid, rng)
    return total, cascades, longest


def _swapped(grid: list[list[str]], a: tuple[int, int], b: tuple[int, int]) -> list[list[str]]:
    out = [row[:] for row in grid]
    (r1, c1), (r2, c2) = a, b
    out[r1][c1], out[r2][c2] = out[r2][c2], out[r1][c1]
    return out


def _adjacent_pairs() -> Iterable[tuple[tuple[int, int], tuple[int, int]]]:
    for r in range(SIZE):
        for c in range(SIZE):
            if c + 1 < SIZE:
                yield (r, c), (r, c + 1)
            if r + 1 < SIZE:
                yield (r, c), (r + 1, c)


def legal_moves(grid: list[list[str]]) -> list[tuple[tuple[int, int], tuple[int, int]]]:
    """入れ替えると何か消える組だけを返す。"""
    out = []
    for a, b in _adjacent_pairs():
        if grid[a[0]][a[1]] == grid[b[0]][b[1]]:
            continue
        if _matches(_swapped(grid, a, b)):
            out.append((a, b))
    return out


def _deal(rng: random.Random) -> list[list[str]]:
    """初手から勝手に消えていない、かつ打つ手がある盤面を配る。"""
    while True:
        grid = [[rng.choice(COLORS) for _ in range(SIZE)] for _ in range(SIZE)]
        if _matches(grid):
            continue
        if legal_moves(grid):
            return grid


def gained(cleared: int, cascades: int, longest: int) -> int:
    """スコア。連鎖と長い直線ほど伸びる。"""
    return cleared * 10 + max(0, cascades - 1) * 50 + max(0, longest - 3) * 30


class Match3:
    name = "match3"
    goal_label = "score"
    default_goal = 3000
    default_max_turns = 60

    def start(self, seed: int) -> State:
        rng = random.Random(seed)
        return State(grid=_freeze(_deal(rng)), rng=rng)

    def candidates(self, state: State, limit: int, rng: random.Random) -> list[Candidate]:
        base = state.copy_grid()
        mobility_before = len(legal_moves(base))
        scored = []
        for a, b in legal_moves(base):
            work = _swapped(base, a, b)
            # 補充なしで評価する。乱数で候補の順位が揺れないようにするため。
            cleared, cascades, longest = resolve(work)
            mobility_after = len(legal_moves(work))
            score = (
                CLEARED_WEIGHT * cleared
                + CASCADE_WEIGHT * max(0, cascades - 1)
                + LONG_MATCH_WEIGHT * max(0, longest - 3)
                + MOBILITY_WEIGHT * (mobility_after - mobility_before)
            )
            summary = (
                f"swap ({a[0]},{a[1]})<->({b[0]},{b[1]}) "
                f"{base[a[0]][a[1]]}/{base[b[0]][b[1]]}, "
                f"clears {cleared}, longest line {longest}, "
                f"moves left after {mobility_after}"
            )
            detail = {
                "from": list(a),
                "to": list(b),
                "colors": [base[a[0]][a[1]], base[b[0]][b[1]]],
                "cleared": cleared,
                "longest_line": longest,
                "moves_after": mobility_after,
            }
            scored.append((score, summary, detail, (a, b)))
        return label_candidates(scored, limit, rng)

    def apply(self, state: State, candidate: Candidate) -> State:
        a, b = candidate.move
        grid = _swapped(state.copy_grid(), a, b)
        cleared, cascades, longest = resolve(grid, state.rng)
        # 入れ替えで打てる手が無くなったら配り直す（詰みではなく仕切り直し）。
        if not legal_moves(grid):
            grid = _deal(state.rng)
        return State(
            grid=_freeze(grid),
            score=state.score + gained(cleared, cascades, longest),
            turn=state.turn + 1,
            rng=state.rng,
            last_cleared=cleared,
            last_cascades=cascades,
        )

    def progress(self, state: State) -> int:
        return state.score

    def rows(self, state: State) -> list[str]:
        return ["".join(row) for row in state.grid]

    def view(self, state: State) -> dict[str, Any]:
        return {
            "board": self.rows(state),
            "legend": (
                f"{SIZE}x{SIZE} grid. Each letter is a gem colour ({'/'.join(COLORS)}). "
                "Coordinates are (row, col), row 0 is the top."
            ),
            "stats": {
                "score": state.score,
                "turn": state.turn,
                "moves_available": len(legal_moves(state.copy_grid())),
            },
        }
