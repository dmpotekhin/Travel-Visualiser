"""Routing service tests: transport coercion + great-circle fallback provider."""
from __future__ import annotations

import pytest

from backend import geo
from backend import transport as transport_mod
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
    monkeypatch.setattr("backend.config.HERE_API_KEY", "")
    from backend import routing

    moscow = (55.7558, 37.6173)
    spb = (59.9343, 30.3351)
    seg = routing.route_segment(moscow, spb, "car")

    assert seg["provider"] == "GREAT_CIRCLE"
    assert seg["transport"] == "car"
    assert seg["distance_km"] == pytest.approx(geo.haversine_km(*moscow, *spb), rel=1e-3)
    assert seg["duration_min"] >= 1.0
    assert len(seg["geometry"]) > 2
