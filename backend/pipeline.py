"""Route processing pipeline: parse -> geocode -> route -> geojson -> persist."""
from __future__ import annotations

import json
from typing import Optional

from . import database, geocoding, geojson as geojson_mod, routing, transport as transport_mod
from . import track as track_mod


def _enrich_segment(seg: dict) -> dict:
    """Attach human-friendly transport metadata to a segment dict."""
    seg["transport_name"] = transport_mod.name(seg["transport"])
    seg["emoji"] = transport_mod.emoji(seg["transport"])
    seg["color"] = transport_mod.color(seg["transport"])
    return seg


def _build_segments(route_text: str) -> list[dict]:
    """Parse a route string into enriched segments (geocode + route each leg)."""
    spec = transport_mod.parse_route(route_text)
    segments = []
    for s in spec:
        fr = geocoding.geocode_city(s["from"])
        to = geocoding.geocode_city(s["to"])
        seg = routing.route_segment(fr, to, s["transport"])
        seg["from"] = s["from"]
        seg["to"] = s["to"]
        segments.append(_enrich_segment(seg))
    return segments


def _points_from_segments(segments: list[dict]) -> list[dict]:
    """Derive an ordered list of stops (name + coord) from segments."""
    pts: list[dict] = []
    for i, s in enumerate(segments):
        if not s["geometry"]:
            continue
        if i == 0:
            pts.append({"name": s["from"], "coord": s["geometry"][0]})
        pts.append({"name": s["to"], "coord": s["geometry"][-1]})
    return pts


def _summarize(segments: list[dict]) -> dict:
    total_km = round(sum(s["distance_km"] for s in segments), 2)
    total_dur = round(sum(s["duration_min"] for s in segments), 1)
    return {
        "segments": segments,
        "points": _points_from_segments(segments),
        "total_distance_km": total_km,
        "total_duration_min": total_dur,
        "geojson": geojson_mod.build_geojson(segments),
    }


def _coord_label(coord) -> str:
    """Human-readable label for a bare (lat, lon) coordinate."""
    return f"{coord[0]:.3f}, {coord[1]:.3f}"


def route_legs(legs: list[dict]) -> dict:
    """Route arbitrary legs by coordinates (no persistence, no geocoding).

    Each leg: {"from": (lat, lon), "to": (lat, lon), "transport": key,
               "from_name": str | None, "to_name": str | None}.
    Used by POST /api/routes so the frontend never talks to a provider.
    """
    segments = []
    for leg in legs:
        seg = routing.route_segment(leg["from"], leg["to"], leg["transport"])
        seg["from"] = leg.get("from_name") or _coord_label(leg["from"])
        seg["to"] = leg.get("to_name") or _coord_label(leg["to"])
        segments.append(_enrich_segment(seg))
    return _summarize(segments)


def preview_route(route_text: str) -> dict:
    """Process a route string WITHOUT persisting (for the wizard preview)."""
    segments = _build_segments(route_text)
    out = _summarize(segments)
    out["route_text"] = route_text
    return out


def preview_track(coords: list[list[float]], route_text: Optional[str] = None) -> dict:
    """Build a preview from raw waypoints (GPX/KML/GeoJSON/Google-Maps coords)."""
    segments = track_mod.coords_to_segments(coords, transport="auto")
    segments = [_enrich_segment(s) for s in segments]
    out = _summarize(segments)
    out["route_text"] = route_text or "Трек"
    return out


def process_route(route_text: str, year: Optional[int] = None, note: Optional[str] = None) -> dict:
    segments = _build_segments(route_text)
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
        "points": _points_from_segments(segments),
        "total_distance_km": round(total_km, 2),
        "total_duration_min": round(total_dur, 1),
        "geojson": gj,
    }


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
        "points": _points_from_segments(segments),
        "total_distance_km": round(total_km, 2),
        "total_duration_min": round(total_dur, 1),
        "geojson": geojson_mod.build_geojson(segments),
        "created_at": row["created_at"],
    }
