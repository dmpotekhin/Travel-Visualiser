import pytest

from backend import transport as t


def test_detect_transport():
    assert t.detect_transport("на самолёте") == "air"
    assert t.detect_transport("поездом") == "rail"
    assert t.detect_transport("авто") == "car"
    assert t.detect_transport("пешком") == "foot"
    assert t.detect_transport("на корабле") == "ferry"
    assert t.detect_transport("Париж") is None


def test_parse_simple_default_car():
    segs = t.parse_route("Санкт-Петербург – Москва – Пекин")
    assert len(segs) == 2
    assert segs[0] == {"from": "Санкт-Петербург", "to": "Москва", "transport": "car"}
    assert segs[1] == {"from": "Москва", "to": "Пекин", "transport": "car"}


def test_parse_inline_hint():
    segs = t.parse_route("Москва [поезд] – Пекин [самолёт]")
    assert segs[0]["transport"] == "rail"
    assert segs[0]["from"] == "Москва"
    assert segs[0]["to"] == "Пекин"


def test_parse_global_phrase():
    segs = t.parse_route("Париж – Берлин на поезде")
    assert segs[0]["transport"] == "rail"
    assert segs[0]["to"] == "Берлин"  # phrase stripped from city name


def test_parse_separators():
    for s in ["Москва - Пекин", "Москва — Пекин", "Москва → Пекин", "Москва->Пекин"]:
        segs = t.parse_route(s)
        assert len(segs) == 1, s
        assert segs[0]["from"] == "Москва", s


def test_parse_too_few_cities():
    with pytest.raises(ValueError):
        t.parse_route("Москва")


def test_transport_metadata():
    assert t.speed_kmh("air") == 850
    assert t.speed_kmh("rail") == 80
    assert t.speed_kmh("car") == 90
    assert t.color("air") == "#3182ce"
