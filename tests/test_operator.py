"""operator が無応答になったら局ごと止まることを見る。"""
import pytest
from jevbench.agents import operator_agent as oa
from jevbench.core import Candidate
from jevbench.match import MatchConfig, play


def _cands():
    return [Candidate(label="A", score=1.0, summary="s", detail={}, move=None)]


def test_first_timeout_falls_back(tmp_path, monkeypatch):
    monkeypatch.setattr(oa, "MAX_CONSECUTIVE_TIMEOUTS", 2)
    a = oa.OperatorAgent(directory=tmp_path, timeout=0.01, name="ghost")
    d = a._decide({}, _cands())
    assert d.fell_back and "timeout" in d.fallback_reason


def test_repeated_timeouts_abort_instead_of_quietly_substituting(tmp_path, monkeypatch):
    monkeypatch.setattr(oa, "MAX_CONSECUTIVE_TIMEOUTS", 2)
    a = oa.OperatorAgent(directory=tmp_path, timeout=0.01, name="ghost")
    a._decide({}, _cands())
    with pytest.raises(oa.OperatorGone):
        a._decide({}, _cands())


def test_a_dead_operator_does_not_produce_a_results_row(tmp_path, monkeypatch):
    monkeypatch.setattr(oa, "MAX_CONSECUTIVE_TIMEOUTS", 2)
    monkeypatch.setattr(oa, "DEFAULT_DIR", tmp_path)
    agent = oa.OperatorAgent(directory=tmp_path, timeout=0.01, name="ghost")
    with pytest.raises(oa.OperatorGone):
        for _ in play(agent, MatchConfig(game="zookeeper", seed=1, goal=2)):
            pass
