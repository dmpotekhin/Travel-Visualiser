"""OSRM provider (public demo server or self-hosted instance).

Profile mapping: car/bus/ferry -> driving, bike -> cycling, foot -> walking.
Air/rail are unsupported and raise UnsupportedTransportError (the provider
chain then falls through to the next provider).
"""
from __future__ import annotations

import httpx

from .. import geo
from .base import (
    ProviderNoRouteError,
    ProviderUnavailableError,
    RouteResult,
    RoutingProvider,
    UnsupportedTransportError,
)

# transport key -> OSRM profile
_OSRM_PROFILE = {
    "car": "driving",
    "bus": "driving",
    "ferry": "driving",
    "bike": "cycling",
    "foot": "walking",
}


def _decode_polyline(polyline: str, precision: int = 5) -> list[list[float]]:
    """Decode Google polyline (OSRM `geometries=polyline`) to [[lon, lat], ...]."""
    factor = float(10**precision)
    coords: list[list[float]] = []
    lat = lng = 0
    index = 0
    length = len(polyline)
    while index < length:
        result = 0
        shift = 0
        while True:
            b = ord(polyline[index]) - 63
            index += 1
            result |= (b & 0x1F) << shift
            shift += 5
            if b < 0x20:
                break
        lat += ~(result >> 1) if (result & 1) else (result >> 1)
        result = 0
        shift = 0
        while True:
            b = ord(polyline[index]) - 63
            index += 1
            result |= (b & 0x1F) << shift
            shift += 5
            if b < 0x20:
                break
        lng += ~(result >> 1) if (result & 1) else (result >> 1)
        coords.append([lng / factor, lat / factor])
    return coords


class OsrmRoutingProvider(RoutingProvider):
    """OSRM routing backend (road/bicycle/walking profiles)."""

    name = "OSRM"
    priority = 20

    def __init__(
        self,
        base_url: str,
        *,
        http_get=httpx.get,
        timeout: float = 15.0,
    ):
        self._base_url = base_url.rstrip("/")
        self._get = http_get
        self._timeout = timeout

    def supports(self, transport: str) -> bool:
        return transport in _OSRM_PROFILE

    def route(self, origin, destination, transport: str) -> RouteResult:
        if transport not in _OSRM_PROFILE:
            raise UnsupportedTransportError(f"OSRM не поддерживает транспорт {transport}")
        fr_lat, fr_lon = origin
        to_lat, to_lon = destination
        profile = _OSRM_PROFILE[transport]
        url = (
            f"{self._base_url}/{profile}/{fr_lon},{fr_lat};{to_lon},{to_lat}"
        )
        params = {"overview": "full", "geometries": "polyline"}
        resp = self._get(url, params=params, timeout=self._timeout)
        resp.raise_for_status()
        data = resp.json()
        code = data.get("code")
        if code != "Ok":
            if code == "NoRoute":
                raise ProviderNoRouteError(
                    f"OSRM не смог построить маршрут: {data.get('message', code)}"
                )
            raise ProviderUnavailableError(f"OSRM вернул код: {code}")
        routes = data.get("routes") or []
        if not routes:
            raise ProviderNoRouteError("OSRM не вернул маршруты")
        route = routes[0]
        distance_km = route["distance"] / 1000.0
        duration_min = route["duration"] / 60.0
        encoded = route.get("geometry") or ""
        if encoded:
            geometry = _decode_polyline(encoded)
        else:
            geometry = geo.geodesic_points(fr_lat, fr_lon, to_lat, to_lon)
        return RouteResult(
            transport=transport,
            distance_km=distance_km,
            duration_min=duration_min,
            geometry=geometry,
            provider=self.name,
            provider_info={
                "profile": profile,
                "geometry_source": "polyline" if encoded else "great-circle",
            },
        )
