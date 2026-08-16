import pytest
from fastapi.testclient import TestClient

from backend.app import app


@pytest.fixture
def client(tmp_db):
    with TestClient(app) as c:
        yield c


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_animate_form(client):
    r = client.post("/animate", data={"route": "Санкт-Петербург – Москва – Пекин", "year": "2023"})
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]


def test_animate_json(client):
    r = client.post("/animate", json={"route": "Москва – Пекин"})
    assert r.status_code == 200


def test_history_and_stats(client):
    client.post("/animate", data={"route": "Москва – Пекин"})
    h = client.get("/history").json()
    assert len(h) == 1
    assert h[0]["total_distance_km"] > 5000
    stats = client.get("/stats").json()
    assert stats["routes_count"] == 1
    assert stats["total_km"] > 5000


def test_map_and_geojson(client):
    client.post("/animate", data={"route": "Москва – Пекин"})
    rid = client.get("/history").json()[0]["id"]
    assert client.get(f"/map/{rid}").status_code == 200
    g = client.get(f"/api/geojson/{rid}").json()
    assert "features" in g["geojson"]
    assert g["segments"][0]["from"] == "Москва"


def test_upload(client):
    csv = (
        "№;Маршрут (кратко);Общее расстояние, км;Примечания;Год\n"
        "1;Москва – Пекин;5800;перелёт;2023\n"
        "2;Париж – Лондон;340;;2022\n"
    ).encode("utf-8")
    r = client.post("/upload", files={"file": ("routes.csv", csv, "text/csv")})
    assert r.status_code == 200
    data = r.json()
    assert data["processed"] == 2
    assert data["stats"]["routes_count"] == 2
    assert len(data["maps"]) == 2


def test_animate_empty_route(client):
    r = client.post("/animate", data={"route": ""})
    assert r.status_code == 400
