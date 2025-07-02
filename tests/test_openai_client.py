import sys
import os
import asyncio
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from translator import openai_client


def test_batch_translate_batches_and_caches(monkeypatch):
    calls = []

    def fake_create(*args, **kwargs):
        prompt = kwargs['messages'][-1]['content']
        lines = [l for l in prompt.splitlines() if l.strip() and l.strip()[0].isdigit()]
        pieces = [l.split('.', 1)[1].strip() if '.' in l else l for l in lines]

        class M:
            pass

        resp = M()
        resp.choices = [M()]
        resp.choices[0].message = M()
        resp.choices[0].message.content = "\n".join(
            f"{i+1}. {p}_t" for i, p in enumerate(pieces)
        )
        calls.append(prompt)
        return resp

    monkeypatch.setattr(openai_client.client.chat.completions, 'create', fake_create)

    texts = ['Hello', 'Hello', 'World']
    result = openai_client.batch_translate(texts, ['cs'], 'en')
    assert result['cs'] == ['Hello_t', 'Hello_t', 'World_t']
    # both unique segments should be sent in one request
    assert len(calls) == 1
    assert '1. Hello' in calls[0]
    assert '2. World' in calls[0]


def test_async_batch_translate(monkeypatch):
    calls = []

    async def fake_create(*args, **kwargs):
        prompt = kwargs['messages'][-1]['content']
        lines = [l for l in prompt.splitlines() if l.strip() and l.strip()[0].isdigit()]
        pieces = [l.split('.', 1)[1].strip() if '.' in l else l for l in lines]

        class M:
            pass

        resp = M()
        resp.choices = [M()]
        resp.choices[0].message = M()
        resp.choices[0].message.content = "\n".join(
            f"{i+1}. {p}_t" for i, p in enumerate(pieces)
        )
        calls.append(prompt)
        return resp

    monkeypatch.setattr(openai_client.async_client.chat.completions, 'create', fake_create)

    texts = ['Hi', 'Bye']
    result = asyncio.run(openai_client.async_batch_translate(texts, ['cs', 'de'], 'en', delay=None))
    assert result['cs'] == ['Hi_t', 'Bye_t']
    assert result['de'] == ['Hi_t', 'Bye_t']
    assert len(calls) == 2
