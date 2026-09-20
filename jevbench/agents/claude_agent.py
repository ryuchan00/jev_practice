"""比較対象の LLM エージェント。Claude Haiku 4.5 に構造化出力で 1 手を選ばせる。

System One との差を見るのが目的なので、
- 盤面とルール説明は system に置いて prompt caching を効かせる
- 出力は json_schema で候補ラベルの enum に固定する（パースの揺れを消す）
"""

from __future__ import annotations

import json
import os

from typing import Any

from ..core import BaseAgent, Candidate, Decision, fallback

# ゲートウェイ経由の場合はモデル ID の綴りが変わることがあるので環境変数で差し替える。
# base_url は SDK が ANTHROPIC_BASE_URL を読む。
MODEL = os.environ.get("JEV_LLM_MODEL", "claude-haiku-4-5")

# Claude Haiku 4.5 の料金（USD / 1M tokens）。
INPUT_PRICE = 1.00
OUTPUT_PRICE = 5.00
CACHE_WRITE_MULTIPLIER = 1.25
CACHE_READ_MULTIPLIER = 0.10

SYSTEM_PROMPT = """You are a game engine picking one move per turn.

You are given the current board, its stats, and a list of candidate moves.
Each candidate has a label and the effect of playing it. Pick the single
best label.

Prefer moves that score the most now without leaving the board in a worse
shape for later turns.

Answer only through the required JSON schema. Do not explain."""


class ClaudeAgent(BaseAgent):
    name = "claude"

    def __init__(self, model: str = MODEL) -> None:
        super().__init__()
        import anthropic  # 遅延 import

        self.model = model
        self.client = anthropic.Anthropic()
        if not (self.client.api_key or self.client.auth_token or self.client.credentials):
            raise RuntimeError(
                "Anthropic の認証情報が無い（ANTHROPIC_API_KEY を設定するか `ant auth login`）"
            )
        self.input_price_per_mtok = INPUT_PRICE
        self.output_price_per_mtok = OUTPUT_PRICE
        self.cache_write_tokens = 0
        self.cache_read_tokens = 0

    def _decide(self, state: dict[str, Any], candidates: list[Candidate]) -> Decision:
        import anthropic

        labels = [c.label for c in candidates]
        user_content = json.dumps(
            {**state, "candidates": {c.label: c.detail for c in candidates}},
            ensure_ascii=False,
        )

        try:
            res = self.client.messages.create(
                model=self.model,
                max_tokens=256,
                system=[
                    {
                        "type": "text",
                        "text": SYSTEM_PROMPT,
                        "cache_control": {"type": "ephemeral"},
                    }
                ],
                messages=[{"role": "user", "content": user_content}],
                output_config={
                    "format": {
                        "type": "json_schema",
                        "schema": {
                            "type": "object",
                            "properties": {"move": {"type": "string", "enum": labels}},
                            "required": ["move"],
                            "additionalProperties": False,
                        },
                    }
                },
            )
        except anthropic.AnthropicError as exc:
            return fallback(candidates, f"{type(exc).__name__}: {exc}")

        usage = res.usage
        self.cache_write_tokens += getattr(usage, "cache_creation_input_tokens", 0) or 0
        self.cache_read_tokens += getattr(usage, "cache_read_input_tokens", 0) or 0

        try:
            text = next(b.text for b in res.content if b.type == "text")
            label = json.loads(text)["move"]
        except (StopIteration, ValueError, KeyError) as exc:
            return fallback(candidates, f"unparsable response: {exc}")

        if label not in labels:
            return fallback(candidates, f"unknown label {label!r}")

        return Decision(
            label=label,
            latency_ms=0.0,
            input_tokens=usage.input_tokens or 0,
            output_tokens=usage.output_tokens or 0,
        )

    @property
    def cost_usd(self) -> float:
        """キャッシュ読み書きの割引・割増を反映した概算コスト。"""
        return (
            self.input_tokens / 1_000_000 * INPUT_PRICE
            + self.output_tokens / 1_000_000 * OUTPUT_PRICE
            + self.cache_write_tokens / 1_000_000 * INPUT_PRICE * CACHE_WRITE_MULTIPLIER
            + self.cache_read_tokens / 1_000_000 * INPUT_PRICE * CACHE_READ_MULTIPLIER
        )
