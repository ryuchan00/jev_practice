"""Claude API の応答形式が崩れても、モデルの選択を利用できることを見る。"""

from types import SimpleNamespace

import anthropic

from jevbench.agents.claude_agent import ClaudeAgent
from jevbench.core import BaseAgent, Candidate


def _candidates():
    return [
        Candidate(label="A", score=1.0, summary="one", detail={}, move=None),
        Candidate(label="B", score=3.0, summary="three", detail={}, move=None),
        Candidate(label="C", score=2.0, summary="two", detail={}, move=None),
    ]


def _agent():
    agent = ClaudeAgent.__new__(ClaudeAgent)
    BaseAgent.__init__(agent)
    agent.model = "test-model"
    agent.cache_write_tokens = 0
    agent.cache_read_tokens = 0
    agent.client = SimpleNamespace(messages=SimpleNamespace(create=None))
    return agent


def _response(text, input_tokens=0, output_tokens=0):
    return SimpleNamespace(
        content=[SimpleNamespace(type="text", text=text)],
        usage=SimpleNamespace(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cache_creation_input_tokens=0,
            cache_read_input_tokens=0,
        ),
    )


def test_schema_honouring_reply_is_parsed(monkeypatch):
    agent = _agent()
    monkeypatch.setattr(agent.client.messages, "create", lambda **kwargs: _response('{"move": "C"}'))

    decision = agent._decide({}, _candidates())

    assert decision.label == "C"
    assert not decision.fell_back


def test_prose_reply_with_standalone_label_is_parsed(monkeypatch):
    agent = _agent()
    monkeypatch.setattr(
        agent.client.messages,
        "create",
        lambda **kwargs: _response("After reviewing the board, I choose A."),
    )

    decision = agent._decide({}, _candidates())

    assert decision.label == "A"
    assert not decision.fell_back


def test_prose_reply_without_label_falls_back(monkeypatch):
    agent = _agent()
    monkeypatch.setattr(
        agent.client.messages,
        "create",
        lambda **kwargs: _response("I cannot select from the available options."),
    )

    decision = agent._decide({}, _candidates())

    assert decision.label == "B"
    assert decision.fell_back


def test_anthropic_error_falls_back(monkeypatch):
    agent = _agent()

    def fail(**kwargs):
        raise anthropic.AnthropicError("gateway failed")

    monkeypatch.setattr(agent.client.messages, "create", fail)

    decision = agent._decide({}, _candidates())

    assert decision.label == "B"
    assert decision.fell_back


def test_usage_tokens_are_accumulated_on_success(monkeypatch):
    agent = _agent()
    monkeypatch.setattr(
        agent.client.messages,
        "create",
        lambda **kwargs: _response("C", input_tokens=17, output_tokens=3),
    )

    decision = agent.choose({}, _candidates())

    assert decision.input_tokens == 17
    assert decision.output_tokens == 3
    assert agent.input_tokens == 17
    assert agent.output_tokens == 3
