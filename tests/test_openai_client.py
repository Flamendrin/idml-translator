import sys
import os
import asyncio
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from translator import openai_client  # noqa: E402


def test_batch_translate_batches_and_caches(monkeypatch):
    calls = []

    models = []

    def fake_create(*args, **kwargs):
        prompt = kwargs['messages'][-1]['content']
        lines = [line for line in prompt.splitlines() if line.strip().startswith('[[SEG')]
        pieces = [line.split(']]', 1)[1].strip() for line in lines]

        class M:
            pass

        resp = M()
        resp.choices = [M()]
        resp.choices[0].message = M()
        resp.choices[0].message.content = "\n".join(
            f"[[SEG{i+1}]] {p}_t" for i, p in enumerate(pieces)
        )
        calls.append(prompt)
        models.append(kwargs.get('model'))
        return resp

    monkeypatch.setattr(openai_client.client.chat.completions, 'create', fake_create)

    texts = ['Hello', 'Hello', 'World']
    result = openai_client.batch_translate(texts, ['cs'], 'en', model='gpt-3.5-turbo')
    assert result['cs'] == ['Hello_t', 'Hello_t', 'World_t']
    # both unique segments should be sent in one request
    assert len(calls) == 1
    assert '[[SEG1]] Hello' in calls[0]
    assert '[[SEG2]] World' in calls[0]
    assert models == ['gpt-3.5-turbo']


def test_async_batch_translate(monkeypatch):
    calls = []

    models = []

    async def fake_create(*args, **kwargs):
        prompt = kwargs['messages'][-1]['content']
        lines = [line for line in prompt.splitlines() if line.strip().startswith('[[SEG')]
        pieces = [line.split(']]', 1)[1].strip() for line in lines]

        class M:
            pass

        resp = M()
        resp.choices = [M()]
        resp.choices[0].message = M()
        resp.choices[0].message.content = "\n".join(
            f"[[SEG{i+1}]] {p}_t" for i, p in enumerate(pieces)
        )
        calls.append(prompt)
        models.append(kwargs.get('model'))
        return resp

    monkeypatch.setattr(openai_client.async_client.chat.completions, 'create', fake_create)

    texts = ['Hi', 'Bye']
    result = asyncio.run(openai_client.async_batch_translate(texts, ['cs', 'de'], 'en', delay=None, model='gpt-3.5-turbo'))
    assert result['cs'] == ['Hi_t', 'Bye_t']
    assert result['de'] == ['Hi_t', 'Bye_t']
    assert len(calls) == 2
    assert models == ['gpt-3.5-turbo', 'gpt-3.5-turbo']


def test_split_batches_respects_tokens(monkeypatch):
    monkeypatch.setattr(openai_client, 'count_tokens', lambda texts, model: len(texts[0]))

    texts = ['aaaaa', 'bb', 'ccc']
    batches = openai_client._split_batches(texts, 5, 'gpt-3.5-turbo')
    assert batches == [['aaaaa'], ['bb', 'ccc']]


def test_parse_segments_preserves_spaces():
    translated = "[[SEG1]]  Hello \n[[SEG2]]  World  "
    result = openai_client._parse_segments(translated)
    assert result == [' Hello ', ' World  ']


def test_get_remaining_credit(monkeypatch):
    class DummyResp:
        def raise_for_status(self):
            pass

        def json(self):
            return {"total_available": 1.23}

    class DummyClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            pass

        def get(self, url, headers=None):
            assert url == "https://api.openai.com/dashboard/billing/credit_grants"
            assert headers["Authorization"] == "Bearer test"
            return DummyResp()

    monkeypatch.setattr(openai_client.httpx, "Client", DummyClient)
    os.environ["OPENAI_API_KEY"] = "test"
    assert openai_client.get_remaining_credit() == 1.23
