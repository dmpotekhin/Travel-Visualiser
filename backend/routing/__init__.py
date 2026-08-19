"""Routing service: provider abstraction + fallback chain.

Public API (backward compatible with the old backend/routing.py):

    route_segment(fr, to, transport, chain=None) -> dict
        one segment: geometry + distance + duration + provider annotation
    get_provider_for(transport, chain=None) -> RoutingProvider
        transport-aware provider selection
    build_provider_chain() -> list[RoutingProvider]
        ordered chain per ROUTING_PROVIDER_ORDER / ROUTING_FALLBACK_ENABLED

Providers live in routing/here.py, routing/osrm.py, routing/graphhopper.py
and routing/fallback.py; the chain is assembled in routing/factory.py.
"""
from .base import (
    ProviderConfigurationError,
    ProviderNoRouteError,
    ProviderUnavailableError,
    RouteResult,
    RoutingError,
    RoutingProvider,
    UnsupportedTransportError,
)
from .fallback import GreatCircleRoutingProvider
from .factory import build_provider_chain, describe_providers, get_provider_for, route_segment

__all__ = [
    "GreatCircleRoutingProvider",
    "ProviderConfigurationError",
    "ProviderNoRouteError",
    "ProviderUnavailableError",
    "RouteResult",
    "RoutingError",
    "RoutingProvider",
    "UnsupportedTransportError",
    "build_provider_chain",
    "describe_providers",
    "get_provider_for",
    "route_segment",
]
