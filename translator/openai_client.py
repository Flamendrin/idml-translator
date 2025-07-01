"""Thin wrapper around the OpenAI client used for translating text."""

from __future__ import annotations

import os
import time
from openai import OpenAI
from openai.types.chat import ChatCompletionMessageParam

DEFAULT_PROMPT = (
    "You are a professional translator. "
    "Translate the following XML-safe text from {from_lang} to {to_lang}. "
    "Do not change XML tags."
)

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

LANGUAGE_MAP = {
    'cs': 'Czech',
    'sk': 'Slovak',
    'pl': 'Polish',
    'en': 'English',
    'de': 'German',
    'hu': 'Hungarian',
}

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
) -> dict[str, list[str]]:
    """Translate a list of texts into multiple languages sequentially."""
    results = {lang: [] for lang in target_langs}
    for text in texts:
        for lang in target_langs:
            print(f"Překládám z {source_lang} do {lang}: {text[:40]}...")
            translation = translate_text(text, source_lang, lang, system_prompt)
            results[lang].append(translation)
            time.sleep(1)
    return results

