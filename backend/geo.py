"""Geodesic helpers: haversine distance and great-circle interpolation."""
from __future__ import annotations

import math

EARTH_RADIUS_KM = 6371.0088


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance between two points in kilometres."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlmb / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(min(1.0, math.sqrt(a)))


def geodesic_points(lat1: float, lon1: float, lat2: float, lon2: float, n: int = 64) -> list[list[float]]:
    """Interpolate a great-circle arc into `n` segments.

    Returns a list of [lon, lat] in GeoJSON order for smooth map drawing.
    """
    if n < 1:
        n = 1
    lat1, lon1, lat2, lon2 = map(math.radians, (lat1, lon1, lat2, lon2))

    def _xyz(lat: float, lon: float):
        return (
            math.cos(lat) * math.cos(lon),
            math.cos(lat) * math.sin(lon),
            math.sin(lat),
        )

    p1 = _xyz(lat1, lon1)
    p2 = _xyz(lat2, lon2)
    dot = max(-1.0, min(1.0, sum(a * b for a, b in zip(p1, p2))))
    omega = math.acos(dot)

    if omega < 1e-9:
        return [
            [math.degrees(lon1), math.degrees(lat1)],
            [math.degrees(lon2), math.degrees(lat2)],
        ]

    points: list[list[float]] = []
    for i in range(n + 1):
        t = i / n
        s = math.sin((1 - t) * omega) / math.sin(omega)
        q = math.sin(t * omega) / math.sin(omega)
        x = s * p1[0] + q * p2[0]
        y = s * p1[1] + q * p2[1]
        z = s * p1[2] + q * p2[2]
        lat = math.atan2(z, math.sqrt(x * x + y * y))
        lon = math.atan2(y, x)
        points.append([math.degrees(lon), math.degrees(lat)])
    return points
