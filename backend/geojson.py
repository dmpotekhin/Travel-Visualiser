"""Build a GeoJSON FeatureCollection from processed route segments."""
from __future__ import annotations

from . import transport as transport_mod


def build_geojson(segments: list[dict]) -> dict:
    """Convert a list of segment dicts into a GeoJSON FeatureCollection.

    Each segment dict has: from, to, transport, distance_km, duration_min,
    geometry (list of [lon, lat]).
    """
    features = []
    for seg in segments:
        features.append(
            {
                "type": "Feature",
                "geometry": {"type": "LineString", "coordinates": seg["geometry"]},
                "properties": {
                    "from": seg["from"],
                    "to": seg["to"],
                    "transport": seg["transport"],
                    "transport_name": transport_mod.name(seg["transport"]),
                    "distance_km": round(seg["distance_km"], 1),
                    "duration_min": round(seg["duration_min"], 1),
                    "color": transport_mod.color(seg["transport"]),
                },
            }
        )

    # also add point features for each city (for labels)
    seen: dict[str, list[float]] = {}
    for seg in segments:
        if seg["geometry"]:
            seen.setdefault(seg["from"], seg["geometry"][0])
            seen.setdefault(seg["to"], seg["geometry"][-1])
    for name, coord in seen.items():
        features.append(
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": coord},
                "properties": {"city": name},
            }
        )

    return {"type": "FeatureCollection", "features": features}


def flatten_coordinates(geojson: dict) -> list[list[float]]:
    """Concatenate all LineString coordinates in order (for marker animation)."""
    out: list[list[float]] = []
    for feat in geojson["features"]:
        if feat["geometry"]["type"] == "LineString":
            out.extend(feat["geometry"]["coordinates"])
    return out
