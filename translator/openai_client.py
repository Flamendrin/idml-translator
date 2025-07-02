"""Thin wrapper around the OpenAI client used for translating text."""

from __future__ import annotations

import os
import time
from openai import OpenAI
from openai.types.chat import ChatCompletionMessageParam

try:
    import pycountry  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    pycountry = None

DEFAULT_PROMPT = (
    "You are a professional translator. "
    "Translate the following XML-safe text from {from_lang} to {to_lang}. "
    "Do not change XML tags."
)

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


class ChatTranslator:
    """Maintain conversation context and cache for consistent translations."""

    def __init__(self, source_lang: str, target_lang: str, system_prompt: str | None = None) -> None:
        from_lang = LANGUAGE_MAP.get(source_lang, source_lang)
        to_lang = LANGUAGE_MAP.get(target_lang, target_lang)
        prompt = (system_prompt or DEFAULT_PROMPT).format(from_lang=from_lang, to_lang=to_lang)
        self.messages: list[ChatCompletionMessageParam] = [
            {"role": "system", "content": prompt}
        ]
        self.cache: dict[str, str] = {}

    def translate(self, text: str) -> str:
        if text in self.cache:
            return self.cache[text]
        self.messages.append({"role": "user", "content": text})
        try:
            response = client.chat.completions.create(
                model="gpt-4",
                messages=self.messages,
                temperature=0.3,
            )
            translation = response.choices[0].message.content.strip()
            self.messages.append({"role": "assistant", "content": translation})
            self.cache[text] = translation
            return translation
        except Exception as e:  # pragma: no cover - network errors
            print(f"❌ Chyba při překladu: {e}")
            return text

LANGUAGE_MAP: dict[str, str] = {}
if pycountry:
    LANGUAGE_MAP.update(
        {
            lang.alpha_2: lang.name
            for lang in pycountry.languages
            if hasattr(lang, "alpha_2")
        }
    )

def translate_text(
    text: str,
    source_lang: str,
    target_lang: str,
    system_prompt: str | None = None,
) -> str:
    """Translate ``text`` from ``source_lang`` to ``target_lang`` using ChatGPT."""
    from_lang = LANGUAGE_MAP.get(source_lang, source_lang)
    to_lang = LANGUAGE_MAP.get(target_lang, target_lang)
    prompt = (system_prompt or DEFAULT_PROMPT).format(
        from_lang=from_lang, to_lang=to_lang
    )
    messages: list[ChatCompletionMessageParam] = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": text},
    ]
    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=messages,
            temperature=0.3,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"❌ Chyba při překladu: {e}")
        return text

def batch_translate(
    texts: list[str],
    target_langs: list[str],
    source_lang: str,
    system_prompt: str | None = None,
    progress_callback: callable | None = None,
) -> dict[str, list[str]]:
    """Translate a list of texts into multiple languages sequentially.

    ``progress_callback`` will be called with the percentage completed (0-100)
    after each translation step if provided.
    """
    results = {lang: [] for lang in target_langs}
    translators = {
        lang: ChatTranslator(source_lang, lang, system_prompt) for lang in target_langs
    }
    total = max(1, len(texts) * len(target_langs))
    done = 0
    for text in texts:
        for lang, translator in translators.items():
            print(f"Překládám z {source_lang} do {lang}: {text[:40]}...")
            translation = translator.translate(text)
            results[lang].append(translation)
            done += 1
            if progress_callback:
                progress_callback(int(done / total * 100))
            time.sleep(1)
    return results

