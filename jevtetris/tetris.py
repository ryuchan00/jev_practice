"""10x20 のテトリスエンジン。7 種ミノ・7-bag 乱数・ハードドロップのみを扱う。"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Iterator

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


def iter_pieces(bag: SevenBag) -> Iterator[str]:
    while True:
        yield bag.next()
