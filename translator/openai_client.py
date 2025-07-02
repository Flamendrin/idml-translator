"""Thin wrapper around the OpenAI client used for translating text."""

from __future__ import annotations

import os
import time
import asyncio
from openai import OpenAI, AsyncOpenAI
from openai.types.chat import ChatCompletionMessageParam
from translator.token_estimator import count_tokens

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
async_client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))


class ChatTranslator:
    """Maintain conversation context and cache for consistent translations."""

    def __init__(
        self,
        source_lang: str,
        target_lang: str,
        system_prompt: str | None = None,
        model: str = "gpt-4",
    ) -> None:
        from_lang = LANGUAGE_MAP.get(source_lang, source_lang)
        to_lang = LANGUAGE_MAP.get(target_lang, target_lang)
        prompt = (system_prompt or DEFAULT_PROMPT).format(from_lang=from_lang, to_lang=to_lang)
        self.messages: list[ChatCompletionMessageParam] = [
            {"role": "system", "content": prompt}
        ]
        self.cache: dict[str, str] = {}
        self.model = model

    def translate(self, text: str) -> str:
        if text in self.cache:
            return self.cache[text]
        self.messages.append({"role": "user", "content": text})
        try:
            response = client.chat.completions.create(
                model=self.model,
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
    model: str = "gpt-4",
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
            model=model,
            messages=messages,
            temperature=0.3,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"❌ Chyba při překladu: {e}")
        return text

def _split_batches(texts: list[str], max_tokens: int, model: str) -> list[list[str]]:
    """Split ``texts`` into batches not exceeding ``max_tokens`` tokens."""
    batches: list[list[str]] = []
    current: list[str] = []
    tokens = 0
    for text in texts:
        count = count_tokens([text], model)
        if current and tokens + count > max_tokens:
            batches.append(current)
            current = []
            tokens = 0
        current.append(text)
        tokens += count
    if current:
        batches.append(current)
    return batches


def _parse_segments(translated: str) -> list[str]:
    """Parse ``translated`` text labelled with ``[[SEG#]]`` markers."""
    import re

    pattern = re.compile(r"\[\[SEG(\d+)\]\]")
    parts = pattern.split(translated)
    results: list[str] = []
    i = 1
    while i < len(parts):
        _num = parts[i]
        text = parts[i + 1].strip()
        results.append(text)
        i += 2
    return results


def batch_translate(
    texts: list[str],
    target_langs: list[str],
    source_lang: str,
    system_prompt: str | None = None,
    progress_callback: callable | None = None,
    *,
    max_tokens: int = 800,
    delay: float | None = 1.0,
    model: str = "gpt-4",
) -> dict[str, list[str]]:
    """Translate ``texts`` into ``target_langs`` using OpenAI in batches."""

    results = {lang: [] for lang in target_langs}
    translators = {
        lang: ChatTranslator(source_lang, lang, system_prompt, model) for lang in target_langs
    }

    counts: dict[str, int] = {}
    for t in texts:
        counts[t] = counts.get(t, 0) + 1

    total = max(1, len(texts) * len(target_langs))
    done = 0

    unique_texts = list(dict.fromkeys(texts))

    for lang, translator in translators.items():
        to_translate = [t for t in unique_texts if t not in translator.cache]
        for batch in _split_batches(to_translate, max_tokens, model):
            marked = "\n".join(f"[[SEG{i+1}]] {t}" for i, t in enumerate(batch))
            prompt = (
                f"Translate the following segments labelled [[SEG1]]..[[SEG{len(batch)}]]. "
                "Provide the translations on separate lines using the same labels:\n" + marked
            )
            translator.messages.append({"role": "user", "content": prompt})
            try:
                response = client.chat.completions.create(
                    model=model,
                    messages=translator.messages,
                    temperature=0.3,
                )
                reply = response.choices[0].message.content.strip()
                translator.messages.append({"role": "assistant", "content": reply})
            except Exception as e:  # pragma: no cover - network errors
                print(f"❌ Chyba při překladu: {e}")
                reply = "\n".join(batch)

            translations = _parse_segments(reply)
            for original, translated in zip(batch, translations):
                translator.cache[original] = translated
                done += counts.get(original, 1)
                if progress_callback:
                    progress_callback(int(done / total * 100))
            if delay:
                time.sleep(delay)

    for text in texts:
        for lang, translator in translators.items():
            results[lang].append(translator.cache.get(text, text))
    return results


async def async_batch_translate(
    texts: list[str],
    target_langs: list[str],
    source_lang: str,
    system_prompt: str | None = None,
    progress_callback: callable | None = None,
    *,
    max_tokens: int = 800,
    delay: float | None = None,
    model: str = "gpt-4",
) -> dict[str, list[str]]:
    """Asynchronously translate ``texts`` into ``target_langs`` using OpenAI."""

    results = {lang: [] for lang in target_langs}
    translators = {
        lang: ChatTranslator(source_lang, lang, system_prompt, model) for lang in target_langs
    }

    counts: dict[str, int] = {}
    for t in texts:
        counts[t] = counts.get(t, 0) + 1

    total = max(1, len(texts) * len(target_langs))
    done = 0

    unique_texts = list(dict.fromkeys(texts))
    tasks = []

    async def translate_batch(lang: str, translator: ChatTranslator, batch: list[str]) -> None:
        nonlocal done
        marked = "\n".join(f"[[SEG{i+1}]] {t}" for i, t in enumerate(batch))
        prompt = (
            f"Translate the following segments labelled [[SEG1]]..[[SEG{len(batch)}]]. "
            "Provide the translations on separate lines using the same labels:\n" + marked
        )
        translator.messages.append({"role": "user", "content": prompt})
        try:
            response = await async_client.chat.completions.create(
                model=model,
                messages=translator.messages,
                temperature=0.3,
            )
            reply = response.choices[0].message.content.strip()
            translator.messages.append({"role": "assistant", "content": reply})
        except Exception as e:  # pragma: no cover - network errors
            print(f"❌ Chyba při překladu: {e}")
            reply = "\n".join(batch)

        translations = _parse_segments(reply)
        for original, translated in zip(batch, translations):
            translator.cache[original] = translated
            done += counts.get(original, 1)
            if progress_callback:
                progress_callback(int(done / total * 100))
        if delay:
            await asyncio.sleep(delay)

    for lang, translator in translators.items():
        to_translate = [t for t in unique_texts if t not in translator.cache]
        for batch in _split_batches(to_translate, max_tokens, model):
            tasks.append(translate_batch(lang, translator, batch))

    if tasks:
        await asyncio.gather(*tasks)

    for text in texts:
        for lang, translator in translators.items():
            results[lang].append(translator.cache.get(text, text))
    return results

