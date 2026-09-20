"""ゲームに依らないループの性質。"""

from __future__ import annotations

from jevbench.agents import HeuristicAgent
from jevbench.core import Decision, label_candidates
from jevbench.games import GAME_NAMES
from jevbench.match import MatchConfig, play

import random

import pytest


@pytest.mark.parametrize("game", GAME_NAMES)
def test_first_event_carries_the_initial_state(game):
    start = next(play(HeuristicAgent(), MatchConfig(game=game, seed=5)))
    assert start["type"] == "start"
    assert start["board"]
    assert "hud" in start


@pytest.mark.parametrize("game", GAME_NAMES)
def test_same_seed_gives_the_same_start_board(game):
    starts = [
        next(play(HeuristicAgent(), MatchConfig(game=game, seed=5))) for _ in range(2)
    ]
    assert starts[0]["board"] == starts[1]["board"]


@pytest.mark.parametrize("game", GAME_NAMES)
def test_start_event_does_not_count_as_a_turn(game):
    fixed_turns = 4
    events = list(
        play(HeuristicAgent(), MatchConfig(game=game, seed=5, turns=fixed_turns))
    )
    assert len([event for event in events if event["type"] == "turn"]) == fixed_turns
    assert events[-1]["type"] == "summary"
    assert events[-1]["turns"] == fixed_turns
    assert len([event for event in events if event["type"] == "summary"]) == 1


@pytest.mark.parametrize("game", GAME_NAMES)
def test_heuristic_reaches_the_default_goal(game):
    summary = list(play(HeuristicAgent(), MatchConfig(game=game, seed=3)))[-1]
    assert summary["type"] == "summary"
    assert summary["reached_goal"], summary
    assert summary["agreement"] == 1.0
    assert summary["mean_regret"] == 0.0
    assert summary["fallbacks"] == 0


@pytest.mark.parametrize("game", GAME_NAMES)
def test_same_seed_gives_the_same_game(game):
    runs = [
        [e.get("board") for e in play(HeuristicAgent(), MatchConfig(game=game, seed=5))]
        for _ in range(2)
    ]
    assert runs[0] == runs[1]


@pytest.mark.parametrize("game", GAME_NAMES)
def test_turn_events_carry_running_token_and_cost_totals(game):
    events = list(play(HeuristicAgent(), MatchConfig(game=game, seed=1)))
    turns = [e for e in events if e["type"] == "turn"]
    assert turns
    for e in turns:
        assert {"input_tokens", "output_tokens", "cost_usd"} <= e.keys()


@pytest.mark.parametrize("game", GAME_NAMES)
def test_fixed_length_runs_past_the_default_goal(game):
    baseline = list(play(HeuristicAgent(), MatchConfig(game=game, seed=3)))[-1]
    fixed_turns = 70
    assert baseline["turns"] < fixed_turns

    summary = list(
        play(HeuristicAgent(), MatchConfig(game=game, seed=3, turns=fixed_turns))
    )[-1]
    assert summary["turns"] == fixed_turns


def test_fixed_length_overrides_goal():
    fixed_turns = 5
    summary = list(
        play(
            HeuristicAgent(),
            MatchConfig(game="zookeeper", seed=3, goal=1, turns=fixed_turns),
        )
    )[-1]
    assert summary["turns"] == fixed_turns


def test_summary_carries_zookeeper_score():
    summary = list(
        play(HeuristicAgent(), MatchConfig(game="zookeeper", seed=3, turns=3))
    )[-1]
    assert summary["score"] > 0


def test_fixed_length_game_over_reports_stuck():
    summary = list(
        play(
            HeuristicAgent(),
            MatchConfig(game="zookeeper", seed=3, turns=5, candidate_limit=0),
        )
    )[-1]
    assert summary["turns"] < 5
    assert summary["stuck"]


def test_labels_are_shuffled_so_the_best_move_is_not_always_first():
    scored = [(float(i), f"move {i}", {"i": i}, i) for i in range(12)]
    firsts = {
        label_candidates(scored, 12, random.Random(seed))[0].score for seed in range(20)
    }
    assert len(firsts) > 1


def test_fallback_is_visible_in_the_summary():
    class Broken(HeuristicAgent):
        name = "broken"

        def _decide(self, state, candidates):
            best = max(candidates, key=lambda c: c.score)
            return Decision(label=best.label, latency_ms=0.0, note="fallback: boom")

    summary = list(play(Broken(), MatchConfig(game="zookeeper", seed=1, goal=2)))[-1]
    assert summary["fallbacks"] == summary["turns"] > 0
    assert summary["fallback_reason"] == "boom"
    # 全手フォールバックでも agreement は満点に見える。だから fallbacks を見る。
    assert summary["agreement"] == 1.0
