"""Provider chain assembly and transport-aware selection.

The chain is ordered by ROUTING_PROVIDER_ORDER ("auto" = HERE,OSRM,GRAPHHOPPER,
GREAT_CIRCLE). Providers that are not configured (missing key/URL) are skipped.
With ROUTING_FALLBACK_ENABLED=true the deterministic great-circle provider is
always appended as the last resort; with false it is omitted and failures
propagate as ProviderUnavailableError.
"""
from __future__ import annotations

import logging

from .. import config
from .base import (
    ProviderConfigurationError,
    ProviderUnavailableError,
    RoutingError,
    RoutingProvider,
)
from .fallback import GreatCircleRoutingProvider
from .here import HereRoutingProvider

log = logging.getLogger(__name__)

KNOWN_PROVIDERS = ("HERE", "OSRM", "GRAPHHOPPER", "GREAT_CIRCLE")
DEFAULT_ORDER = ("HERE", "OSRM", "GRAPHHOPPER", "GREAT_CIRCLE")


def _provider_available(name: str, cfg) -> bool:
    if name == "HERE":
        return bool(cfg.HERE_API_KEY)
    if name == "OSRM":
        return bool(cfg.OSRM_BASE_URL)
    if name == "GRAPHHOPPER":
        return bool(cfg.GRAPHHOPPER_API_KEY)
    if name == "GREAT_CIRCLE":
        return True
    return False


def _make_provider(name: str, cfg) -> RoutingProvider:
    if name == "HERE":
        return HereRoutingProvider(
            cfg.HERE_API_KEY,
            timeout=cfg.ROUTING_TIMEOUT_S,
        )
    if name == "OSRM":
        from .osrm import OsrmRoutingProvider

        return OsrmRoutingProvider(
            cfg.OSRM_BASE_URL,
            timeout=cfg.ROUTING_TIMEOUT_S,
        )
    if name == "GRAPHHOPPER":
        from .graphhopper import GraphHopperRoutingProvider

        return GraphHopperRoutingProvider(
            cfg.GRAPHHOPPER_API_KEY,
            base_url=cfg.GRAPHHOPPER_BASE_URL,
            timeout=cfg.ROUTING_TIMEOUT_S,
        )
    if name == "GREAT_CIRCLE":
        return GreatCircleRoutingProvider()
    raise ProviderConfigurationError(f"Неизвестный провайдер маршрутов: {name}")


def _resolve_order(cfg) -> list[str]:
    raw = (cfg.ROUTING_PROVIDER_ORDER or "auto").strip()
    if not raw or raw.lower() == "auto":
        return list(DEFAULT_ORDER)
    names = [n.strip().upper() for n in raw.split(",") if n.strip()]
    unknown = [n for n in names if n not in KNOWN_PROVIDERS]
    if unknown:
        raise ProviderConfigurationError(
            f"Неизвестные провайдеры маршрутов: {', '.join(unknown)}"
        )
    return names


def build_provider_chain(cfg=None) -> list[RoutingProvider]:
    """Assemble the routing provider chain honouring configuration."""
    cfg = cfg or config
    chain: list[RoutingProvider] = []
    for name in _resolve_order(cfg):
        if name == "GREAT_CIRCLE":
            chain.append(GreatCircleRoutingProvider())
        elif _provider_available(name, cfg):
            chain.append(_make_provider(name, cfg))
        else:
            log.info("routing provider %s skipped (not configured)", name)

    has_fallback = any(p.name == "GREAT_CIRCLE" for p in chain)
    if cfg.ROUTING_FALLBACK_ENABLED and not has_fallback:
        chain.append(GreatCircleRoutingProvider())
    if not chain:  # strict mode with nothing configured -> still usable
        chain.append(GreatCircleRoutingProvider())
    return chain


def get_provider_for(transport: str, chain=None) -> RoutingProvider:
    """First provider in the chain that supports the transport type."""
    chain = chain if chain is not None else build_provider_chain()
    for provider in chain:
        if provider.supports(transport):
            return provider
    raise ProviderUnavailableError(
        f"Нет провайдера маршрутов, поддерживающего транспорт: {transport}"
    )


def route_segment(fr, to, transport: str, chain=None) -> dict:
    """Route one segment through the provider chain.

    Backward-compatible with the legacy backend/routing.py: returns a dict
    with transport / distance_km / duration_min / geometry, now also
    annotated with the serving provider (and fallback reasons, if any).
    """
    chain = chain if chain is not None else build_provider_chain()
    errors: list[str] = []
    for provider in chain:
        if not provider.supports(transport):
            continue
        try:
            result = provider.route(fr, to, transport)
        except RoutingError as exc:
            errors.append(f"{provider.name}: {exc}")
            log.warning(
                "routing via %s failed (%s -> %s, %s): %s",
                provider.name, fr, to, transport, exc,
            )
            continue
        segment = result.to_dict()
        if errors:
            segment["provider_fallback"] = errors
            log.info(
                "route %s->%s (%s) served by %s after %d failed provider(s)",
                fr, to, transport, provider.name, len(errors),
            )
        else:
            log.info("route %s->%s (%s) served by %s", fr, to, transport, provider.name)
        return segment

    detail = "; ".join(errors) if errors else f"нет провайдеров для транспорта {transport}"
    raise ProviderUnavailableError(f"Все провайдеры маршрута недоступны: {detail}")
