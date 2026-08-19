"""Transport types: metadata, keyword detection, and route-string parsing."""
from __future__ import annotations

import re
from enum import Enum
from typing import Optional

# key -> (name_ru, name_en, avg_speed_kmh, color_hex)
TRANSPORTS: dict[str, dict] = {
    "air":   {"name": "Самолёт",  "en": "air",   "speed_kmh": 850, "color": "#3182ce"},
    "rail":  {"name": "Поезд",    "en": "rail",  "speed_kmh": 80,  "color": "#2f855a"},
    "car":   {"name": "Авто",     "en": "car",   "speed_kmh": 90,  "color": "#c53030"},
    "bus":   {"name": "Автобус",  "en": "bus",   "speed_kmh": 70,  "color": "#b7791f"},
    "ferry": {"name": "Паром",    "en": "ferry", "speed_kmh": 35,  "color": "#2c7a7b"},
    "bike":  {"name": "Велосипед","en": "bike",  "speed_kmh": 18,  "color": "#d69e2e"},
    "foot":  {"name": "Пешком",   "en": "foot",  "speed_kmh": 5,   "color": "#805ad5"},
}

DEFAULT_TRANSPORT = "car"


class TransportType(str, Enum):
    """Canonical transport types.

    Values ARE the internal lowercase keys used in storage and GeoJSON,
    so existing data stays compatible. New code should reference the enum
    members; legacy code can keep using the raw keys.
    """

    CAR = "car"
    TRAIN = "rail"
    PLANE = "air"
    WALK = "foot"
    BICYCLE = "bike"
    BUS = "bus"
    FERRY = "ferry"


# uppercase / English aliases accepted by coerce_transport()
_TRANSPORT_ALIASES: dict[str, str] = {
    "CAR": "car", "AUTO": "car", "DRIVING": "car", "DRIVE": "car", "TAXI": "car",
    "TRAIN": "rail", "RAIL": "rail", "RAILWAY": "rail",
    "PLANE": "air", "AIR": "air", "FLIGHT": "air", "FLY": "air",
    "WALK": "foot", "WALKING": "foot", "FOOT": "foot", "PEDESTRIAN": "foot",
    "BICYCLE": "bike", "BIKE": "bike", "CYCLING": "bike",
    "BUS": "bus", "COACH": "bus",
    "FERRY": "ferry", "SHIP": "ferry", "BOAT": "ferry",
}


def coerce_transport(value) -> str:
    """Normalize any user-supplied transport value to a canonical key.

    Accepts TransportType members, existing internal keys (car, rail, ...)
    and uppercase/English aliases (CAR, TRAIN, PLANE, WALK, BICYCLE, ...).

    Raises ValueError for unknown or empty values.
    """
    if isinstance(value, TransportType):
        return value.value
    if value is None:
        raise ValueError("Тип транспорта не указан")
    s = str(value).strip()
    if not s:
        raise ValueError("Тип транспорта не указан")
    low = s.lower()
    if low in TRANSPORTS:
        return low
    key = _TRANSPORT_ALIASES.get(s.upper())
    if key:
        return key
    raise ValueError(f"Неизвестный тип транспорта: {value}")

# transport key -> emoji marker icon (used by the frontend map marker)
EMOJI: dict[str, str] = {
    "air": "✈️",
    "rail": "🚂",
    "car": "🚗",
    "bus": "🚌",
    "ferry": "⛴️",
    "bike": "🚲",
    "foot": "🚶",
}

# keyword -> transport key (lowercased). Order matters: more specific first.
_KEYWORDS: list[tuple[str, str]] = [
    ("авиа", "air"), ("самолёт", "air"), ("самолет", "air"), ("перелёт", "air"),
    ("перелет", "air"), ("flight", "air"), ("plane", "air"), ("air", "air"),
    ("fly", "air"),
    ("железн", "rail"), ("поезд", "rail"), ("ж/д", "rail"), ("ж.д", "rail"),
    ("rail", "rail"), ("train", "rail"), ("жд", "rail"),
    ("паром", "ferry"), ("корабл", "ferry"), ("круиз", "ferry"), ("ferry", "ferry"),
    ("ship", "ferry"), ("boat", "ferry"), ("мор", "ferry"),
    ("автобус", "bus"), ("bus", "bus"), ("coach", "bus"),
    ("велосипед", "bike"), ("вело", "bike"), ("bike", "bike"), ("bicycle", "bike"),
    ("самокат", "bike"),
    ("пешком", "foot"), ("пеш", "foot"), ("треккинг", "foot"), ("поход", "foot"),
    ("walk", "foot"),
    ("авто", "car"), ("автомобил", "car"), ("машин", "car"), ("такси", "car"),
    ("car", "car"), ("drive", "car"), ("taxi", "car"),
]

# characters that split city tokens.
# Long dashes and arrows are unambiguous separators; a bare hyphen-minus "-"
# is treated as a separator only when surrounded by spaces, so that
# hyphenated city names (Санкт-Петербург, Нью-Йорк, Буэнос-Айрес) stay intact.
_SPLIT_RE = re.compile(r"\s*(?:—|–|−|->|→|=>|>|»)\s*|\s+-\s+")
# inline transport annotation: "Город (поезд)" or "Город [самолёт]"
_HINT_RE = re.compile(r"[\[(]([^)\]]+)[\])]\s*$")

# global transport phrases that should not become part of a city name
_GLOBAL_PHRASES = [
    r"\s+на\s+поезде", r"\s+поездом", r"\s+на\s+самолёте", r"\s+на\s+самолете",
    r"\s+самолётом", r"\s+самолетом", r"\s+перелётом", r"\s+перелетом",
    r"\s+на\s+авто", r"\s+на\s+машине", r"\s+автомобилем", r"\s+на\s+автобусе",
    r"\s+автобусом", r"\s+пешком", r"\s+на\s+велосипеде", r"\s+велосипедом",
    r"\s+на\s+пароме", r"\s+паромом", r"\s+по\s+морю", r"\s+морским\s+путём",
    r"\s+морским\s+путем", r"\s+на\s+корабле", r"\s+кораблём", r"\s+кораблем",
]


def detect_transport(text: str) -> Optional[str]:
    """Return transport key if any keyword matches, else None."""
    low = text.lower()
    for kw, key in _KEYWORDS:
        if kw in low:
            return key
    return None


def _clean_city(token: str) -> tuple[str, Optional[str]]:
    token = token.strip()
    hint: Optional[str] = None
    m = _HINT_RE.search(token)
    if m:
        detected = detect_transport(m.group(1))
        if detected:
            hint = detected
            token = token[: m.start()].strip()
    return token, hint


def parse_route(route_text: str) -> list[dict]:
    """Split a route string into segments.

    Examples:
      "Санкт-Петербург – Москва – Пекин"
      "Санкт-Петербург [самолёт] – Москва [поезд] – Пекин"
      "Париж – Берлин – Прага на поезде"

    Returns list of {"from", "to", "transport"}.
    """
    original = route_text.strip()

    # strip trailing global transport phrases so they don't pollute a city name
    cleaned = original
    for pat in _GLOBAL_PHRASES:
        cleaned = re.sub(pat, "", cleaned)

    tokens = [t for t in _SPLIT_RE.split(cleaned) if t.strip()]
    if len(tokens) < 2:
        raise ValueError("Маршрут должен содержать минимум два города.")

    cities = [_clean_city(t) for t in tokens]

    # global transport hint: use only if NO inline annotations were given
    global_hint: Optional[str] = None
    if not any(h for _, h in cities):
        global_hint = detect_transport(original)

    segments = []
    for i in range(len(cities) - 1):
        fr_name, fr_hint = cities[i]
        to_name, to_hint = cities[i + 1]
        transport = fr_hint or to_hint or global_hint or DEFAULT_TRANSPORT
        segments.append(
            {"from": fr_name, "to": to_name, "transport": transport}
        )
    return segments


def speed_kmh(transport: str) -> float:
    return TRANSPORTS.get(transport, TRANSPORTS[DEFAULT_TRANSPORT])["speed_kmh"]


def color(transport: str) -> str:
    return TRANSPORTS.get(transport, TRANSPORTS[DEFAULT_TRANSPORT])["color"]


def name(transport: str) -> str:
    return TRANSPORTS.get(transport, TRANSPORTS[DEFAULT_TRANSPORT])["name"]


def emoji(transport: str) -> str:
    return EMOJI.get(transport, EMOJI[DEFAULT_TRANSPORT])
