"""使えるゲームの一覧。名前で引いてインスタンスを返す。"""

from __future__ import annotations

from .base import Game
from .match3 import Match3
from .tetris import Tetris

GAMES = {g.name: g for g in (Tetris(), Match3())}
GAME_NAMES = tuple(GAMES)


def build(name: str) -> Game:
    try:
        return GAMES[name]
    except KeyError:
        raise ValueError(f"unknown game: {name} (expected one of {', '.join(GAME_NAMES)})") from None


__all__ = ["Game", "GAMES", "GAME_NAMES", "build", "Tetris", "Match3"]
