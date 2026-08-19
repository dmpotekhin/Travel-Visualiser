"""Routing service: provider abstraction + fallback chain.

Public API (backward compatible with the old backend/routing.py):

    route_segment(fr, to, transport) -> dict
        one segment: geometry + distance + duration + provider info
    route_segments(segments) -> list[RouteResult]
        batch helper over explicit segment specs
    get_provider_for(transport) -> RoutingProvider
        provider selection by transport type
    build_provider_chain() -> list[RoutingProvider]
        ordered provider chain from configuration

Providers live in here.py, osrm.py, graphhopper.py and fallback.py;
the chain itself is assembled in factory.py.
"""
from __future__ import annotations

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


def route_segment(fr, to, transport):
    """Backward-compatible single-segment routing.

    For now: great-circle model (no external providers yet). The provider
    chain (HERE -> OSRM -> GraphHopper -> great-circle) is wired up in
    factory.py during the next milestone phase.
    """
    return GreatCircleRoutingProvider().route(fr, to, transport).to_dict()
