"""Claude CLI の出力が揺れたり起動に失敗しても、局を継続できることを見る。"""

import subprocess
from types import SimpleNamespace

from jevbench.agents import claude_cli_agent as cca
from jevbench.core import Candidate


def _cands():
    return [
        Candidate(label="A", score=1.0, summary="one", detail={}, move=None),
        Candidate(label="B", score=3.0, summary="three", detail={}, move=None),
    ]


def _full_cands():
    return [
        Candidate(label=label, score=float(index), summary=label, detail={}, move=None)
        for index, label in enumerate("ABCDEFGHIJKL")
    ]


def _result(stdout="", returncode=0):
    return SimpleNamespace(stdout=stdout, stderr="", returncode=returncode)


def _assert_fallback(decision):
    assert decision.label == "B"
    assert decision.note.startswith("fallback: ")


def test_standalone_label_is_parsed(monkeypatch):
    monkeypatch.setattr(cca.subprocess, "run", lambda *args, **kwargs: _result("I pick G"))
    decision = cca.ClaudeCliAgent()._decide({"board": [], "stats": {}}, _full_cands())
    assert decision.label == "G"
    assert not decision.fell_back


def test_output_without_standalone_label_falls_back(monkeypatch):
    monkeypatch.setattr(cca.subprocess, "run", lambda *args, **kwargs: _result("none of these"))
    decision = cca.ClaudeCliAgent()._decide({}, _full_cands())
    assert decision.label == "L"
    assert decision.note.startswith("fallback: ")


def test_garbage_answer_falls_back(monkeypatch):
    monkeypatch.setattr(cca.subprocess, "run", lambda *args, **kwargs: _result("???"))
    _assert_fallback(cca.ClaudeCliAgent()._decide({}, _cands()))


def test_nonzero_exit_falls_back(monkeypatch):
    monkeypatch.setattr(cca.subprocess, "run", lambda *args, **kwargs: _result(returncode=1))
    _assert_fallback(cca.ClaudeCliAgent()._decide({}, _cands()))


def test_timeout_falls_back(monkeypatch):
    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd="claude", timeout=120)

    monkeypatch.setattr(cca.subprocess, "run", timeout)
    _assert_fallback(cca.ClaudeCliAgent()._decide({}, _cands()))


def test_missing_cli_falls_back(monkeypatch):
    def missing(*args, **kwargs):
        raise FileNotFoundError

    monkeypatch.setattr(cca.subprocess, "run", missing)
    _assert_fallback(cca.ClaudeCliAgent()._decide({}, _cands()))
