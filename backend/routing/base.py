"""Routing provider abstraction: domain model + provider interface.

Route calculation depends on the `RoutingProvider` abstraction instead of
concrete external APIs. Providers (HERE, OSRM, GraphHopper, great-circle)
live in this package; the fallback chain is assembled in factory.py.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, Sequence


class RoutingError(Exception):
    """Base class for all routing errors."""


class ProviderConfigurationError(RoutingError):
    """Provider is misconfigured (missing key, bad URL, unknown name)."""


class ProviderUnavailableError(RoutingError):
    """Provider could not be reached (network, timeout, HTTP 5xx)."""


class ProviderNoRouteError(RoutingError):
    """Provider responded but could not produce a route for the request."""


class UnsupportedTransportError(RoutingError):
    """Provider does not support the requested transport type."""


@dataclass
class RouteResult:
    """Provider-independent route for one segment.

    `geometry` is a list of [lon, lat] pairs (GeoJSON order).
    `provider` is the public provider name, e.g. "HERE", "OSRM",
    "GRAPHHOPPER" or "GREAT_CIRCLE".
    """

    transport: str
    distance_km: float
    duration_min: Optional[float]
    geometry: Sequence[Sequence[float]]
    provider: str
    provider_info: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Serialize to the legacy segment dict (keys preserved)."""
        out = {
            "transport": self.transport,
            "distance_km": round(max(self.distance_km, 0.0), 2),
            "duration_min": round(max(self.duration_min or 1.0, 1.0), 1),
            "geometry": [list(pt) for pt in self.geometry],
            "provider": self.provider,
        }
        if self.provider_info:
            out["provider_info"] = self.provider_info
        return out


class RoutingProvider(ABC):
    """Interface for any routing backend.

    Implementations must be stateless (or keep only immutable config),
    so the same instance can serve every request.
    """

    #: public provider name, used in GeoJSON properties and logs
    name: str = "PROVIDER"
    #: lower number = tried earlier in the fallback chain
    priority: int = 100

    @abstractmethod
    def supports(self, transport: str) -> bool:
        """Whether this provider can route the given transport key."""

    @abstractmethod
    def route(self, origin, destination, transport: str) -> RouteResult:
        """Route one segment.

        origin / destination are (lat, lon) tuples.
        Raises a RoutingError subclass on any failure — providers never
        swallow errors silently; the chain decides whether to fall back.
        """
