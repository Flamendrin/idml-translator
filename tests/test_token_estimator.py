import tiktoken
import pytest
from translator.token_estimator import count_tokens, estimate_cost, MODEL_RATES


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

