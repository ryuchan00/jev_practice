"""ズーキーパー風のマッチ3。

本家（KITERETSU / ROBOT, 2003）のルールに寄せている:

- 8x8 に 7 種の動物。隣り合う 2 匹を入れ替える
- 入れ替えて 3 匹以上並ばない手は**そもそも打てない**（元に戻る）
- 消えると上から落ちてきて連鎖する
- 動物を捕獲するとタイマーが回復し、1 手ごとに減る。0 でゲームオーバー
- 動物ごとにノルマがあり、**全種**のノルマを満たすとレベルアップ。
  レベルが上がるほどタイマーの減りが速くなる
- どう動かしても消せなくなったら盤面を総入れ替え（ボーナス点とタイマー回復つき）

「一番多く消える手」ではなく「まだ足りていない動物が消える手」が正解になるので、
候補手の選り分けが素点だけでは決まらない。そこが System One に効かせたい所。
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field, replace
from typing import Any, Iterable

from ..core import Candidate, label_candidates

SIZE = 8
MIN_MATCH = 3

ANIMALS = ("elephant", "giraffe", "crocodile", "panda", "hippo", "monkey", "lion")
CODES = "EGCPHML"
"""盤面テキスト 1 文字ぶんの略号。ANIMALS と同じ並び。"""

CODE_OF = dict(zip(ANIMALS, CODES))
ANIMAL_OF = dict(zip(CODES, ANIMALS))

# --- タイマー（本家は実時間だが、ここは手番制なので 1 手 = 一定量の消費）---
TIMER_MAX = 100.0
TIMER_START = 60.0
DRAIN_PER_TURN = 6.0
"""レベル 1 での 1 手あたりの減り。"""
DRAIN_LEVEL_STEP = 1.5
"""レベルが 1 上がるごとに増える減り。"""
RECOVER_PER_ANIMAL = 1.6
RESHUFFLE_RECOVER = 10.0

# --- ノルマ ---
QUOTA_BASE = 8
QUOTA_LEVEL_STEP = 4
"""レベルが 1 上がるごとに増えるノルマ（全種ぶん）。"""

# --- 得点 ---
POINT_PER_ANIMAL = 10
CASCADE_BONUS = 50
LONG_LINE_BONUS = 30
RESHUFFLE_BONUS = 200
LEVEL_BONUS = 500

# --- 候補手の評価式 ---
NEEDED_WEIGHT = 2.0
"""ノルマがまだ残っている動物を消す手の価値。"""
SURPLUS_WEIGHT = 0.4
"""ノルマ達成済みの動物を消しても、あまり嬉しくない。"""
CASCADE_WEIGHT = 3.0
LONG_LINE_WEIGHT = 2.0
MOBILITY_WEIGHT = 0.3
"""打てる手を減らす一手は、後で総入れ替えに追い込まれるので少し嫌う。"""

Grid = tuple[tuple[str, ...], ...]
Cell = tuple[int, int]
Move = tuple[Cell, Cell]


def quota_for(level: int) -> int:
    return QUOTA_BASE + (level - 1) * QUOTA_LEVEL_STEP


def drain_for(level: int) -> float:
    return DRAIN_PER_TURN + (level - 1) * DRAIN_LEVEL_STEP


@dataclass
class State:
    grid: Grid
    rng: random.Random
    level: int = 1
    score: int = 0
    turn: int = 0
    timer: float = TIMER_START
    caught: dict[str, int] = field(default_factory=lambda: {a: 0 for a in ANIMALS})
    over: bool = False
    last_event: str = ""
    # 直前の 1 手の見た目（UI の演出用。ルールには関係しない）。
    before: Grid | None = None
    swap: tuple[Cell, Cell] | None = None
    popped: list[Cell] = field(default_factory=list)

    def copy_grid(self) -> list[list[str]]:
        return [list(row) for row in self.grid]

    @property
    def quota(self) -> int:
        return quota_for(self.level)

    def remaining(self) -> dict[str, int]:
        """各動物のノルマ残り。全部 0 になるとレベルアップ。"""
        return {a: max(0, self.quota - self.caught[a]) for a in ANIMALS}


def _freeze(grid: list[list[str]]) -> Grid:
    return tuple(tuple(row) for row in grid)


def _matches(grid: list[list[str]]) -> set[Cell]:
    """3 匹以上並んでいるマスの集合。縦横それぞれ走査する。"""
    hit: set[Cell] = set()
    for r in range(SIZE):
        start = 0
        for c in range(1, SIZE + 1):
            same = c < SIZE and grid[r][c] and grid[r][c] == grid[r][start]
            if not same:
                if c - start >= MIN_MATCH and grid[r][start]:
                    hit |= {(r, x) for x in range(start, c)}
                start = c
    for c in range(SIZE):
        start = 0
        for r in range(1, SIZE + 1):
            same = r < SIZE and grid[r][c] and grid[r][c] == grid[start][c]
            if not same:
                if r - start >= MIN_MATCH and grid[start][c]:
                    hit |= {(y, c) for y in range(start, r)}
                start = r
    return hit


def _longest_run(grid: list[list[str]], cells: set[Cell]) -> int:
    """消えた塊の中で一番長い直線。4 以上なら手柄が大きい。"""
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
                grid[r][c] = rng.choice(CODES)


@dataclass
class Clear:
    """1 手を解決した結果。"""

    caught: dict[str, int] = field(default_factory=dict)
    cascades: int = 0
    longest: int = 0
    first_cells: list[Cell] = field(default_factory=list)
    """最初の連鎖で消えたマス。UI の消える演出に使う。"""

    @property
    def total(self) -> int:
        return sum(self.caught.values())


def resolve(grid: list[list[str]], rng: random.Random | None = None) -> Clear:
    """消える限り消し続ける。

    rng を渡すと補充する（本番の 1 手）。渡さないと補充しないので、
    結果が乱数に左右されない（候補手の評価に使う）。
    """
    out = Clear()
    while True:
        hit = _matches(grid)
        if not hit:
            break
        out.longest = max(out.longest, _longest_run(grid, hit))
        out.cascades += 1
        if not out.first_cells:
            out.first_cells = sorted(hit)
        for r, c in hit:
            animal = ANIMAL_OF[grid[r][c]]
            out.caught[animal] = out.caught.get(animal, 0) + 1
            grid[r][c] = ""
        _collapse(grid)
        if rng is None:
            break  # 補充しないなら連鎖は追えないので 1 段で打ち切る
        _refill(grid, rng)
    return out


def _swapped(grid: list[list[str]], a: Cell, b: Cell) -> list[list[str]]:
    out = [row[:] for row in grid]
    out[a[0]][a[1]], out[b[0]][b[1]] = out[b[0]][b[1]], out[a[0]][a[1]]
    return out


def _adjacent_pairs() -> Iterable[Move]:
    for r in range(SIZE):
        for c in range(SIZE):
            if c + 1 < SIZE:
                yield (r, c), (r, c + 1)
            if r + 1 < SIZE:
                yield (r, c), (r + 1, c)


def legal_moves(grid: list[list[str]]) -> list[Move]:
    """入れ替えると何か消える組だけ。消せない入れ替えは本家同様そもそも打てない。"""
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
        grid = [[rng.choice(CODES) for _ in range(SIZE)] for _ in range(SIZE)]
        if _matches(grid):
            continue
        if legal_moves(grid):
            return grid


def points(clear: Clear) -> int:
    return (
        clear.total * POINT_PER_ANIMAL
        + max(0, clear.cascades - 1) * CASCADE_BONUS
        + max(0, clear.longest - MIN_MATCH) * LONG_LINE_BONUS
    )


class ZooKeeper:
    name = "zookeeper"
    goal_label = "level"
    default_goal = 3
    default_max_turns = 300

    def start(self, seed: int) -> State:
        rng = random.Random(seed)
        return State(grid=_freeze(_deal(rng)), rng=rng)

    def candidates(self, state: State, limit: int, rng: random.Random) -> list[Candidate]:
        if state.over:
            return []
        base = state.copy_grid()
        remaining = state.remaining()
        mobility_before = len(legal_moves(base))

        scored = []
        for a, b in legal_moves(base):
            work = _swapped(base, a, b)
            # 補充なしで評価する。乱数で候補の順位が揺れないようにするため。
            clear = resolve(work)
            mobility_after = len(legal_moves(work))

            needed = sum(min(n, remaining[animal]) for animal, n in clear.caught.items())
            surplus = clear.total - needed
            score = (
                NEEDED_WEIGHT * needed
                + SURPLUS_WEIGHT * surplus
                + CASCADE_WEIGHT * max(0, clear.cascades - 1)
                + LONG_LINE_WEIGHT * max(0, clear.longest - MIN_MATCH)
                + MOBILITY_WEIGHT * (mobility_after - mobility_before)
            )
            caught_text = ", ".join(
                f"{n}x {animal}{'' if remaining[animal] else ' (quota met)'}"
                for animal, n in sorted(clear.caught.items())
            )
            summary = (
                f"swap ({a[0]},{a[1]})<->({b[0]},{b[1]}): catches {caught_text}; "
                f"{clear.cascades} cascade(s), longest line {clear.longest}, "
                f"{mobility_after} moves left after"
            )
            detail = {
                "from": list(a),
                "to": list(b),
                "catches": dict(sorted(clear.caught.items())),
                "still_needed_of_those": needed,
                "cascades": clear.cascades,
                "longest_line": clear.longest,
                "moves_after": mobility_after,
            }
            scored.append((score, summary, detail, (a, b)))
        return label_candidates(scored, limit, rng)

    def apply(self, state: State, candidate: Candidate) -> State:
        a, b = candidate.move
        # 入れ替え直後（まだ何も消えていない）を演出用に取っておく。
        swapped = _swapped(state.copy_grid(), a, b)
        before = _freeze(swapped)
        grid = [row[:] for row in swapped]
        clear = resolve(grid, state.rng)

        caught = dict(state.caught)
        for animal, n in clear.caught.items():
            caught[animal] += n

        score = state.score + points(clear)
        timer = state.timer + clear.total * RECOVER_PER_ANIMAL - drain_for(state.level)
        level = state.level
        notes = []

        # 全種のノルマを満たしたらレベルアップ。捕獲数は持ち越さずリセットする。
        if all(caught[animal] >= state.quota for animal in ANIMALS):
            level += 1
            score += LEVEL_BONUS
            caught = {animal: 0 for animal in ANIMALS}
            timer = min(TIMER_MAX, timer + RESHUFFLE_RECOVER)
            notes.append(f"level {level}")

        # どう動かしても消せないなら総入れ替え（本家同様ボーナスつき）。
        if not legal_moves(grid):
            grid = _deal(state.rng)
            score += RESHUFFLE_BONUS
            timer += RESHUFFLE_RECOVER
            notes.append("reshuffle")

        timer = min(TIMER_MAX, timer)
        return replace(
            state,
            grid=_freeze(grid),
            level=level,
            score=score,
            turn=state.turn + 1,
            timer=timer,
            caught=caught,
            over=timer <= 0,
            last_event=" + ".join(notes),
            before=before,
            swap=(a, b),
            popped=clear.first_cells,
        )

    def progress(self, state: State) -> int:
        return state.level

    def rows(self, state: State) -> list[str]:
        return ["".join(row) for row in state.grid]

    def view(self, state: State) -> dict[str, Any]:
        return {
            "board": self.rows(state),
            "legend": {CODE_OF[a]: a for a in ANIMALS}
            | {"_note": f"{SIZE}x{SIZE} grid, (row, col), row 0 is the top."},
            "goal": (
                f"Catch {state.quota} of EVERY animal to clear the level. "
                "The timer drops every turn and is restored by catching animals."
            ),
            "stats": {
                "level": state.level,
                "score": state.score,
                "timer": round(state.timer, 1),
                "still_needed": {a: n for a, n in state.remaining().items() if n},
                "moves_available": len(legal_moves(state.copy_grid())),
            },
        }

    def hud(self, state: State) -> dict[str, Any]:
        return {
            "kind": "zookeeper",
            "level": state.level,
            "score": state.score,
            "timer": round(state.timer, 1),
            "timer_max": TIMER_MAX,
            "quota": state.quota,
            "caught": {a: state.caught[a] for a in ANIMALS},
            "codes": {a: CODE_OF[a] for a in ANIMALS},
            "over": state.over,
            "event": state.last_event,
            "effects": {
                "before": ["".join(row) for row in state.before] if state.before else None,
                "swap": [list(state.swap[0]), list(state.swap[1])] if state.swap else None,
                "popped": [list(c) for c in state.popped],
            },
        }
