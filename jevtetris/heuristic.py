"""候補手のヒューリスティック評価と、上位 N 手の絞り込み。"""

from __future__ import annotations

import random
import string
from dataclasses import dataclass

from .tetris import HEIGHT, WIDTH, Board, Placement

# 記事の評価式:
#   score = -4*holes + 3*cleared_lines - 0.5*max_height - 0.2*roughness
HOLE_WEIGHT = -4.0
CLEAR_WEIGHT = 3.0
HEIGHT_WEIGHT = -0.5
ROUGHNESS_WEIGHT = -0.2

LABELS = string.ascii_uppercase


@dataclass(frozen=True)
class Candidate:
    """ラベル付きの着手候補。ラベルは毎手 A..L を振り直す。"""

    label: str
    placement: Placement
    score: float
    holes: int
    max_height: int
    roughness: int

    def describe(self) -> str:
        """Jev / LLM に見せる 1 行の説明。数値はすべて着手後の盤面のもの。"""
        return (
            f"col {self.placement.col}, rot {self.placement.rotation}, "
            f"clears {self.placement.cleared}, holes {self.holes}, "
            f"max_height {self.max_height}, bumpiness {self.roughness}"
        )

    def as_dict(self) -> dict[str, object]:
        return {
            "column": self.placement.col,
            "rotation": self.placement.rotation,
            "lines_cleared": self.placement.cleared,
            "holes_after": self.holes,
            "max_height_after": self.max_height,
            "bumpiness_after": self.roughness,
        }


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


def top_candidates(
    all_placements: list[Placement],
    limit: int = 12,
    rng: random.Random | None = None,
) -> list[Candidate]:
    """評価上位 limit 手を取り、順番をシャッフルしてからラベルを振る。

    シャッフルしないとラベル A が常に最善手になり、位置バイアスだけで
    正解できてしまう。評価順は Candidate.score に残る。
    """
    scored = []
    for placement in all_placements:
        score, holes, max_height, roughness = evaluate(placement)
        scored.append((score, placement, holes, max_height, roughness))
    scored.sort(key=lambda item: item[0], reverse=True)
    picked = scored[:limit]

    order = list(range(len(picked)))
    (rng or random).shuffle(order)

    return [
        Candidate(
            label=LABELS[i],
            placement=picked[j][1],
            score=picked[j][0],
            holes=picked[j][2],
            max_height=picked[j][3],
            roughness=picked[j][4],
        )
        for i, j in enumerate(order)
    ]


def danger_ratio(board: Board) -> float:
    """盤面の埋まり具合。ゲームオーバー接近度の素朴な指標。"""
    return board.max_height() / HEIGHT


def board_stats(board: Board) -> dict[str, int | float]:
    return {
        "holes": board.holes(),
        "max_height": board.max_height(),
        "bumpiness": board.roughness(),
        "fill_ratio": round(
            sum(1 for row in board.grid for cell in row if cell) / (WIDTH * HEIGHT), 3
        ),
    }
