"""10x20 のテトリスエンジン。7 種ミノ・7-bag 乱数・ハードドロップのみを扱う。"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any

from ..core import Candidate, label_candidates

WIDTH = 10
HEIGHT = 20

# 各ミノの回転状態を (row, col) のセルリストで持つ。row は下方向が正。
SHAPES: dict[str, list[list[tuple[int, int]]]] = {
    "I": [
        [(1, 0), (1, 1), (1, 2), (1, 3)],
        [(0, 2), (1, 2), (2, 2), (3, 2)],
    ],
    "O": [
        [(0, 1), (0, 2), (1, 1), (1, 2)],
    ],
    "T": [
        [(0, 1), (1, 0), (1, 1), (1, 2)],
        [(0, 1), (1, 1), (1, 2), (2, 1)],
        [(1, 0), (1, 1), (1, 2), (2, 1)],
        [(0, 1), (1, 0), (1, 1), (2, 1)],
    ],
    "S": [
        [(0, 1), (0, 2), (1, 0), (1, 1)],
        [(0, 1), (1, 1), (1, 2), (2, 2)],
    ],
    "Z": [
        [(0, 0), (0, 1), (1, 1), (1, 2)],
        [(0, 2), (1, 1), (1, 2), (2, 1)],
    ],
    "J": [
        [(0, 0), (1, 0), (1, 1), (1, 2)],
        [(0, 1), (0, 2), (1, 1), (2, 1)],
        [(1, 0), (1, 1), (1, 2), (2, 2)],
        [(0, 1), (1, 1), (2, 0), (2, 1)],
    ],
    "L": [
        [(0, 2), (1, 0), (1, 1), (1, 2)],
        [(0, 1), (1, 1), (2, 1), (2, 2)],
        [(1, 0), (1, 1), (1, 2), (2, 0)],
        [(0, 0), (0, 1), (1, 1), (2, 1)],
    ],
}

PIECES = tuple(SHAPES)


class SevenBag:
    """7 種を 1 巡ずつ引く袋。seed を固定すれば両エージェントに同じ列を配れる。"""

    def __init__(self, seed: int | None = None) -> None:
        self._rng = random.Random(seed)
        self._bag: list[str] = []

    def next(self) -> str:
        if not self._bag:
            self._bag = list(PIECES)
            self._rng.shuffle(self._bag)
        return self._bag.pop()


@dataclass(frozen=True)
class Placement:
    """1 手ぶんの着手候補。piece を rotation 回転させ col に落とした結果。"""

    piece: str
    rotation: int
    col: int
    cells: tuple[tuple[int, int], ...]
    cleared: int
    board_after: tuple[tuple[str, ...], ...]

    @property
    def landing_row(self) -> int:
        return min(r for r, _ in self.cells)


@dataclass
class Board:
    grid: list[list[str]] = field(
        default_factory=lambda: [["" for _ in range(WIDTH)] for _ in range(HEIGHT)]
    )

    def copy(self) -> "Board":
        return Board([row[:] for row in self.grid])

    def frozen(self) -> tuple[tuple[str, ...], ...]:
        return tuple(tuple(row) for row in self.grid)

    def occupied(self, row: int, col: int) -> bool:
        return bool(self.grid[row][col])

    def column_height(self, col: int) -> int:
        """その列の一番高いブロックの高さ（空なら 0、床から数える）。"""
        for row in range(HEIGHT):
            if self.grid[row][col]:
                return HEIGHT - row
        return 0

    def heights(self) -> list[int]:
        return [self.column_height(c) for c in range(WIDTH)]

    def holes(self) -> int:
        """各列で、ブロックより下にある空きマスの数。"""
        total = 0
        for col in range(WIDTH):
            seen_block = False
            for row in range(HEIGHT):
                if self.grid[row][col]:
                    seen_block = True
                elif seen_block:
                    total += 1
        return total

    def roughness(self) -> int:
        """隣り合う列の高さ差の合計（でこぼこ具合）。"""
        h = self.heights()
        return sum(abs(h[i] - h[i + 1]) for i in range(WIDTH - 1))

    def max_height(self) -> int:
        return max(self.heights())

    def to_text(self) -> str:
        """LLM / Jev に渡すための盤面テキスト。'.' が空きマス。"""
        return "\n".join("".join(cell or "." for cell in row) for row in self.grid)

    def to_rows(self) -> list[str]:
        return [ "".join(cell or "." for cell in row) for row in self.grid]


def _clear_lines(grid: list[list[str]]) -> int:
    kept = [row for row in grid if not all(row)]
    cleared = HEIGHT - len(kept)
    for _ in range(cleared):
        kept.insert(0, ["" for _ in range(WIDTH)])
    grid[:] = kept
    return cleared


def placements(board: Board, piece: str) -> list[Placement]:
    """piece の全回転 x 全列のハードドロップ結果を列挙する。置けない組は捨てる。"""
    out: list[Placement] = []
    for rotation, shape in enumerate(SHAPES[piece]):
        min_c = min(c for _, c in shape)
        max_c = max(c for _, c in shape)
        for offset in range(-min_c, WIDTH - max_c):
            landed = _drop(board, shape, offset)
            if landed is None:
                continue
            work = board.copy()
            for r, c in landed:
                work.grid[r][c] = piece
            cleared = _clear_lines(work.grid)
            out.append(
                Placement(
                    piece=piece,
                    rotation=rotation,
                    col=min(c for _, c in landed),
                    cells=tuple(landed),
                    cleared=cleared,
                    board_after=work.frozen(),
                )
            )
    return out


def _drop(board: Board, shape: list[tuple[int, int]], offset: int) -> list[tuple[int, int]] | None:
    """shape を offset 列ずらして落とし、静止位置のセルを返す。1 マスも入らなければ None。"""
    best: list[tuple[int, int]] | None = None
    for top in range(-4, HEIGHT):
        cells = [(r + top, c + offset) for r, c in shape]
        if any(r >= HEIGHT or c < 0 or c >= WIDTH for r, c in cells):
            break
        if any(r >= 0 and board.occupied(r, c) for r, c in cells):
            break
        best = cells
    if best is None or any(r < 0 for r, _ in best):
        return None
    return best


# 記事の評価式:
#   score = -4*holes + 3*cleared_lines - 0.5*max_height - 0.2*roughness
HOLE_WEIGHT = -4.0
CLEAR_WEIGHT = 3.0
HEIGHT_WEIGHT = -0.5
ROUGHNESS_WEIGHT = -0.2


def evaluate(placement: Placement) -> tuple[float, int, int, int]:
    board = Board([list(row) for row in placement.board_after])
    holes = board.holes()
    max_height = board.max_height()
    roughness = board.roughness()
    score = (
        HOLE_WEIGHT * holes
        + CLEAR_WEIGHT * placement.cleared
        + HEIGHT_WEIGHT * max_height
        + ROUGHNESS_WEIGHT * roughness
    )
    return score, holes, max_height, roughness


@dataclass
class State:
    board: Board
    bag: SevenBag
    piece: str
    lines: int = 0
    turn: int = 0


class Tetris:
    name = "tetris"
    goal_label = "lines"
    default_goal = 20
    default_max_turns = 200

    def start(self, seed: int) -> State:
        bag = SevenBag(seed)
        return State(board=Board(), bag=bag, piece=bag.next())

    def candidates(self, state: State, limit: int, rng: random.Random) -> list[Candidate]:
        scored = []
        for placement in placements(state.board, state.piece):
            score, holes, max_height, roughness = evaluate(placement)
            summary = (
                f"col {placement.col}, rot {placement.rotation}, "
                f"clears {placement.cleared}, holes {holes}, "
                f"max_height {max_height}, bumpiness {roughness}"
            )
            detail = {
                "column": placement.col,
                "rotation": placement.rotation,
                "lines_cleared": placement.cleared,
                "holes_after": holes,
                "max_height_after": max_height,
                "bumpiness_after": roughness,
            }
            scored.append((score, summary, detail, placement))
        return label_candidates(scored, limit, rng)

    def apply(self, state: State, candidate: Candidate) -> State:
        placement: Placement = candidate.move
        return State(
            board=Board([list(row) for row in placement.board_after]),
            bag=state.bag,
            piece=state.bag.next(),
            lines=state.lines + placement.cleared,
            turn=state.turn + 1,
        )

    def progress(self, state: State) -> int:
        return state.lines

    def score(self, state: State) -> int:
        """独立した得点を持たないため、消去ライン数を得点として扱う。"""
        return state.lines

    def rows(self, state: State) -> list[str]:
        return state.board.to_rows()

    def objective(self, state: State) -> str:
        return (
            "Choose the candidate that clears lines, avoids creating holes, and keeps "
            "the stack low and flat."
        )

    def view(self, state: State) -> dict[str, Any]:
        board = state.board
        return {
            "board": self.rows(state),
            "current_piece": state.piece,
            "legend": "'.' is empty, a letter is a settled block. Row 0 is the top.",
            "objective": self.objective(state),
            "stats": {
                "holes": board.holes(),
                "max_height": board.max_height(),
                "bumpiness": board.roughness(),
                "lines": state.lines,
            },
        }

    def hud(self, state: State) -> dict[str, Any]:
        board = state.board
        return {
            "kind": "tetris",
            "lines": state.lines,
            "next_piece": state.piece,
            "holes": board.holes(),
            "max_height": board.max_height(),
            "over": False,
        }
