"""Segment routing.

With a HERE API key: real road/rail geometry and distances via HERE Routing v8,
with a Matrix API fallback for distance/duration only.

Without a key: great-circle (haversine) distance + geodesic arc geometry.
Air segments always use the great-circle model (no public airline routing).
"""
from __future__ import annotations

import httpx

from . import config, geo, transport as transport_mod
from .here_polyline import decode_polyline

# transport key -> HERE Routing v8 transportMode
_HERE_MODE = {
    "car": "car",
    "bus": "bus",
    "bike": "bicycle",
    "foot": "pedestrian",
    "ferry": "car",
}


def _here_route(fr, to, transport):
    """HERE Routing v8 -> (geometry, distance_km, duration_min)."""
    params = {
        "transportMode": _HERE_MODE[transport],
        "origin": f"{fr[0]},{fr[1]}",
        "destination": f"{to[0]},{to[1]}",
        "return": "polyline,summary",
        "apiKey": config.HERE_API_KEY,
    }
    r = httpx.get(config.HERE_ROUTING_URL, params=params, timeout=15.0)
    r.raise_for_status()
    routes = r.json().get("routes", [])
    if not routes:
        raise ValueError("HERE returned no routes")
    section = routes[0]["sections"][0]
    summary = section["summary"]
    distance_km = summary["length"] / 1000.0
    duration_min = summary["duration"] / 60.0

    geometry = None
    poly = section.get("polyline")
    if poly:
        try:
            geometry = decode_polyline(poly)
        except Exception:
            geometry = None
    if not geometry:
        geometry = geo.geodesic_points(fr[0], fr[1], to[0], to[1])
    return geometry, distance_km, duration_min


def _here_matrix(fr, to, transport):
    """HERE Matrix v8 -> (distance_km, duration_min)."""
    params = {
        "origin": f"{fr[0]},{fr[1]}",
        "destination": f"{to[0]},{to[1]}",
        "routingMode": "fast",
        "transportMode": _HERE_MODE.get(transport, "car"),
        "apiKey": config.HERE_API_KEY,
    }
    r = httpx.get(config.HERE_MATRIX_URL, params=params, timeout=15.0)
    r.raise_for_status()
    entry = r.json()["matrix"][0][0]
    summary = entry.get("summary", {})
    return summary.get("length", 0) / 1000.0, summary.get("duration", 0) / 60.0


def route_segment(fr, to, transport):
    """Compute geometry + distance + duration for one city -> city segment.

    `fr` and `to` are (lat, lon) tuples.
    """
    lat1, lon1 = fr
    lat2, lon2 = to
    speed = transport_mod.speed_kmh(transport)

    # baseline great-circle model
    distance_km = geo.haversine_km(lat1, lon1, lat2, lon2)
    geometry = geo.geodesic_points(lat1, lon1, lat2, lon2)
    duration_min = distance_km / speed * 60.0

    # HERE enhancement for surface transport (rail/ferry fall back to car mode
    # or great-circle if the API doesn't support them).
    if transport not in ("air", "rail") and config.HERE_API_KEY:
        try:
            geometry, distance_km, duration_min = _here_route(fr, to, transport)
        except Exception:
            try:
                distance_km, duration_min = _here_matrix(fr, to, transport)
            except Exception:
                duration_min = distance_km / speed * 60.0

    distance_km = max(distance_km, 0.0)
    duration_min = max(duration_min, 1.0)

    return {
        "transport": transport,
        "distance_km": round(distance_km, 2),
        "duration_min": round(duration_min, 1),
        "geometry": geometry,
    }
