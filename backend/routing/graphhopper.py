"""GraphHopper provider (cloud API or self-hosted instance).

Profiles: car, bike, foot (bus/ferry route as car). Air/rail are unsupported
and raise UnsupportedTransportError so the provider chain can fall through.
GraphHopper returns unencoded coordinates (points_encoded=false) — no
polyline decoding is required.
"""
from __future__ import annotations

import httpx

from .. import geo
from .base import (
    ProviderUnavailableError,
    RouteResult,
    RoutingProvider,
    UnsupportedTransportError,
)

# transport key -> GraphHopper profile
_GH_PROFILE = {
    "car": "car",
    "bus": "car",
    "ferry": "car",
    "bike": "bike",
    "foot": "foot",
}


class GraphHopperRoutingProvider(RoutingProvider):
    """GraphHopper routing backend (car/bike/foot profiles)."""

    name = "GRAPHHOPPER"
    priority = 30

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = "https://graphhopper.com/api/1",
        http_get=httpx.get,
        timeout: float = 15.0,
    ):
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._get = http_get
        self._timeout = timeout

    def supports(self, transport: str) -> bool:
        return transport in _GH_PROFILE

    def route(self, origin, destination, transport: str) -> RouteResult:
        if transport not in _GH_PROFILE:
            raise UnsupportedTransportError(
                f"GraphHopper не поддерживает транспорт {transport}"
            )
        fr_lat, fr_lon = origin
        to_lat, to_lon = destination
        params = {
            "key": self._api_key,
            "profile": _GH_PROFILE[transport],
            "point": [f"{fr_lat},{fr_lon}", f"{to_lat},{to_lon}"],
            "points_encoded": "false",
        }
        resp = self._get(
            f"{self._base_url}/route", params=params, timeout=self._timeout
        )
        resp.raise_for_status()
        data = resp.json()
        paths = data.get("paths") or []
        if not paths:
            raise ProviderUnavailableError(
                f"GraphHopper не вернул маршруты: {data.get('message', 'no paths')}"
            )
        path = paths[0]
        distance_km = path["distance"] / 1000.0
        duration_min = path["time"] / 60_000.0
        points = path.get("points") or {}
        raw_coords = points.get("coordinates") or []
        # GraphHopper returns [lat, lon]; convert to GeoJSON [lon, lat]
        geometry = [[lon, lat] for lat, lon in raw_coords]
        if not geometry:
            geometry = geo.geodesic_points(fr_lat, fr_lon, to_lat, to_lon)
        return RouteResult(
            transport=transport,
            distance_km=distance_km,
            duration_min=duration_min,
            geometry=geometry,
            provider=self.name,
            provider_info={
                "profile": _GH_PROFILE[transport],
                "geometry_source": "api" if raw_coords else "great-circle",
            },
        )
