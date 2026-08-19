"""Natural-language route parsing (DeepSeek when a key is set, else heuristic).

The goal: turn prose like "Хочу поехать из СПб в Москву, потом в Пекин на поезде"
into the canonical route string understood by ``transport.parse_route``:

    Санкт-Петербург – Москва [поезд] – Пекин [самолёт]

DeepSeek is used only when ``DEEPSEEK_API_KEY`` is present; otherwise a
deterministic heuristic normalizer runs (coarser, but never needs a network or a
key). The heuristic is intentionally simple — it exists so the feature degrades
gracefully rather than erroring.
"""
from __future__ import annotations

import re

import httpx

from . import config, transport as transport_mod

_SYSTEM_PROMPT = (
    "Ты — парсер текстовых описаний путешествий. Извлеки из текста города в "
    "порядке следования и вид транспорта между ними (если указан). Верни ТОЛЬКО "
    "одну строку в формате: Город [транспорт] – Город [транспорт] – Город. "
    "Транспорт пиши одним из слов: самолёт, поезд, авто, автобус, паром, "
    "велосипед, пешком. Если транспорт не указан — не добавляй скобки. Не "
    "добавляй пояснений, комментариев или markdown — только строку маршрута."
)

# "из X в Y" and "от X до Y" -> "X – Y" (X/Y: words, spaces, hyphens)
_FROM_TO_RE = re.compile(
    r"(?:из|от|с)\s+([А-ЯЁа-яёA-Za-z][А-ЯЁа-яёA-Za-z\- ]*?)\s+(?:в|до|на)\s+([А-ЯЁа-яёA-Za-z][А-ЯЁа-яёA-Za-z\- ]+)",
    flags=re.IGNORECASE,
)
# conjunctions that imply "next stop"
_CONJ_RE = re.compile(
    r"\s*(?:потом\s+в|затем\s+в|далее\s+в|а\s+потом|а\s+затем|потом|затем|далее|после\s+этого)\s*",
    flags=re.IGNORECASE,
)
# leading filler: "хочу посетить", "поехать", "съездить", "маршрут:", "путешествие"
_FILLER_RE = re.compile(
    r"^(?:я\s+хочу|хочу|планирую|собираюсь|поеду|еду|поехать|съездить|посетить|маршрут|путь|путешествие)\s*[:\-—]?\s*",
    flags=re.IGNORECASE,
)


def _heuristic_parse(text: str) -> str:
    t = text.strip()
    t = _FILLER_RE.sub("", t)
    # "из СПб в Москву" -> "СПб – Москву"
    t = _FROM_TO_RE.sub(r"\1 – \2", t)
    # "– в Пекин" -> "– Пекин"  (dangling "в" after a separator)
    t = re.sub(r"(\s*–\s*)(?:в|до|на)\s+", r"\1", t, flags=re.IGNORECASE)
    # conjunctions -> separator
    t = _CONJ_RE.sub(" – ", t)
    # commas / semicolons / arrows -> separator
    t = re.sub(r"\s*(?:,|;|→|->|=>)\s*", " – ", t)
    # collapse repeated separators and stray leading/trailing separators
    t = re.sub(r"\s*–\s*(?:–\s*)+", " – ", t)
    t = t.strip(" –")
    return t


def _deepseek_parse(text: str) -> str:
    r = httpx.post(
        config.DEEPSEEK_URL,
        json={
            "model": config.DEEPSEEK_MODEL,
            "messages": [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": text},
            ],
            "temperature": 0,
            "stream": False,
            "max_tokens": config.LLM_MAX_TOKENS,
            **config.LLM_EXTRA_JSON,
        },
        headers={"Authorization": f"Bearer {config.DEEPSEEK_API_KEY}"},
        timeout=30.0,
    )
    r.raise_for_status()
    content = r.json()["choices"][0]["message"]["content"].strip()
    content = content.strip("`").strip()
    # validate it actually parses as a route
    segs = transport_mod.parse_route(content)
    if len(segs) < 1:
        return ""
    return content


def parse_natural_language(text: str) -> str:
    """Return a canonical route string for a natural-language description."""
    if not text.strip():
        raise ValueError("Пустое описание маршрута.")

    if config.DEEPSEEK_API_KEY:
        try:
            route = _deepseek_parse(text)
            if route:
                return route
        except Exception:
            pass  # fall back to heuristic

    route = _heuristic_parse(text)
    # ensure it yields at least two cities, else raise a clear error
    try:
        segs = transport_mod.parse_route(route)
    except ValueError:
        raise ValueError(
            "Не удалось распознать города в описании. Укажите маршрут явно, "
            "например: «Санкт-Петербург – Москва – Пекин»."
        )
    if len(segs) < 1:
        raise ValueError("Не удалось распознать маршрут в описании.")
    return route
