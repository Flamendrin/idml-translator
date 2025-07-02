import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from translator import openai_client


def test_batch_translate_uses_cache(monkeypatch):
    calls = []

    def fake_create(*args, **kwargs):
        class M:
            pass
        resp = M()
        resp.choices = [M()]
        resp.choices[0].message = M()
        resp.choices[0].message.content = kwargs['messages'][-1]['content'] + '_t'
        calls.append(kwargs['messages'][-1]['content'])
        return resp

    monkeypatch.setattr(openai_client.client.chat.completions, 'create', fake_create)

    texts = ['Hello', 'Hello', 'World']
    result = openai_client.batch_translate(texts, ['cs'], 'en')
    assert result['cs'] == ['Hello_t', 'Hello_t', 'World_t']
    # two unique texts -> two API calls
    assert calls == ['Hello', 'World']
