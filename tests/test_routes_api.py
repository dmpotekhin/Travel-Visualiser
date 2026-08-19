"""Tests for the provider-agnostic routes API (POST /api/routes, GET /api/providers)."""
import pytest
from fastapi.testclient import TestClient

from backend import config
from backend.app import app


@pytest.fixture
def client(tmp_db):
    with TestClient(app) as c:
        yield c


def test_routes_api_returns_geojson_with_provider(monkeypatch, client):
    monkeypatch.setattr(config, "HERE_API_KEY", "")
    r = client.post(
        "/api/routes",
        json={
            "segments": [
                {
                    "from": {"lat": 55.7558, "lon": 37.6173, "name": "Москва"},
                    "to": {"lat": 59.9343, "lon": 30.3351, "name": "Санкт-Петербург"},
                    "transport": "CAR",
                },
                {
                    "from": {"lat": 59.9343, "lon": 30.3351},
                    "to": {"lat": 39.9042, "lon": 116.4074},
                    "transport": "PLANE",
                },
            ]
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert len(data["segments"]) == 2
    assert data["segments"][0]["provider"] == "GREAT_CIRCLE"
    assert data["segments"][0]["from"] == "Москва"
    assert data["total_distance_km"] > 0
    # GeoJSON carries the provider property (additive, frontend stays agnostic)
    props = data["geojson"]["features"][0]["properties"]
    assert props["provider"] == "GREAT_CIRCLE"
    assert props["transport"] == "car"


def test_routes_api_accepts_internal_keys(monkeypatch, client):
    monkeypatch.setattr(config, "HERE_API_KEY", "")
    r = client.post(
        "/api/routes",
        json={
            "segments": [
                {
                    "from": {"lat": 55.7558, "lon": 37.6173},
                    "to": {"lat": 59.9343, "lon": 30.3351},
                    "transport": "train",
                }
            ]
        },
    )
    assert r.status_code == 200
    assert r.json()["segments"][0]["transport"] == "rail"


def test_routes_api_defaults_transport_to_car(monkeypatch, client):
    monkeypatch.setattr(config, "HERE_API_KEY", "")
    r = client.post(
        "/api/routes",
        json={
            "segments": [
                {
                    "from": {"lat": 55.7558, "lon": 37.6173},
                    "to": {"lat": 59.9343, "lon": 30.3351},
                }
            ]
        },
    )
    assert r.status_code == 200
    assert r.json()["segments"][0]["transport"] == "car"


def test_routes_api_invalid_transport_422(client):
    r = client.post(
        "/api/routes",
        json={
            "segments": [
                {
                    "from": {"lat": 55.7558, "lon": 37.6173},
                    "to": {"lat": 59.9343, "lon": 30.3351},
                    "transport": "teleport",
                }
            ]
        },
    )
    assert r.status_code == 422


def test_routes_api_requires_segments(client):
    r = client.post("/api/routes", json={"segments": []})
    assert r.status_code == 422


def test_providers_endpoint(monkeypatch, client):
    monkeypatch.setattr(config, "HERE_API_KEY", "")
    monkeypatch.setattr(config, "OSRM_BASE_URL", "")
    monkeypatch.setattr(config, "GRAPHHOPPER_API_KEY", "")
    r = client.get("/api/providers")
    assert r.status_code == 200
    data = r.json()
    assert data["fallback_enabled"] is True
    assert data["order"] == "auto"
    names = [p["name"] for p in data["providers"]]
    assert names == ["HERE", "OSRM", "GRAPHHOPPER", "GREAT_CIRCLE"]


def test_providers_endpoint_reports_config(monkeypatch, client):
    monkeypatch.setattr(config, "HERE_API_KEY", "test")
    monkeypatch.setattr(config, "OSRM_BASE_URL", "")
    monkeypatch.setattr(config, "GRAPHHOPPER_API_KEY", "")
    r = client.get("/api/providers")
    data = r.json()
    by_name = {p["name"]: p for p in data["providers"]}
    assert by_name["HERE"]["configured"] is True
    assert by_name["HERE"]["in_chain"] is True
    assert by_name["OSRM"]["configured"] is False
    assert "car" in by_name["HERE"]["transports"]
    assert by_name["GREAT_CIRCLE"]["transports"] == sorted(
        ["car", "bus", "bike", "foot", "ferry", "rail", "air"]
    )
