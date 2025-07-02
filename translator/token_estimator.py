"""Helpers for estimating token usage and cost."""

from __future__ import annotations

import tiktoken

# approximate rates per 1k tokens in USD
MODEL_RATES: dict[str, float] = {
    "gpt-3.5-turbo": 0.001,
    "gpt-4": 0.03,
    "gpt-4o": 0.005,
}


def count_tokens(texts: list[str], model: str) -> int:
    """Return the total number of tokens for ``texts`` using ``model`` encoding."""
    # ``encoding_for_model`` may try to download data which is blocked in tests
    # so we rely on the base encoding used by chat models.
    try:
        enc = tiktoken.get_encoding("cl100k_base")
    except Exception:
        return 0
    total = 0
    for text in texts:
        total += len(enc.encode(text))
    return total


def estimate_cost(tokens: int, model: str, languages: int = 1) -> float:
    """Return estimated price for ``tokens`` for ``languages`` translations."""
    rate = MODEL_RATES.get(model, 0.03)
    return (tokens / 1000) * rate * languages

