import os
import time
from openai import OpenAI
from openai.types.chat import ChatCompletionMessageParam

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

LANGUAGE_MAP = {
    'cs': 'Czech',
    'sk': 'Slovak',
    'pl': 'Polish',
    'en': 'English',
    'de': 'German',
    'hu': 'Hungarian',
}

def translate_text(text, source_lang, target_lang):
    from_lang = LANGUAGE_MAP.get(source_lang, source_lang)
    to_lang = LANGUAGE_MAP.get(target_lang, target_lang)
    messages: list[ChatCompletionMessageParam] = [
        {"role": "system", "content": f"You are a professional translator. Translate the following XML-safe text from {from_lang} to {to_lang}. Do not change XML tags."},
        {"role": "user", "content": text}
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

def batch_translate(texts, target_langs, source_lang):
    results = {lang: [] for lang in target_langs}
    for text in texts:
        for lang in target_langs:
            print(f"Překládám z {source_lang} do {lang}: {text[:40]}...")
            translation = translate_text(text, source_lang, lang)
            results[lang].append(translation)
            time.sleep(1)
    return results
