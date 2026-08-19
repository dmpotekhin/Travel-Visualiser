"""Routing service tests: transport coercion + great-circle fallback provider."""
from __future__ import annotations

import pytest

from backend import config, geo
from backend import transport as transport_mod
from backend.routing import route_segment
from backend.routing.base import (
    ProviderConfigurationError,
    ProviderNoRouteError,
    ProviderUnavailableError,
    RoutingProvider,
    UnsupportedTransportError,
)
from backend.routing.factory import build_provider_chain, get_provider_for
from backend.routing.fallback import GreatCircleRoutingProvider
from backend.routing.graphhopper import GraphHopperRoutingProvider
from backend.routing.here import HereRoutingProvider
from backend.routing.osrm import OsrmRoutingProvider
from backend.transport import TransportType, coerce_transport


# --- transport coercion ---------------------------------------------------

@pytest.mark.parametrize(
    "raw,expected",
    [
        ("CAR", "car"), ("car", "car"), ("AUTO", "car"), ("DRIVING", "car"),
        ("TRAIN", "rail"), ("train", "rail"), ("RAIL", "rail"),
        ("PLANE", "air"), ("plane", "air"), ("AIR", "air"), ("FLIGHT", "air"),
        ("WALK", "foot"), ("walk", "foot"), ("WALKING", "foot"), ("FOOT", "foot"),
        ("BICYCLE", "bike"), ("bicycle", "bike"), ("BIKE", "bike"), ("CYCLING", "bike"),
        ("BUS", "bus"), ("bus", "bus"),
        ("FERRY", "ferry"), ("ferry", "ferry"),
    ],
)
def test_coerce_transport(raw, expected):
    assert coerce_transport(raw) == expected


def test_coerce_transport_enum_member():
    assert coerce_transport(TransportType.CAR) == "car"
    assert coerce_transport(TransportType.TRAIN) == "rail"
    assert coerce_transport(TransportType.PLANE) == "air"


def test_coerce_transport_unknown_raises():
    with pytest.raises(ValueError):
        coerce_transport("teleport")
    with pytest.raises(ValueError):
        coerce_transport(None)
    with pytest.raises(ValueError):
        coerce_transport("")


def test_transport_type_members_match_internal_keys():
    # Enum values ARE the internal keys -> stored rows / GeoJSON stay compatible
    for t in TransportType:
        assert t.value in transport_mod.TRANSPORTS


# --- great-circle provider ------------------------------------------------

def test_great_circle_provider_route():
    from backend.routing.fallback import GreatCircleRoutingProvider

    p = GreatCircleRoutingProvider()
    moscow = (55.7558, 37.6173)
    spb = (59.9343, 30.3351)
    res = p.route(moscow, spb, "car")

    expected_km = geo.haversine_km(*moscow, *spb)
    assert res.distance_km == pytest.approx(expected_km, rel=1e-6)
    assert res.duration_min == pytest.approx(expected_km / 90.0 * 60.0, rel=1e-6)
    assert res.provider == "GREAT_CIRCLE"
    assert len(res.geometry) > 2
    # GeoJSON order: [lon, lat]
    assert res.geometry[0] == pytest.approx([moscow[1], moscow[0]])
    assert res.geometry[-1] == pytest.approx([spb[1], spb[0]])


def test_great_circle_supports_all_transports():
    from backend.routing.fallback import GreatCircleRoutingProvider

    p = GreatCircleRoutingProvider()
    for t in transport_mod.TRANSPORTS:
        assert p.supports(t)


def test_route_segment_without_provider_uses_great_circle(monkeypatch):
    # no HERE key -> deterministic great-circle result, provider annotated
    monkeypatch.setattr(config, "HERE_API_KEY", "")
    moscow = (55.7558, 37.6173)
    spb = (59.9343, 30.3351)
    seg = route_segment(moscow, spb, "car")

    assert seg["provider"] == "GREAT_CIRCLE"
    assert seg["transport"] == "car"
    assert seg["distance_km"] == pytest.approx(geo.haversine_km(*moscow, *spb), rel=1e-3)
    assert seg["duration_min"] >= 1.0
    assert len(seg["geometry"]) > 2


# --- HERE provider --------------------------------------------------------

# "BF45p0KkkzlH8GwHsT8nC" decodes to:
#   [[37.6173, 55.7558], [37.6185, 55.7569], [37.63, 55.76]]
# (generated with an independent encoder, see /tmp/enc_polyline.py)
HERE_POLYLINE = "BF45p0KkkzlH8GwHsT8nC"
MOSCOW = (55.7558, 37.6173)
SPB = (59.9343, 30.3351)


class _FakeResp:
    def __init__(self, payload, status=200):
        self._payload = payload
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self._payload


def test_here_provider_parses_route_response():
    calls = []

    def fake_get(url, params=None, timeout=None):
        calls.append(url)
        assert params["apiKey"] == "test-key"
        assert params["transportMode"] == "car"
        return _FakeResp(
            {
                "routes": [
                    {
                        "sections": [
                            {
                                "summary": {"length": 634000, "duration": 25200},
                                "polyline": HERE_POLYLINE,
                            }
                        ]
                    }
                ]
            }
        )

    provider = HereRoutingProvider("test-key", http_get=fake_get)
    res = provider.route(MOSCOW, SPB, "car")

    assert res.provider == "HERE"
    assert res.distance_km == pytest.approx(634.0)
    assert res.duration_min == pytest.approx(420.0)
    # decoded flexible polyline -> [lon, lat]
    assert res.geometry[0] == pytest.approx([37.6173, 55.7558])
    assert res.geometry[-1] == pytest.approx([37.63, 55.76])


def test_here_provider_matrix_fallback_on_route_failure():
    def fake_get(url, params=None, timeout=None):
        if "matrix" in url:
            return _FakeResp(
                {"matrix": [[{"summary": {"length": 700000, "duration": 30000}}]]}
            )
        raise RuntimeError("routing down")

    provider = HereRoutingProvider("test-key", http_get=fake_get)
    res = provider.route(MOSCOW, SPB, "car")

    assert res.provider == "HERE"
    assert res.distance_km == pytest.approx(700.0)
    assert res.duration_min == pytest.approx(500.0)
    assert res.provider_info["distance_source"] == "matrix"
    # geometry is the great-circle baseline
    assert res.geometry[0] == pytest.approx([37.6173, 55.7558])
    assert res.geometry[-1] == pytest.approx([30.3351, 59.9343])


def test_here_provider_raises_when_route_and_matrix_fail():
    def fake_get(url, params=None, timeout=None):
        raise RuntimeError("network down")

    provider = HereRoutingProvider("test-key", http_get=fake_get)
    with pytest.raises(ProviderUnavailableError):
        provider.route(MOSCOW, SPB, "car")


def test_here_provider_supports_surface_transport_only():
    provider = HereRoutingProvider("test-key")
    for t in ("car", "bus", "bike", "foot", "ferry"):
        assert provider.supports(t)
    assert not provider.supports("air")
    assert not provider.supports("rail")


# --- provider chain / factory ---------------------------------------------


def test_build_provider_chain_auto_with_here(monkeypatch):
    monkeypatch.setattr(config, "HERE_API_KEY", "test-key")
    monkeypatch.setattr(config, "OSRM_BASE_URL", "")
    monkeypatch.setattr(config, "GRAPHHOPPER_API_KEY", "")
    chain = build_provider_chain()
    assert [p.name for p in chain] == ["HERE", "GREAT_CIRCLE"]


def test_build_provider_chain_without_here(monkeypatch):
    monkeypatch.setattr(config, "HERE_API_KEY", "")
    monkeypatch.setattr(config, "OSRM_BASE_URL", "")
    monkeypatch.setattr(config, "GRAPHHOPPER_API_KEY", "")
    chain = build_provider_chain()
    assert [p.name for p in chain] == ["GREAT_CIRCLE"]


def test_build_provider_chain_invalid_order(monkeypatch):
    monkeypatch.setattr(config, "HERE_API_KEY", "test-key")
    monkeypatch.setattr(config, "ROUTING_PROVIDER_ORDER", "HERE,BOGUS")
    with pytest.raises(ProviderConfigurationError):
        build_provider_chain()


def test_get_provider_for_transport(monkeypatch):
    monkeypatch.setattr(config, "HERE_API_KEY", "test-key")
    monkeypatch.setattr(config, "OSRM_BASE_URL", "")
    monkeypatch.setattr(config, "GRAPHHOPPER_API_KEY", "")
    chain = build_provider_chain()
    assert get_provider_for("car", chain).name == "HERE"
    # air/rail are not supported by HERE -> great-circle
    assert get_provider_for("air", chain).name == "GREAT_CIRCLE"
    assert get_provider_for("rail", chain).name == "GREAT_CIRCLE"


def test_route_segment_uses_here_when_available():
    def fake_get(url, params=None, timeout=None):
        return _FakeResp(
            {
                "routes": [
                    {
                        "sections": [
                            {
                                "summary": {"length": 634000, "duration": 25200},
                                "polyline": HERE_POLYLINE,
                            }
                        ]
                    }
                ]
            }
        )

    chain = [
        HereRoutingProvider("test-key", http_get=fake_get),
        GreatCircleRoutingProvider(),
    ]
    seg = route_segment(MOSCOW, SPB, "car", chain=chain)
    assert seg["provider"] == "HERE"
    assert seg["distance_km"] == pytest.approx(634.0)


def test_route_segment_falls_back_through_chain():
    def fake_get(url, params=None, timeout=None):
        raise RuntimeError("down")

    chain = [
        HereRoutingProvider("test-key", http_get=fake_get),
        GreatCircleRoutingProvider(),
    ]
    seg = route_segment(MOSCOW, SPB, "car", chain=chain)
    assert seg["provider"] == "GREAT_CIRCLE"
    assert seg["provider_fallback"], "fallback reasons must be recorded"
    assert "HERE" in seg["provider_fallback"][0]


def test_route_segment_raises_when_all_providers_fail():
    def fake_get(url, params=None, timeout=None):
        raise RuntimeError("down")

    chain = [HereRoutingProvider("test-key", http_get=fake_get)]
    with pytest.raises(ProviderUnavailableError):
        route_segment(MOSCOW, SPB, "car", chain=chain)


# --- OSRM provider ---------------------------------------------------------

OSRM_POLYLINE = "wxhsIccrdF{EoFkR{fA"  # [[37.6173,55.7558],[37.6185,55.7569],[37.63,55.76]]


def test_osrm_provider_parses_route_response():
    def fake_get(url, params=None, timeout=None):
        assert "/driving/" in url
        assert params["geometries"] == "polyline"
        return _FakeResp(
            {
                "code": "Ok",
                "routes": [
                    {
                        "distance": 634000,
                        "duration": 25200,
                        "geometry": OSRM_POLYLINE,
                    }
                ],
            }
        )

    p = OsrmRoutingProvider("http://localhost:5000", http_get=fake_get)
    res = p.route(MOSCOW, SPB, "car")
    assert res.provider == "OSRM"
    assert res.distance_km == pytest.approx(634.0)
    assert res.duration_min == pytest.approx(420.0)
    assert res.geometry[0] == pytest.approx([37.6173, 55.7558])
    assert res.geometry[-1] == pytest.approx([37.63, 55.76])


def test_osrm_provider_profile_mapping():
    seen = []

    def fake_get(url, params=None, timeout=None):
        seen.append(url)
        return _FakeResp({"code": "Ok", "routes": [{"distance": 1000, "duration": 60, "geometry": ""}]})

    p = OsrmRoutingProvider("http://localhost:5000", http_get=fake_get)
    p.route(MOSCOW, SPB, "car")
    p.route(MOSCOW, SPB, "bike")
    p.route(MOSCOW, SPB, "foot")
    assert "/driving/" in seen[0]
    assert "/cycling/" in seen[1]
    assert "/walking/" in seen[2]


def test_osrm_provider_unsupported_transport_raises():
    p = OsrmRoutingProvider("http://localhost:5000", http_get=lambda *a, **k: _FakeResp({}))
    assert not p.supports("air")
    assert not p.supports("rail")
    with pytest.raises(UnsupportedTransportError):
        p.route(MOSCOW, SPB, "air")


def test_osrm_provider_no_route_raises():
    def fake_get(url, params=None, timeout=None):
        return _FakeResp({"code": "NoRoute", "message": "Impossible route"})

    p = OsrmRoutingProvider("http://localhost:5000", http_get=fake_get)
    with pytest.raises(ProviderNoRouteError):
        p.route(MOSCOW, SPB, "car")


def test_build_provider_chain_with_osrm(monkeypatch):
    monkeypatch.setattr(config, "HERE_API_KEY", "")
    monkeypatch.setattr(config, "OSRM_BASE_URL", "http://localhost:5000")
    monkeypatch.setattr(config, "GRAPHHOPPER_API_KEY", "")
    chain = build_provider_chain()
    assert [p.name for p in chain] == ["OSRM", "GREAT_CIRCLE"]


def test_route_segment_falls_here_to_osrm():
    def here_get(url, params=None, timeout=None):
        raise RuntimeError("down")

    def osrm_get(url, params=None, timeout=None):
        return _FakeResp({"code": "Ok", "routes": [{"distance": 634000, "duration": 25200, "geometry": ""}]})

    chain = [
        HereRoutingProvider("test-key", http_get=here_get),
        OsrmRoutingProvider("http://localhost:5000", http_get=osrm_get),
        GreatCircleRoutingProvider(),
    ]
    seg = route_segment(MOSCOW, SPB, "car", chain=chain)
    assert seg["provider"] == "OSRM"
    assert seg["distance_km"] == pytest.approx(634.0)
    assert "HERE" in seg["provider_fallback"][0]


# --- GraphHopper provider --------------------------------------------------

def test_graphhopper_provider_parses_route_response():
    def fake_get(url, params=None, timeout=None):
        assert "graphhopper.com" in url
        assert params["key"] == "gh-key"
        assert params["profile"] == "car"
        return _FakeResp(
            {
                "paths": [
                    {
                        "distance": 634000,
                        "time": 25_200_000,
                        "points": {
                            "type": "LineString",
                            "coordinates": [
                                [55.7558, 37.6173],
                                [55.7569, 37.6185],
                                [55.76, 37.63],
                            ],
                        },
                    }
                ]
            }
        )

    p = GraphHopperRoutingProvider("gh-key", http_get=fake_get)
    res = p.route(MOSCOW, SPB, "car")
    assert res.provider == "GRAPHHOPPER"
    assert res.distance_km == pytest.approx(634.0)
    assert res.duration_min == pytest.approx(420.0)
    # GeoJSON order: [lon, lat]
    assert res.geometry[0] == pytest.approx([37.6173, 55.7558])
    assert res.geometry[-1] == pytest.approx([37.63, 55.76])


def test_graphhopper_provider_profile_mapping():
    seen = []

    def fake_get(url, params=None, timeout=None):
        seen.append(params["profile"])
        return _FakeResp({"paths": [{"distance": 1000, "time": 60_000, "points": {"coordinates": []}}]})

    p = GraphHopperRoutingProvider("gh-key", http_get=fake_get)
    p.route(MOSCOW, SPB, "car")
    p.route(MOSCOW, SPB, "bike")
    p.route(MOSCOW, SPB, "foot")
    assert seen == ["car", "bike", "foot"]


def test_graphhopper_provider_unsupported_transport_raises():
    p = GraphHopperRoutingProvider("gh-key", http_get=lambda *a, **k: _FakeResp({}))
    assert not p.supports("air")
    assert not p.supports("rail")
    with pytest.raises(UnsupportedTransportError):
        p.route(MOSCOW, SPB, "rail")


def test_graphhopper_provider_raises_on_error():
    def fake_get(url, params=None, timeout=None):
        return _FakeResp({"message": "Unauthorized"}, status=401)

    p = GraphHopperRoutingProvider("gh-key", http_get=fake_get)
    with pytest.raises(ProviderUnavailableError):
        p.route(MOSCOW, SPB, "car")


def test_build_provider_chain_with_graphhopper(monkeypatch):
    monkeypatch.setattr(config, "HERE_API_KEY", "")
    monkeypatch.setattr(config, "OSRM_BASE_URL", "")
    monkeypatch.setattr(config, "GRAPHHOPPER_API_KEY", "gh-key")
    chain = build_provider_chain()
    assert [p.name for p in chain] == ["GRAPHHOPPER", "GREAT_CIRCLE"]


def test_route_segment_falls_through_osrm_to_graphhopper():
    def down(url, params=None, timeout=None):
        raise RuntimeError("down")

    def gh_get(url, params=None, timeout=None):
        return _FakeResp({"paths": [{"distance": 634000, "time": 25_200_000, "points": {"coordinates": []}}]})

    chain = [
        HereRoutingProvider("test-key", http_get=down),
        OsrmRoutingProvider("http://localhost:5000", http_get=down),
        GraphHopperRoutingProvider("gh-key", http_get=gh_get),
        GreatCircleRoutingProvider(),
    ]
    seg = route_segment(MOSCOW, SPB, "car", chain=chain)
    assert seg["provider"] == "GRAPHHOPPER"
    assert seg["distance_km"] == pytest.approx(634.0)
    assert len(seg["provider_fallback"]) == 2
