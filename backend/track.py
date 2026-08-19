"""Track / file / URL input parsing.

Converts GPX / KML / GeoJSON files and Google-Maps share links into an ordered
list of ``[lon, lat]`` waypoints (GeoJSON order), then into route segments.

Everything here is dependency-light: GPX and KML are parsed with stdlib
``xml.etree.ElementTree`` (namespace-agnostic via the ``{*}`` wildcard),
GeoJSON with stdlib ``json``. No gpxpy/togeojson native deps.
"""
from __future__ import annotations

import json
import re
import urllib.parse
import xml.etree.ElementTree as ET
from typing import List, Optional

from . import geo, transport as transport_mod

# --------------------------------------------------------------------------
# transport auto-detection by segment distance
# --------------------------------------------------------------------------

def auto_transport(distance_km: float) -> str:
    """Pick a transport for a segment purely from its distance (heuristic)."""
    if distance_km > 1000:
        return "air"
    if distance_km > 200:
        return "rail"
    if distance_km > 30:
        return "car"
    return "foot"


# --------------------------------------------------------------------------
# coordinate extraction
# --------------------------------------------------------------------------

def _num(s: str) -> float:
    return float(s.strip())


def parse_gpx(content: bytes) -> List[List[float]]:
    """Extract ordered ``[lon, lat]`` waypoints from a GPX document.

    Collects ``<trkpt>`` (track points), ``<rtept>`` (route points) and ``<wpt>``
    (waypoints) in document order.
    """
    try:
        root = ET.fromstring(content)
    except ET.ParseError as e:
        raise ValueError(f"Не удалось прочитать GPX: {e}")

    pts: List[List[float]] = []
    for el in root.iter():
        local = el.tag.rsplit("}", 1)[-1]
        if local not in ("trkpt", "rtept", "wpt"):
            continue
        lat = el.get("lat")
        lon = el.get("lon")
        if lat is None or lon is None:
            continue
        try:
            pts.append([_num(lon), _num(lat)])
        except ValueError:
            continue
    if len(pts) < 2:
        raise ValueError("В GPX-файле не найдено ни одного трека (нужно ≥2 точек).")
    return pts


def parse_kml(content: bytes) -> List[List[float]]:
    """Extract ordered ``[lon, lat]`` waypoints from a KML/KMZ document.

    Handles ``<coordinates>`` blocks inside LineString / Point / gx:Track, and
    simple ``lon,lat[,alt]`` whitespace-separated lists.
    """
    try:
        root = ET.fromstring(content)
    except ET.ParseError as e:
        raise ValueError(f"Не удалось прочитать KML: {e}")

    pts: List[List[float]] = []
    for el in root.iter():
        if el.tag.rsplit("}", 1)[-1] != "coordinates":
            continue
        text = (el.text or "").strip()
        if not text:
            continue
        for token in text.split():
            parts = token.split(",")
            if len(parts) < 2:
                continue
            try:
                pts.append([_num(parts[0]), _num(parts[1])])
            except ValueError:
                continue
    if len(pts) < 2:
        raise ValueError("В KML-файле не найдено ни одной линии (нужно ≥2 точек).")
    return pts


def _geojson_coords(obj) -> List[List[float]]:
    """Recursively flatten a GeoJSON object into ordered ``[lon, lat]`` points."""
    t = obj.get("type")
    out: List[List[float]] = []

    if t == "FeatureCollection":
        for f in obj.get("features", []):
            out.extend(_geojson_coords(f))
    elif t == "Feature":
        out.extend(_geojson_coords(obj.get("geometry", {})))
    elif t == "GeometryCollection":
        for g in obj.get("geometries", []):
            out.extend(_geojson_coords(g))
    elif t == "LineString":
        out.extend([[float(c[0]), float(c[1])] for c in obj.get("coordinates", [])])
    elif t == "MultiLineString":
        for line in obj.get("coordinates", []):
            out.extend([[float(c[0]), float(c[1])] for c in line])
    elif t == "Point":
        c = obj.get("coordinates", [])
        if len(c) >= 2:
            out.append([float(c[0]), float(c[1])])
    elif t == "MultiPoint":
        out.extend([[float(c[0]), float(c[1])] for c in obj.get("coordinates", [])])
    return out


def parse_geojson(content: bytes) -> List[List[float]]:
    try:
        obj = json.loads(content)
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        raise ValueError(f"Не удалось прочитать GeoJSON: {e}")
    pts = _geojson_coords(obj)
    if len(pts) < 2:
        raise ValueError("В GeoJSON не найдено линии (нужно ≥2 координат).")
    return pts


def parse_track(content: bytes, filename: str) -> List[List[float]]:
    """Dispatch by file extension to the right parser."""
    name = filename.lower()
    if name.endswith(".gpx"):
        return parse_gpx(content)
    if name.endswith((".kml", ".kmz")):
        # KMZ is a zipped KML; extract doc.kml if possible, else fail clearly.
        if name.endswith(".kmz"):
            return parse_kml(_extract_kmz(content))
        return parse_kml(content)
    if name.endswith((".geojson", ".json")):
        return parse_geojson(content)
    raise ValueError("Поддерживаются только файлы .gpx, .kml, .kmz и .geojson/.json.")


def _extract_kmz(content: bytes) -> bytes:
    """Extract ``doc.kml`` from a KMZ (zip) archive."""
    import io
    import zipfile

    try:
        with zipfile.ZipFile(io.BytesIO(content)) as zf:
            for name in zf.namelist():
                if name.lower().endswith(".kml"):
                    return zf.read(name)
    except zipfile.BadZipFile as e:
        raise ValueError(f"Не удалось открыть KMZ-архив: {e}")
    raise ValueError("В KMZ-архиве не найден файл .kml.")


# --------------------------------------------------------------------------
# Google Maps link parsing
# --------------------------------------------------------------------------

_COORD_PAIR_RE = re.compile(r"(-?\d{1,3}\.\d+)[,;]\s*(-?\d{1,3}\.\d+)")


def parse_gmaps_url(url: str) -> List[List[float]]:
    """Extract waypoints from a Google Maps link.

    Works for full links that embed numeric coordinates (``@lat,lng``,
    ``daddr=lat,lng``, ``ll=lat,lng``). Short ``goo.gl/maps/...`` links must be
    expanded first (we can't resolve the redirect here).
    """
    decoded = urllib.parse.unquote(url)
    pts: List[List[float]] = []
    for m in _COORD_PAIR_RE.finditer(decoded):
        lat, lon = float(m.group(1)), float(m.group(2))
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            continue
        pt = [lon, lat]
        if not pts or pts[-1] != pt:
            pts.append(pt)
    if len(pts) < 2:
        raise ValueError(
            "Не удалось извлечь маршрут из ссылки. Используйте полную ссылку с "
            "координатами (@lat,lng) или вставьте названия городов напрямую."
        )
    return pts


# --------------------------------------------------------------------------
# simplification (Douglas-Peucker)
# --------------------------------------------------------------------------

def _perpendicular_dist(pt, a, b) -> float:
    """Distance (km) from point ``pt`` to segment ``a-b`` (all [lon,lat])."""
    px, py = pt
    ax, ay = a
    bx, by = b
    # approximate using local equirectangular in km (fine for simplification)
    dx, dy = bx - ax, by - ay
    if dx == 0 and dy == 0:
        return geo.haversine_km(py, px, ay, ax)
    t = ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)
    t = max(0.0, min(1.0, t))
    cx, cy = ax + t * dx, ay + t * dy
    return geo.haversine_km(py, px, cy, cx)


def simplify(coords: List[List[float]], tolerance_km: float = 1.0) -> List[List[float]]:
    """Douglas-Peucker simplification (keeps first/last, tolerance in km)."""
    if len(coords) <= 2:
        return list(coords)
    # iterative stack to avoid recursion depth on long tracks
    keep = {0, len(coords) - 1}
    stack = [(0, len(coords) - 1)]
    while stack:
        start, end = stack.pop()
        if end - start < 2:
            continue
        max_d, max_i = 0.0, -1
        for i in range(start + 1, end):
            d = _perpendicular_dist(coords[i], coords[start], coords[end])
            if d > max_d:
                max_d, max_i = d, i
        if max_d > tolerance_km and max_i != -1:
            keep.add(max_i)
            stack.append((start, max_i))
            stack.append((max_i, end))
    return [coords[i] for i in sorted(keep)]


def simplify_to(coords: List[List[float]], max_points: int = 24) -> List[List[float]]:
    """Simplify a track to at most ``max_points`` waypoints."""
    if len(coords) <= max_points:
        return list(coords)
    # adaptive tolerance: start coarse, refine until under the cap
    lo, hi = 0.0, 1000.0
    result = coords
    for _ in range(12):
        mid = (lo + hi) / 2
        result = simplify(coords, mid)
        if len(result) <= max_points:
            hi = mid
        else:
            lo = mid
    return simplify(coords, hi) if len(result) > max_points else result


# --------------------------------------------------------------------------
# coordinates -> segments
# --------------------------------------------------------------------------

def coords_to_segments(
    coords: List[List[float]],
    transport: str = "auto",
    names: Optional[List[str]] = None,
) -> List[dict]:
    """Turn an ordered waypoint list into segment dicts.

    Each consecutive pair becomes a segment. Transport is either an explicit key,
    ``"auto"`` (distance heuristic), or taken per-segment from ``names`` transport
    annotations. Geometry is a straight line between the two points.
    """
    segments: List[dict] = []
    for i in range(len(coords) - 1):
        a, b = coords[i], coords[i + 1]
        dist = geo.haversine_km(a[1], a[0], b[1], b[0])
        t = transport if transport != "auto" else auto_transport(dist)
        from_name = names[i] if names else f"Точка {i + 1}"
        to_name = names[i + 1] if names else f"Точка {i + 2}"
        segments.append(
            {
                "from": from_name,
                "to": to_name,
                "transport": t,
                "distance_km": round(dist, 2),
                "duration_min": round(dist / transport_mod.speed_kmh(t) * 60.0, 1),
                "geometry": [a, b],
            }
        )
    return segments
