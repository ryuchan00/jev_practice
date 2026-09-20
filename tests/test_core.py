"""ゲーム共通の小さな判定処理を見る。"""

import pytest

from jevbench.core import pick_label


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("G", "G"),
        ("G\n", "G"),
        ("The answer is J.", "J"),
        ("Looking at the options, I pick G", "G"),
        ("Based on the quota, C is best", "C"),
        ("I considered B and D, but choose F", "F"),
        ("**G**", "G"),
        ("Looking at the board", None),
        ("", None),
        ("none of these", None),
    ],
)
def test_pick_label(text, expected):
    assert pick_label(text, set("ABCDEFGHIJKL")) == expected
