"""Route processing pipeline: parse -> geocode -> route -> geojson -> persist."""
from __future__ import annotations

import json
from typing import Optional

from . import database, geocoding, geojson as geojson_mod, routing, transport as transport_mod


def _enrich_segment(seg: dict) -> dict:
    """Attach human-friendly transport metadata to a segment dict."""
    seg["transport_name"] = transport_mod.name(seg["transport"])
    seg["emoji"] = transport_mod.emoji(seg["transport"])
    seg["color"] = transport_mod.color(seg["transport"])
    return seg


def _build_route(route_text: str, year: Optional[int], note: Optional[str]) -> dict:
    spec = transport_mod.parse_route(route_text)
    segments = []
    for s in spec:
        fr = geocoding.geocode_city(s["from"])
        to = geocoding.geocode_city(s["to"])
        seg = routing.route_segment(fr, to, s["transport"])
        seg["from"] = s["from"]
        seg["to"] = s["to"]
        segments.append(_enrich_segment(seg))

    total_km = sum(s["distance_km"] for s in segments)
    total_dur = sum(s["duration_min"] for s in segments)
    gj = geojson_mod.build_geojson(segments)

    route_id = database.save_route(
        route_text, segments, total_km, total_dur, year=year, note=note
    )

    return {
        "id": route_id,
        "route_text": route_text,
        "year": year,
        "note": note,
        "segments": segments,
        "total_distance_km": round(total_km, 2),
        "total_duration_min": round(total_dur, 1),
        "geojson": gj,
    }


def process_route(route_text: str, year: Optional[int] = None, note: Optional[str] = None) -> dict:
    return _build_route(route_text, year, note)


def route_from_db(route_id: int) -> Optional[dict]:
    row = database.get_route(route_id)
    if row is None:
        return None
    segments = json.loads(row["segments_json"])
    segments = [_enrich_segment(s) for s in segments]
    total_km = sum(s["distance_km"] for s in segments)
    total_dur = sum(s["duration_min"] for s in segments)
    return {
        "id": row["id"],
        "route_text": row["route_text"],
        "year": row["year"],
        "note": row["note"],
        "segments": segments,
        "total_distance_km": round(total_km, 2),
        "total_duration_min": round(total_dur, 1),
        "geojson": geojson_mod.build_geojson(segments),
        "created_at": row["created_at"],
    }
