"""マッチ3 エンジンの不変条件。"""

from __future__ import annotations

import random

from jevbench.games.match3 import (
    COLORS, SIZE, Match3, _collapse, _matches, gained, legal_moves, resolve,
)


def _grid(rows: list[str]) -> list[list[str]]:
    return [list(r) for r in rows]


def test_matches_finds_horizontal_and_vertical_runs():
    grid = _grid([
        "RRRGBYPC",
        "GBYPCGBY",
        "GBYPCGBY",
        "GBYPCGBY",  # 左列の G が縦 3
        "YPCGBYPC",
        "CGBYPCGB",
        "BYPCGBYP",
        "PCGBYPCG",
    ])
    hit = _matches(grid)
    assert {(0, 0), (0, 1), (0, 2)} <= hit      # 横 3
    assert {(1, 0), (2, 0), (3, 0)} <= hit      # 縦 3


def test_a_run_of_two_does_not_match():
    grid = _grid([
        "RRGBYPCG",
        "GBYPCGBY",
        "YPCGBYPC",
        "CGBYPCGB",
        "BYPCGBYP",
        "PCGBYPCG",
        "GBYPCGBY",
        "YPCGBYPC",
    ])
    assert _matches(grid) == set()


def test_collapse_drops_cleared_cells_and_leaves_gaps_on_top():
    grid = _grid(["RGBYPCGB"] * SIZE)
    grid[SIZE - 1][0] = ""
    _collapse(grid)
    assert grid[0][0] == ""                      # 空きは上に寄る
    assert all(grid[r][0] for r in range(1, SIZE))


def test_resolve_without_rng_is_deterministic_and_does_not_refill():
    rows = [
        "RRRGBYPC", "GBYPCGBY", "YPCGBYPC", "CGBYPCGB",
        "BYPCGBYP", "PCGBYPCG", "GBYPCGBY", "YPCGBYPC",
    ]
    a, b = _grid(rows), _grid(rows)
    assert resolve(a) == resolve(b)
    assert any(cell == "" for row in a for cell in row), "補充していないので空きが残る"


def test_every_legal_move_actually_clears_something():
    game = Match3()
    grid = game.start(seed=11).copy_grid()
    moves = legal_moves(grid)
    assert moves
    for a, b in moves:
        work = [row[:] for row in grid]
        work[a[0]][a[1]], work[b[0]][b[1]] = work[b[0]][b[1]], work[a[0]][a[1]]
        assert _matches(work)


def test_start_deals_a_settled_board_with_moves_available():
    game = Match3()
    for seed in range(8):
        grid = game.start(seed).copy_grid()
        assert not _matches(grid), "初手から勝手に消えていてはいけない"
        assert legal_moves(grid)
        assert all(cell in COLORS for row in grid for cell in row)


def test_scoring_rewards_cascades_and_long_lines():
    assert gained(3, 1, 3) < gained(3, 2, 3)     # 連鎖した方が高い
    assert gained(3, 1, 3) < gained(3, 1, 5)     # 長い直線の方が高い


def test_apply_increases_score_and_keeps_the_board_playable():
    game = Match3()
    state = game.start(seed=2)
    for _ in range(15):
        candidates = game.candidates(state, 12, random.Random(0))
        assert candidates
        state = game.apply(state, max(candidates, key=lambda c: c.score))
        assert legal_moves(state.copy_grid()), "打つ手が無い盤面を残してはいけない"
    assert state.score > 0
