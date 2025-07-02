"""Helpers for estimating token usage and cost."""

from __future__ import annotations

import tiktoken

# approximate rates per 1k tokens in USD
MODEL_RATES: dict[str, float] = {
    "gpt-3.5-turbo": 0.001,
    "gpt-4": 0.03,
    "gpt-4o": 0.005,
}

# Same default system prompt used in the translator client. Duplicated here to
# avoid cross-module imports.
DEFAULT_SYSTEM_PROMPT = (
    "You are a professional translator. "
    "Translate the following XML-safe text from {from_lang} to {to_lang}. "
    "Do not change XML tags. "
    "Preserve all whitespace including spaces and line breaks."
)


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


def estimate_total_tokens(
    texts: list[str],
    model: str,
    languages: int = 1,
    system_prompt: str = DEFAULT_SYSTEM_PROMPT,
) -> int:
    """Return a rough estimate of total tokens for translating ``texts``.

    The estimate includes both request and response tokens and scales with the
    number of target languages.  It still remains an approximation but should be
    closer to the actual usage reported by the OpenAI API.
    """
    unique = list(dict.fromkeys(texts))

    # Tokens for the user's request
    tokens = count_tokens(unique, model)
    tokens += count_tokens([system_prompt], model)
    tokens += count_tokens(
        [
            "Translate the following segments labelled [[SEG1]]..[[SEGN]]. "
            "Provide the translations on separate lines using the same labels:"
        ],
        model,
    )
    markers = [f"[[SEG{i+1}]]" for i in range(len(unique))]
    tokens += count_tokens(markers, model)

    # Rough protocol overhead for a single chat completion
    overhead = 3 if model.startswith("gpt-4") else 4
    tokens += overhead * 2  # user + assistant

    # Assume replies are roughly the same length as the source
    response_tokens = count_tokens(unique, model)

    total = (tokens + response_tokens + overhead) * max(1, languages)
    return total

