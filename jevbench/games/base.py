"""ゲームが満たすべき形。match.py はこれだけを見て 1 局を回す。"""

from __future__ import annotations

import random
from typing import Any, Protocol


class Game(Protocol):
    name: str
    goal_label: str
    """進捗の単位（テトリスなら "lines"、マッチ3 なら "score"）。"""
    default_goal: int
    default_max_turns: int

    def start(self, seed: int) -> Any:
        """初期状態を作る。同じ seed なら必ず同じ局になる。"""

    def candidates(self, state: Any, limit: int, rng: random.Random) -> list:
        """ラベル付きの着手候補。打つ手が無ければ空リスト（=局の終わり）。"""

    def apply(self, state: Any, candidate) -> Any:
        """候補手を適用した次の状態。"""

    def progress(self, state: Any) -> int:
        """ライン数やスコアなど、目標と突き合わせる値。"""

    def score(self, state: Any) -> int:
        """対局終了時に比較用として報告する得点。"""

    def rows(self, state: Any) -> list[str]:
        """UI に出す盤面。1 要素 1 行。"""

    def view(self, state: Any) -> dict[str, Any]:
        """モデルに渡す state。盤面・凡例・統計を JSON で。"""

    def hud(self, state: Any) -> dict[str, Any]:
        """UI に出す、そのゲーム固有の数字（レベル・タイマー・ノルマなど）。"""
