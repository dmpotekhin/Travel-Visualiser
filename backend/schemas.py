"""Pydantic request/response models."""
from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class RouteRequest(BaseModel):
    route: str = Field(..., min_length=2, description="Строка маршрута, города через дефис")
    year: Optional[int] = None
    note: Optional[str] = None


class SegmentModel(BaseModel):
    frm: str
    to: str
    transport: str
    distance_km: float
    duration_min: float
    geometry: List[List[float]]


class RouteResponse(BaseModel):
    id: int
    route_text: str
    year: Optional[int] = None
    segments: List[SegmentModel]
    total_distance_km: float
    total_duration_min: float
    geojson: dict
