"""HERE routing provider (Routing v8 API, Matrix v8 fallback).

HERE supports surface transport only (car/bus/bicycle/pedestrian/ferry).
When the routing call fails, the provider falls back to the Matrix API for
distance/duration and uses a great-circle arc for geometry (same behaviour
as the legacy backend/routing.py). If both fail, the error is propagated
so the provider chain can try the next provider.
"""
from __future__ import annotations

import httpx

from .. import config, geo
from ..here_polyline import decode_polyline
from .base import ProviderUnavailableError, RouteResult, RoutingProvider

# transport key -> HERE Routing v8 transportMode
_HERE_MODE = {
    "car": "car",
    "bus": "bus",
    "bike": "bicycle",
    "foot": "pedestrian",
    "ferry": "car",
}


class HereRoutingProvider(RoutingProvider):
    """HERE routing backend (surface transport only; air/rail unsupported)."""

    name = "HERE"
    priority = 10

    def __init__(
        self,
        api_key: str,
        *,
        routing_url: str = config.HERE_ROUTING_URL,
        matrix_url: str = config.HERE_MATRIX_URL,
        http_get=httpx.get,
        timeout: float = config.ROUTING_TIMEOUT_S,
    ):
        self._api_key = api_key
        self._routing_url = routing_url
        self._matrix_url = matrix_url
        self._get = http_get
        self._timeout = timeout

    def supports(self, transport: str) -> bool:
        return transport in _HERE_MODE

    def route(self, origin, destination, transport: str) -> RouteResult:
        fr_lat, fr_lon = origin
        to_lat, to_lon = destination
        baseline_geometry = geo.geodesic_points(fr_lat, fr_lon, to_lat, to_lon)

        try:
            geometry, distance_km, duration_min, mode = self._route_v8(
                origin, destination, transport
            )
            return RouteResult(
                transport=transport,
                distance_km=distance_km,
                duration_min=duration_min,
                geometry=geometry,
                provider=self.name,
                provider_info={"mode": mode},
            )
        except Exception as route_err:  # noqa: BLE001 - chain decides severity
            try:
                distance_km, duration_min = self._matrix(origin, destination, transport)
            except Exception as matrix_err:  # noqa: BLE001
                raise ProviderUnavailableError(
                    f"HERE недоступен (routing: {route_err}; matrix: {matrix_err})"
                ) from matrix_err
            return RouteResult(
                transport=transport,
                distance_km=distance_km,
                duration_min=duration_min,
                geometry=baseline_geometry,
                provider=self.name,
                provider_info={
                    "mode": _HERE_MODE.get(transport, "car"),
                    "geometry_source": "great-circle",
                    "distance_source": "matrix",
                },
            )

    def _route_v8(self, origin, destination, transport: str):
        fr_lat, fr_lon = origin
        to_lat, to_lon = destination
        mode = _HERE_MODE[transport]
        params = {
            "transportMode": mode,
            "origin": f"{fr_lat},{fr_lon}",
            "destination": f"{to_lat},{to_lon}",
            "return": "polyline,summary",
            "apiKey": self._api_key,
        }
        resp = self._get(self._routing_url, params=params, timeout=self._timeout)
        resp.raise_for_status()
        routes = resp.json().get("routes") or []
        if not routes:
            raise ProviderUnavailableError("HERE вернул пустой список маршрутов")
        section = routes[0]["sections"][0]
        summary = section["summary"]
        distance_km = summary["length"] / 1000.0
        duration_min = summary["duration"] / 60.0

        geometry = None
        polyline = section.get("polyline")
        if polyline:
            try:
                geometry = decode_polyline(polyline)
            except Exception:  # noqa: BLE001 - fall back to baseline geometry
                geometry = None
        if not geometry:
            geometry = geo.geodesic_points(fr_lat, fr_lon, to_lat, to_lon)
        return geometry, distance_km, duration_min, mode

    def _matrix(self, origin, destination, transport: str):
        params = {
            "origin1": f"{origin[0]},{origin[1]}",
            "destination1": f"{destination[0]},{destination[1]}",
            "transportMode": _HERE_MODE.get(transport, "car"),
            "return": "summary",
            "apiKey": self._api_key,
        }
        resp = self._get(self._matrix_url, params=params, timeout=self._timeout)
        resp.raise_for_status()
        matrix = resp.json().get("matrix") or []
        if not matrix or not matrix[0]:
            raise ProviderUnavailableError("HERE matrix вернул пустой ответ")
        summary = matrix[0][0].get("summary", {})
        distance_km = summary.get("length", 0.0) / 1000.0
        duration_min = summary.get("duration", 0.0) / 60.0
        return distance_km, duration_min
