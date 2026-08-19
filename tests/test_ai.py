import pytest

from backend import ai, config


@pytest.fixture(autouse=True)
def no_deepseek(monkeypatch):
    monkeypatch.setattr(config, "DEEPSEEK_API_KEY", "")
    monkeypatch.setattr(config, "DEEPSEEK_MODEL", "deepseek-chat")


def test_heuristic_from_to():
    assert ai._heuristic_parse("из СПб в Москву") == "СПб – Москву"


def test_heuristic_conjunctions():
    out = ai._heuristic_parse("Париж, потом Рим, затем Барселона")
    assert "–" in out
    assert "потом" not in out and "затем" not in out


def test_heuristic_filler_stripped():
    out = ai._heuristic_parse("Хочу посетить Париж, потом Рим")
    assert not out.lower().startswith("хочу")


def test_parse_natural_language_no_key():
    route = ai.parse_natural_language("Париж, потом Рим, затем Барселона")
    # yields at least two cities separated by dashes
    assert "–" in route


def test_parse_natural_language_uses_deepseek(monkeypatch):
    monkeypatch.setattr(config, "DEEPSEEK_API_KEY", "fake-key")
    monkeypatch.setattr(
        ai, "_deepseek_parse", lambda text: "Париж [поезд] – Рим – Барселона [самолёт]"
    )
    route = ai.parse_natural_language("хочу в Париж, Рим и Барселону")
    assert route == "Париж [поезд] – Рим – Барселона [самолёт]"


def test_parse_natural_language_empty():
    with pytest.raises(ValueError):
        ai.parse_natural_language("")
