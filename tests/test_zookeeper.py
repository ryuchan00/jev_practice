"""ズーキーパーのルールが本家どおりかを見る。"""

from __future__ import annotations

import random

import pytest

from jevbench.games.zookeeper import (
    ANIMALS, CODES, MIN_MATCH, SIZE, TIMER_MAX, ZooKeeper,
    _collapse, _matches, drain_for, legal_moves, points, quota_for, resolve,
)


def _grid(rows: list[str]) -> list[list[str]]:
    return [list(r) for r in rows]


SETTLED = [
    "EGCPHMLE", "GCPHMLEG", "CPHMLEGC", "PHMLEGCP",
    "HMLEGCPH", "MLEGCPHM", "LEGCPHML", "EGCPHMLE",
]


def test_there_are_seven_animals():
    # 本家と同じ 7 種（ゾウ・キリン・ワニ・パンダ・カバ・サル・ライオン）。
    assert len(ANIMALS) == len(CODES) == 7
    assert set(ANIMALS) == {
        "elephant", "giraffe", "crocodile", "panda", "hippo", "monkey", "lion",
    }


def test_matches_finds_horizontal_and_vertical_runs():
    grid = _grid(["EEEPHMLE"] + SETTLED[1:])
    grid[1][0] = grid[2][0] = grid[3][0] = "G"
    hit = _matches(grid)
    assert {(0, 0), (0, 1), (0, 2)} <= hit      # 横 3
    assert {(1, 0), (2, 0), (3, 0)} <= hit      # 縦 3


def test_a_run_of_two_does_not_match():
    assert _matches(_grid(SETTLED)) == set()


def test_a_swap_that_clears_nothing_is_not_a_legal_move():
    """本家では消せない入れ替えはそもそも打てない。"""
    game = ZooKeeper()
    grid = game.start(seed=11).copy_grid()
    moves = legal_moves(grid)
    assert moves
    for a, b in moves:
        work = [row[:] for row in grid]
        work[a[0]][a[1]], work[b[0]][b[1]] = work[b[0]][b[1]], work[a[0]][a[1]]
        assert _matches(work), "打てる手は必ず何か消す"


def test_collapse_drops_cleared_cells_and_leaves_gaps_on_top():
    grid = _grid(SETTLED)
    grid[SIZE - 1][0] = ""
    _collapse(grid)
    assert grid[0][0] == ""                      # 空きは上に寄る
    assert all(grid[r][0] for r in range(1, SIZE))


def test_resolve_without_rng_is_deterministic_and_does_not_refill():
    rows = ["EEEPHMLE"] + SETTLED[1:]
    a, b = _grid(rows), _grid(rows)
    ca, cb = resolve(a), resolve(b)
    assert (ca.caught, ca.cascades, ca.longest) == (cb.caught, cb.cascades, cb.longest)
    assert any(cell == "" for row in a for cell in row), "補充していないので空きが残る"


def test_resolve_counts_which_animal_was_caught():
    clear = resolve(_grid(["EEEPHMLE"] + SETTLED[1:]))
    assert clear.caught["elephant"] >= MIN_MATCH
    assert clear.total == sum(clear.caught.values())


def test_start_deals_a_settled_board_with_moves_available():
    game = ZooKeeper()
    for seed in range(8):
        grid = game.start(seed).copy_grid()
        assert not _matches(grid), "初手から勝手に消えていてはいけない"
        assert legal_moves(grid)
        assert all(cell in CODES for row in grid for cell in row)


def test_quota_and_drain_grow_with_the_level():
    assert quota_for(2) > quota_for(1)
    assert drain_for(2) > drain_for(1)


def test_points_reward_cascades_and_long_lines():
    from jevbench.games.zookeeper import Clear

    flat = Clear(caught={"lion": 3}, cascades=1, longest=3)
    chained = Clear(caught={"lion": 3}, cascades=2, longest=3)
    longer = Clear(caught={"lion": 3}, cascades=1, longest=5)
    assert points(flat) < points(chained)
    assert points(flat) < points(longer)


def test_levelling_up_requires_the_quota_of_every_animal():
    game = ZooKeeper()
    state = game.start(seed=3)
    # 1 種だけ満たしてもレベルは上がらない。
    state.caught["lion"] = state.quota * 5
    assert any(n for n in state.remaining().values())


def test_timer_falls_over_a_game_and_ends_it():
    game = ZooKeeper()
    state = game.start(seed=0)
    rng = random.Random(0)
    seen_over = False
    for _ in range(300):
        candidates = game.candidates(state, 12, rng)
        if not candidates:
            break
        state = game.apply(state, max(candidates, key=lambda c: c.score))
        assert state.timer <= TIMER_MAX, "タイマーは上限を超えない"
        if state.over:
            seen_over = True
            break
    assert seen_over, "ほうっておけばいつかタイマーが切れるはず"
    assert state.level > 1, "その前に何レベルかは上がるはず"


def test_the_board_always_stays_playable():
    game = ZooKeeper()
    state = game.start(seed=2)
    rng = random.Random(2)
    for _ in range(40):
        candidates = game.candidates(state, 12, rng)
        if not candidates:
            break
        state = game.apply(state, max(candidates, key=lambda c: c.score))
        if not state.over:
            assert legal_moves(state.copy_grid()), "手詰まりなら総入れ替えされるはず"


@pytest.mark.parametrize("seed", range(4))
def test_hud_carries_what_the_viewer_needs(seed):
    game = ZooKeeper()
    hud = game.hud(game.start(seed))
    assert hud["kind"] == "zookeeper"
    assert set(hud["caught"]) == set(ANIMALS)
    assert set(hud["codes"]) == set(ANIMALS)
    assert 0 < hud["timer"] <= hud["timer_max"]


def test_a_pre_existing_match_elsewhere_does_not_make_every_swap_legal():
    """手の判定は「入れ替えた 2 マス自身が並ぶか」で行う。

    候補手の評価に使う補充なしの盤面には、まだ消えていない並びが残ることが
    ある。盤面のどこかに並びがあるかで判定すると、その残骸のせいでほぼ全部の
    入れ替えが合法手に見えてしまう。
    """
    grid = _grid([
        "CCCMPMLE",   # 左上に消え残りの並びがある
        "EGCPHMLE", "GCPHMLEG", "PHMLEGCP",
        "HMLEGCPH", "MLEGCPHM", "LEGCPHML", "EGCPHMLE",
    ])
    assert _matches(grid), "前提: 盤面には並びが残っている"
    moves = legal_moves(grid)
    assert len(moves) < 20, f"残骸のせいで手が水増しされている: {len(moves)}"
    for a, b in moves:
        work = [row[:] for row in grid]
        work[a[0]][a[1]], work[b[0]][b[1]] = work[b[0]][b[1]], work[a[0]][a[1]]
        hit = _matches(work)
        assert a in hit or b in hit, "入れ替えた側が並びに入っていない"


def test_a_swap_with_an_empty_cell_is_not_a_move():
    grid = _grid(SETTLED)
    grid[0][0] = ""
    assert all(
        (0, 0) not in (a, b) for a, b in legal_moves(grid)
    ), "補充前の空マスとの入れ替えは手ではない"


def test_moves_after_tracks_the_real_next_position():
    """候補が名乗る moves_after は、実際に打った後の手数と噛み合っていること。

    補充なしの盤面で測るので完全一致はしないが、桁が違ってはいけない。
    ここが壊れると jev / LLM に嘘の数字を見せることになる。
    """
    game = ZooKeeper()
    gaps = []
    for seed in range(4):
        state = game.start(seed)
        rng = random.Random(seed)
        for _ in range(12):
            candidates = game.candidates(state, 12, rng)
            if not candidates:
                break
            pick = max(candidates, key=lambda c: c.score)
            predicted = pick.detail["moves_after"]
            state = game.apply(state, pick)
            gaps.append(abs(predicted - len(legal_moves(state.copy_grid()))))
            if state.over:
                break
    assert gaps
    assert sum(gaps) / len(gaps) < 6, f"予測と実際が離れすぎ: 平均 {sum(gaps)/len(gaps):.1f}"
