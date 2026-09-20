"""テトリスエンジンの不変条件。API は叩かない。"""

from __future__ import annotations

import random

import pytest

from jevbench.games.tetris import (
    HEIGHT, PIECES, WIDTH, Board, SevenBag, Tetris, placements,
)


def test_seven_bag_deals_each_piece_once_per_cycle():
    bag = SevenBag(seed=1)
    assert sorted(bag.next() for _ in range(7)) == sorted(PIECES)


def test_seven_bag_is_reproducible():
    assert [SevenBag(7).next() for _ in range(14)] == [SevenBag(7).next() for _ in range(14)]


@pytest.mark.parametrize("piece", PIECES)
def test_placements_on_empty_board_all_land_on_floor(piece):
    options = placements(Board(), piece)
    assert options
    for placement in options:
        assert max(r for r, _ in placement.cells) == HEIGHT - 1
        assert all(0 <= c < WIDTH for _, c in placement.cells)
        assert placement.cleared == 0


def test_full_row_is_cleared():
    board = Board()
    # 最下段を 4 マスだけ空けて埋め、I ミノを寝かせて入れる。
    for col in range(4, WIDTH):
        board.grid[HEIGHT - 1][col] = "X"
    cleared = [p for p in placements(board, "I") if p.cleared]
    assert cleared, "横 I で 1 ライン消えるはず"
    assert cleared[0].cleared == 1
    assert all(cell == "" for cell in cleared[0].board_after[HEIGHT - 1])


def test_holes_counts_only_cells_under_a_block():
    board = Board()
    board.grid[HEIGHT - 3][0] = "X"
    assert board.holes() == 2
    assert board.column_height(0) == 3


def test_apply_advances_the_piece_and_the_line_count():
    game = Tetris()
    state = game.start(seed=4)
    candidates = game.candidates(state, 12, random.Random(4))
    after = game.apply(state, candidates[0])
    assert after.turn == state.turn + 1
    assert after.piece and after.lines >= state.lines


def test_view_carries_a_non_empty_objective():
    game = Tetris()
    state = game.start(seed=4)
    assert game.view(state)["objective"]
