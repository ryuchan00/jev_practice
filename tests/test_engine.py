"""エンジンとヒューリスティックの最低限の不変条件。API は叩かない。"""

from __future__ import annotations

import random

import pytest

from jevtetris.agents import HeuristicAgent
from jevtetris.heuristic import top_candidates
from jevtetris.match import MatchConfig, play
from jevtetris.tetris import HEIGHT, PIECES, WIDTH, Board, SevenBag, placements


def test_seven_bag_deals_each_piece_once_per_cycle():
    bag = SevenBag(seed=1)
    drawn = [bag.next() for _ in range(7)]
    assert sorted(drawn) == sorted(PIECES)


def test_seven_bag_is_reproducible():
    assert [SevenBag(7).next() for _ in range(14)] == [SevenBag(7).next() for _ in range(14)]


@pytest.mark.parametrize("piece", PIECES)
def test_placements_on_empty_board_all_land_on_floor(piece):
    board = Board()
    options = placements(board, piece)
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


def test_top_candidates_keeps_the_best_scoring_moves():
    options = placements(Board(), "T")
    candidates = top_candidates(options, limit=12, rng=random.Random(0))
    assert len(candidates) == 12
    assert [c.label for c in candidates] == list("ABCDEFGHIJKL")

    from jevtetris.heuristic import evaluate

    expected = sorted((evaluate(p)[0] for p in options), reverse=True)[:12]
    assert sorted((c.score for c in candidates), reverse=True) == expected


def test_top_candidates_does_not_always_put_the_best_move_first():
    """ラベル A が常に最善だと、位置バイアスだけで当たってしまう。"""
    options = placements(Board(), "T")
    firsts = {
        top_candidates(options, limit=12, rng=random.Random(seed))[0].score
        for seed in range(20)
    }
    assert len(firsts) > 1


def test_heuristic_agent_reaches_the_line_target():
    events = list(play(HeuristicAgent(), MatchConfig(seed=3, target_lines=10, max_pieces=200)))
    summary = events[-1]
    assert summary["type"] == "summary"
    assert summary["lines"] >= 10, summary
    assert summary["agreement"] == 1.0
    assert summary["mean_regret"] == 0.0


def test_same_seed_gives_the_same_game():
    a = [e for e in play(HeuristicAgent(), MatchConfig(seed=5, max_pieces=30))]
    b = [e for e in play(HeuristicAgent(), MatchConfig(seed=5, max_pieces=30))]
    assert [e.get("board") for e in a] == [e.get("board") for e in b]
