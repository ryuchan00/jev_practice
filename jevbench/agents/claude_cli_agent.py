"""Claude CLI に盤面を渡し、候補から 1 手を選ばせるエージェント。"""

from __future__ import annotations

import json
import os
import re
import subprocess
from typing import Any

from ..core import BaseAgent, Candidate, Decision, fallback

DEFAULT_MODEL = os.environ.get("JEV_CLI_MODEL", "claude-haiku-4-5")


class ClaudeCliAgent(BaseAgent):
    name = "haiku-cli"

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        name: str = "haiku-cli",
        timeout: float = 120,
    ) -> None:
        super().__init__()
        self.model = model
        self.name = name
        self.timeout = timeout

    def _decide(self, state: dict[str, Any], candidates: list[Candidate]) -> Decision:
        choices = "\n".join(f"{candidate.label}: {candidate.summary}" for candidate in candidates)
        prompt = f"""You are picking one move in a Zoo Keeper style match-3 game.
The level clears only when the quota for EVERY species is met, so the best move is
usually NOT the one catching the most animals. Prefer species listed in
stats.still_needed, then cascades and longer lines, then more moves left after.

Board:
{json.dumps(state.get("board"), ensure_ascii=False)}

Stats:
{json.dumps(state.get("stats"), ensure_ascii=False)}

Candidates:
{choices}

Answer with exactly one character: the chosen label, nothing else."""

        try:
            result = subprocess.run(
                ["claude", "-p", "--model", self.model],
                input=prompt,
                capture_output=True,
                text=True,
                timeout=self.timeout,
            )
        except subprocess.TimeoutExpired:
            return fallback(candidates, f"claude CLI timeout after {self.timeout:g}s")
        except FileNotFoundError:
            return fallback(candidates, "claude CLI not found")
        except (subprocess.SubprocessError, OSError) as exc:
            # CLI 側の失敗でゲーム全体を止めないため、予期される実行例外も代打ちする。
            return fallback(candidates, f"claude CLI error: {exc}")

        if result.returncode != 0:
            return fallback(candidates, f"claude CLI exited with status {result.returncode}")

        labels = {candidate.label for candidate in candidates}
        label_pattern = "|".join(re.escape(label) for label in sorted(labels, key=len, reverse=True))
        # 単純な包含判定では、説明文の単語に含まれるラベルを回答と誤認するため。
        matches = re.findall(rf"(?<![A-Za-z])(?:{label_pattern})(?![A-Za-z])", result.stdout)
        if not matches:
            return fallback(candidates, "claude CLI returned no usable label")

        return Decision(label=matches[-1], latency_ms=0.0)
