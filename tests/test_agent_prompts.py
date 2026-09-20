"""ゲーム固有の方針がエージェント側へ紛れ込まないことを見る。"""

from pathlib import Path


def test_agent_modules_do_not_contain_game_specific_strategy():
    agents = Path(__file__).parents[1] / "jevbench" / "agents"
    forbidden = ("holes", "stack", "cascade", "quota", "line")
    for name in ("jev_agent.py", "claude_agent.py"):
        source = (agents / name).read_text(encoding="utf-8").lower()
        assert not any(word in source for word in forbidden), name
