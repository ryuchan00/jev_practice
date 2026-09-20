"""使えるゲームの一覧。名前で引いてインスタンスを返す。"""

from __future__ import annotations

from .base import Game
from .tetris import Tetris
from .zookeeper import ZooKeeper

GAMES = {g.name: g for g in (ZooKeeper(), Tetris())}
GAME_NAMES = tuple(GAMES)


def build(name: str) -> Game:
    try:
        return GAMES[name]
    except KeyError:
        raise ValueError(
            f"unknown game: {name} (expected one of {', '.join(GAME_NAMES)})"
        ) from None


__all__ = ["Game", "GAMES", "GAME_NAMES", "build", "Tetris", "ZooKeeper"]
