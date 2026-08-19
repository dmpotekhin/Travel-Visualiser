"""Deterministic no-network fallback provider (great-circle model).

Always available: haversine distance + geodesic arc geometry. This is the
last link of the fallback chain, so the app stays usable when every
external routing API is unavailable.
"""
from __future__ import annotations

from .. import geo, transport as transport_mod
from .base import RouteResult, RoutingProvider


class GreatCircleRoutingProvider(RoutingProvider):
    name = "GREAT_CIRCLE"
    priority = 1000  # always last

    def supports(self, transport: str) -> bool:
        return True

    def route(self, origin, destination, transport: str) -> RouteResult:
        lat1, lon1 = origin
        lat2, lon2 = destination
        distance_km = geo.haversine_km(lat1, lon1, lat2, lon2)
        duration_min = distance_km / transport_mod.speed_kmh(transport) * 60.0
        geometry = geo.geodesic_points(lat1, lon1, lat2, lon2)
        return RouteResult(
            transport=transport,
            distance_km=distance_km,
            duration_min=duration_min,
            geometry=geometry,
            provider=self.name,
            provider_info={"model": "great-circle (haversine)"},
        )
