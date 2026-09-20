"""人間 / 別プロセスの LLM に 1 手ずつ聞くエージェント。

API を叩かない。作業ディレクトリに「いま何を聞かれているか」を書き出し、
答えが書き戻されるまで待つ。Claude Code のようにファイル越しに操作できる
相手を、そのまま 1 人のプレイヤーとしてベンチに乗せるための口。

    turn.json   <- こちらが書く（盤面・候補手・選べるラベル）
    answer.txt  -> 相手が書く（ラベル 1 文字）

レイテンシは「相手が答えを書くまでの実時間」なので、API エージェントの
往復時間とは意味が違う。トークンもコストも 0 として記録される。
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

from ..core import BaseAgent, Candidate, Decision, fallback

DEFAULT_DIR = Path(os.environ.get("JEV_OPERATOR_DIR", ".operator"))
DEFAULT_TIMEOUT = float(os.environ.get("JEV_OPERATOR_TIMEOUT", "600"))
POLL_SECONDS = 0.25


class OperatorAgent(BaseAgent):
    name = "operator"

    def __init__(self, directory: Path | None = None, timeout: float = DEFAULT_TIMEOUT) -> None:
        super().__init__()
        self.dir = Path(directory or DEFAULT_DIR)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.timeout = timeout
        self.turn_path = self.dir / "turn.json"
        self.answer_path = self.dir / "answer.txt"
        self.log_path = self.dir / "log.jsonl"
        self._index = 0
        for stale in (self.turn_path, self.answer_path):
            stale.unlink(missing_ok=True)

    def _decide(self, state: dict[str, Any], candidates: list[Candidate]) -> Decision:
        labels = [c.label for c in candidates]
        self.answer_path.unlink(missing_ok=True)
        self.turn_path.write_text(
            json.dumps(
                {
                    "turn": self._index,
                    "state": state,
                    "choices": {c.label: c.summary for c in candidates},
                    "answer_with": f"{self.answer_path} に {'/'.join(labels)} のどれか 1 文字を書く",
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        deadline = time.monotonic() + self.timeout
        while time.monotonic() < deadline:
            if self.answer_path.exists():
                label = self.answer_path.read_text(encoding="utf-8").strip().upper()[:1]
                if label in labels:
                    self.turn_path.unlink(missing_ok=True)
                    self.answer_path.unlink(missing_ok=True)
                    self._index += 1
                    return Decision(label=label, latency_ms=0.0)
                # 読めない答えは捨ててもう一度待つ
                self.answer_path.unlink(missing_ok=True)
            time.sleep(POLL_SECONDS)

        self.turn_path.unlink(missing_ok=True)
        return fallback(candidates, f"operator timeout after {self.timeout:.0f}s")

    def close(self) -> None:
        self.turn_path.unlink(missing_ok=True)
        self.answer_path.unlink(missing_ok=True)
