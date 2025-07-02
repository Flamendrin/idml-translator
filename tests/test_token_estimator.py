from translator.token_estimator import count_tokens, estimate_cost, MODEL_RATES


def test_estimate_cost_matches_manual():
    texts = ["Hello world", "Bye"]
    model = "gpt-3.5-turbo"
    tokens = count_tokens(texts, model)
    cost = estimate_cost(tokens, model, 2)
    assert cost == tokens / 1000 * MODEL_RATES[model] * 2

