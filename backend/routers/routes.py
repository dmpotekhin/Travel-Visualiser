"""Provider-agnostic route calculation API.

POST /api/routes   — calculate routes for explicit legs (coordinates), no persistence.
GET  /api/providers — diagnostic: which routing providers are configured/active.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from .. import config, pipeline, routing, transport as transport_mod

router = APIRouter(prefix="/api", tags=["routes"])


class RoutePoint(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    name: Optional[str] = None


class RouteLeg(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    from_: RoutePoint = Field(alias="from")
    to: RoutePoint
    transport: Optional[str] = None


class RouteRequest(BaseModel):
    segments: list[RouteLeg] = Field(min_length=1)


@router.post("/routes")
def calculate_routes(req: RouteRequest) -> dict:
    """Route explicit legs through the provider chain (frontend stays agnostic)."""
    legs = []
    for leg in req.segments:
        try:
            transport = (
                transport_mod.coerce_transport(leg.transport)
                if leg.transport
                else transport_mod.DEFAULT_TRANSPORT
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc))
        legs.append(
            {
                "from": (leg.from_.lat, leg.from_.lon),
                "from_name": leg.from_.name,
                "to": (leg.to.lat, leg.to.lon),
                "to_name": leg.to.name,
                "transport": transport,
            }
        )
    return pipeline.route_legs(legs)


@router.get("/providers")
def list_providers() -> dict:
    """Diagnostic endpoint: provider configuration and chain state."""
    return {
        "order": config.ROUTING_PROVIDER_ORDER,
        "fallback_enabled": config.ROUTING_FALLBACK_ENABLED,
        "providers": routing.describe_providers(),
    }
