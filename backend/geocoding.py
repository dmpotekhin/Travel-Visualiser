"""Geocoding: HERE Geocoding API (if key) else Nominatim, with a built-in cache.

The cache makes the demo route (and many common cities) work instantly and
offline, and avoids hammering the free Nominatim service.
"""
from __future__ import annotations

import time
from typing import Optional, Tuple

import httpx

from . import config

# (lat, lon) for common cities. Keys are lowercased names (Cyrillic + Latin).
CITY_CACHE: dict[str, Tuple[float, float]] = {
    "санкт-петербург": (59.9311, 30.3609), "saint petersburg": (59.9311, 30.3609),
    "питер": (59.9311, 30.3609), "спб": (59.9311, 30.3609),
    "москва": (55.7558, 37.6173), "moscow": (55.7558, 37.6173),
    "пекин": (39.9042, 116.4074), "beijing": (39.9042, 116.4074),
    "париж": (48.8566, 2.3522), "paris": (48.8566, 2.3522),
    "лондон": (51.5074, -0.1278), "london": (51.5074, -0.1278),
    "берлин": (52.5200, 13.4050), "berlin": (52.5200, 13.4050),
    "рим": (41.9028, 12.4964), "rome": (41.9028, 12.4964),
    "нью-йорк": (40.7128, -74.0060), "new york": (40.7128, -74.0060),
    "токио": (35.6762, 139.6503), "tokyo": (35.6762, 139.6503),
    "владивосток": (43.1332, 131.9113), "vladivostok": (43.1332, 131.9113),
    "новосибирск": (55.0084, 82.9357), "novosibirsk": (55.0084, 82.9357),
    "екатеринбург": (56.8389, 60.6057), "yekaterinburg": (56.8389, 60.6057),
    "казань": (55.7963, 49.1088), "kazan": (55.7963, 49.1088),
    "нижний новгород": (56.2965, 43.9361), "nizhny novgorod": (56.2965, 43.9361),
    "сочи": (43.5855, 39.7231), "sochi": (43.5855, 39.7231),
    "минск": (53.9006, 27.5590), "minsk": (53.9006, 27.5590),
    "киев": (50.4501, 30.5234), "kyiv": (50.4501, 30.5234), "kiev": (50.4501, 30.5234),
    "астана": (51.1694, 71.4491), "astana": (51.1694, 71.4491),
    "стамбул": (41.0082, 28.9784), "istanbul": (41.0082, 28.9784),
    "дубай": (25.2048, 55.2708), "dubai": (25.2048, 55.2708),
    "мадрид": (40.4168, -3.7038), "madrid": (40.4168, -3.7038),
    "барселона": (41.3874, 2.1686), "barcelona": (41.3874, 2.1686),
    "амстердам": (52.3676, 4.9041), "amsterdam": (52.3676, 4.9041),
    "прага": (50.0755, 14.4378), "prague": (50.0755, 14.4378),
    "вена": (48.2082, 16.3738), "vienna": (48.2082, 16.3738),
    "лиссабон": (38.7223, -9.1393), "lisbon": (38.7223, -9.1393),
    "варшава": (52.2297, 21.0122), "warsaw": (52.2297, 21.0122),
    "хельсинки": (60.1699, 24.9384), "helsinki": (60.1699, 24.9384),
    "осло": (59.9139, 10.7522), "oslo": (59.9139, 10.7522),
    "стокгольм": (59.3293, 18.0686), "stockholm": (59.3293, 18.0686),
    "копенгаген": (55.6761, 12.5683), "copenhagen": (55.6761, 12.5683),
    "лос-анджелес": (34.0522, -118.2437), "los angeles": (34.0522, -118.2437),
    "сан-франциско": (37.7749, -122.4194), "san francisco": (37.7749, -122.4194),
    "сингапур": (1.3521, 103.8198), "singapore": (1.3521, 103.8198),
    "сеул": (37.5665, 126.9780), "seoul": (37.5665, 126.9780),
    "шанхай": (31.2304, 121.4737), "shanghai": (31.2304, 121.4737),
    "гонконг": (22.3193, 114.1694), "hong kong": (22.3193, 114.1694),
    "дели": (28.7041, 77.1025), "delhi": (28.7041, 77.1025),
    "мумбаи": (19.0760, 72.8777), "mumbai": (19.0760, 72.8777),
    "каир": (30.0444, 31.2357), "cairo": (30.0444, 31.2357),
    "кейптаун": (-33.9249, 18.4241), "cape town": (-33.9249, 18.4241),
    "сидней": (-33.8688, 151.2093), "sydney": (-33.8688, 151.2093),
    "мельбурн": (-37.8136, 144.9631), "melbourne": (-37.8136, 144.9631),
    "рио-де-жанейро": (-22.9068, -43.1729), "rio de janeiro": (-22.9068, -43.1729),
    "буэнос-айрес": (-34.6037, -58.3816), "buenos aires": (-34.6037, -58.3816),
    "мехико": (19.4326, -99.1332), "mexico city": (19.4326, -99.1332),
    "торонто": (43.6532, -79.3832), "toronto": (43.6532, -79.3832),
    "ванкувер": (49.2827, -123.1207), "vancouver": (49.2827, -123.1207),
    "рейкьявик": (64.1466, -21.9426), "reykjavik": (64.1466, -21.9426),
    "бангкок": (13.7563, 100.5018), "bangkok": (13.7563, 100.5018),
    "ханой": (21.0278, 105.8342), "hanoi": (21.0278, 105.8342),
    "тбилиси": (41.7151, 44.8271), "tbilisi": (41.7151, 44.8271),
    "ереван": (40.1792, 44.4991), "yerevan": (40.1792, 44.4991),
    "баку": (40.4093, 49.8671), "baku": (40.4093, 49.8671),
    "алматы": (43.2220, 76.8512), "almaty": (43.2220, 76.8512),
    "ташкент": (41.2995, 69.2401), "tashkent": (41.2995, 69.2401),
    "цаган": (47.7419, 46.8719),
}

# keep track of last Nominatim call for the 1 req/sec courtesy limit
_last_nominatim = 0.0


def _here_geocode(name: str) -> Optional[Tuple[float, float]]:
    r = httpx.get(
        config.HERE_GEOCODE_URL,
        params={"q": name, "apiKey": config.HERE_API_KEY, "limit": 1},
        timeout=10.0,
    )
    r.raise_for_status()
    items = r.json().get("items", [])
    if not items:
        return None
    pos = items[0].get("position", {})
    return (pos.get("lat"), pos.get("lng"))


def _nominatim_geocode(name: str) -> Optional[Tuple[float, float]]:
    global _last_nominatim
    elapsed = time.time() - _last_nominatim
    if elapsed < 1.0:
        time.sleep(1.0 - elapsed)
    r = httpx.get(
        config.NOMINATIM_URL,
        params={"q": name, "format": "json", "limit": 1},
        headers={"User-Agent": config.NOMINATIM_USER_AGENT},
        timeout=10.0,
    )
    _last_nominatim = time.time()
    r.raise_for_status()
    items = r.json()
    if not items:
        return None
    return (float(items[0]["lat"]), float(items[0]["lon"]))


def geocode_city(name: str) -> Tuple[float, float]:
    """Resolve a city name to (lat, lon). Cache -> HERE -> Nominatim."""
    key = name.strip().lower()
    if key in CITY_CACHE:
        return CITY_CACHE[key]

    if config.HERE_API_KEY:
        try:
            if (res := _here_geocode(name)) is not None:
                CITY_CACHE[key] = res
                return res
        except Exception:
            pass  # fall through to Nominatim

    try:
        if (res := _nominatim_geocode(name)) is not None:
            CITY_CACHE[key] = res
            return res
    except Exception:
        pass

    raise ValueError(f"Не удалось геокодировать город: {name!r}")
