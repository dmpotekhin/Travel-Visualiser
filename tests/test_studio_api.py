import pytest
from fastapi.testclient import TestClient

from backend.app import app
from backend import config


@pytest.fixture
def client(tmp_db):
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def no_deepseek(monkeypatch):
    monkeypatch.setattr(config, "DEEPSEEK_API_KEY", "")


def test_parse_text(client):
    r = client.post("/api/parse", json={"kind": "text", "input": "Санкт-Петербург – Москва – Пекин"})
    assert r.status_code == 200
    data = r.json()
    assert len(data["segments"]) == 2
    assert len(data["points"]) == 3
    assert data["geojson"]["type"] == "FeatureCollection"


def test_parse_nl(client):
    r = client.post("/api/parse", json={"kind": "nl", "input": "Париж, потом Рим, затем Барселона"})
    assert r.status_code == 200
    assert len(r.json()["segments"]) == 2


def test_parse_gmaps(client):
    url = "https://www.google.com/maps/dir/59.9311,30.3609/55.7558,37.6173/39.9042,116.4074"
    r = client.post("/api/parse", json={"kind": "gmaps", "input": url})
    assert r.status_code == 200
    assert len(r.json()["segments"]) == 2


def test_parse_empty(client):
    assert client.post("/api/parse", json={"kind": "text", "input": ""}).status_code == 400


def test_parse_unknown_city(client, monkeypatch):
    from backend import geocoding
    monkeypatch.setattr(
        geocoding,
        "geocode_city",
        lambda name: (_ for _ in ()).throw(ValueError(f"Не удалось геокодировать город: {name!r}")),
    )
    r = client.post("/api/parse", json={"kind": "text", "input": "НесуществующийГород123 – Москва"})
    assert r.status_code == 422


GPX = b"""<?xml version="1.0"?>
<gpx xmlns="http://www.topografix.com/GPX/1/1"><trk><trkseg>
<trkpt lat="59.9311" lon="30.3609"/><trkpt lat="55.7558" lon="37.6173"/><trkpt lat="39.9042" lon="116.4074"/>
</trkseg></trk></gpx>
"""

GEOJSON = b'{"type":"LineString","coordinates":[[30.3609,59.9311],[37.6173,55.7558],[116.4074,39.9042]]}'


def test_parse_file_gpx(client):
    r = client.post("/api/parse-file", files={"file": ("route.gpx", GPX, "application/gpx+xml")})
    assert r.status_code == 200
    data = r.json()
    assert len(data["segments"]) == 2
    # СПб→Москва ~634 км → rail; Москва→Пекин ~5800 км → air
    assert data["segments"][0]["transport"] == "rail"
    assert data["segments"][1]["transport"] == "air"


def test_parse_file_geojson(client):
    r = client.post("/api/parse-file", files={"file": ("route.geojson", GEOJSON, "application/geo+json")})
    assert r.status_code == 200
    assert len(r.json()["points"]) == 3


def test_parse_file_unsupported(client):
    r = client.post("/api/parse-file", files={"file": ("x.csv", b"a,b", "text/csv")})
    assert r.status_code == 422


def test_geocode(client):
    r = client.post("/api/geocode", json={"name": "Москва"})
    assert r.status_code == 200
    assert r.json()["coord"] == [37.6173, 55.7558]


def test_geocode_unknown(client, monkeypatch):
    from backend import geocoding
    monkeypatch.setattr(geocoding, "geocode_city", lambda name: (_ for _ in ()).throw(ValueError("x")))
    assert client.post("/api/geocode", json={"name": "zzz"}).status_code == 422


def test_config(client):
    r = client.get("/api/config")
    assert r.status_code == 200
    assert "cesium_ion_token" in r.json()
