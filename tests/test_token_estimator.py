import tiktoken
from translator.token_estimator import (
    count_tokens,
    estimate_cost,
    MODEL_RATES,
    estimate_total_tokens,
    DEFAULT_SYSTEM_PROMPT,
)


class DummyEncoder:
    def encode(self, text: str):
        return text.split()


def test_estimate_cost_matches_manual(monkeypatch):
    monkeypatch.setattr(tiktoken, "get_encoding", lambda name: DummyEncoder())
    texts = ["Hello world", "Bye"]
    model = "gpt-3.5-turbo"
    tokens = count_tokens(texts, model)
    cost = estimate_cost(tokens, model, 2)
    assert cost == tokens / 1000 * MODEL_RATES[model] * 2


def test_count_tokens_uses_encoder(monkeypatch):
    monkeypatch.setattr(tiktoken, "get_encoding", lambda name: DummyEncoder())
    assert count_tokens(["a b", "c"], "gpt-4") == 3


def test_count_tokens_returns_zero_on_error(monkeypatch):
    def boom(name):
        raise RuntimeError("nope")
    monkeypatch.setattr(tiktoken, "get_encoding", boom)
    assert count_tokens(["hi"], "gpt-4") == 0


def test_estimate_cost_default_rate():
    cost = estimate_cost(1000, "unknown", 3)
    assert cost == (1000 / 1000) * 0.03 * 3


def test_estimate_total_tokens_adds_overhead(monkeypatch):
    captured = []

    def fake_count(texts, model):
        captured.append(list(texts))
        return len(texts)

    monkeypatch.setattr(tiktoken, "get_encoding", lambda name: DummyEncoder())
    monkeypatch.setattr(
        'translator.token_estimator.count_tokens',
        fake_count,
    )

    tokens = estimate_total_tokens(["a", "b"], "gpt-4")
    # count_tokens should be called four times: unique texts, system prompt,
    # instruction text and markers
    assert captured[0] == ['a', 'b']
    assert captured[1] == [DEFAULT_SYSTEM_PROMPT]
    assert captured[2] == [
        'Translate the following segments labelled [[SEG1]]..[[SEGN]]. Provide the translations on separate lines using the same labels:'
    ]
    assert captured[3] == ['[[SEG1]]', '[[SEG2]]']
    assert tokens > sum(len(c) for c in captured)
