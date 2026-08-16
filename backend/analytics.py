"""Analytics over the route history."""
from __future__ import annotations

from collections import Counter
from typing import List, Optional

from . import config, database, transport as transport_mod

ROUND = 1


def _fmt(v: float) -> float:
    return round(v, ROUND)


def compute_stats(segments: Optional[List[dict]] = None) -> dict:
    """Aggregate stats. If segments omitted, pull everything from the DB."""
    if segments is None:
        segments = database.all_segments()

    # group segments into routes by route_id
    routes: dict[int, dict] = {}
    for s in segments:
        rid = s.get("route_id", 0)
        r = routes.setdefault(rid, {"segments": [], "year": s.get("year")})
        r["segments"].append(s)

    total_km = sum(s["distance_km"] for s in segments)
    total_dur = sum(s["duration_min"] for s in segments)
    n_routes = len(routes) or (1 if segments else 0)

    # per-transport aggregates
    by_transport: dict[str, dict] = {}
    for s in segments:
        t = s["transport"]
        b = by_transport.setdefault(t, {"km": 0.0, "min": 0.0, "count": 0})
        b["km"] += s["distance_km"]
        b["min"] += s["duration_min"]
        b["count"] += 1

    transport_share = [
        {
            "transport": t,
            "name": transport_mod.name(t),
            "km": _fmt(b["km"]),
            "percent": _fmt(b["km"] / total_km * 100) if total_km else 0.0,
            "hours": _fmt(b["min"] / 60),
        }
        for t, b in sorted(by_transport.items(), key=lambda kv: -kv[1]["km"])
    ]

    # per-year distribution
    by_year: dict[int, float] = {}
    for rid, r in routes.items():
        y = r["year"]
        km = sum(s["distance_km"] for s in r["segments"])
        by_year[y if y else 0] = by_year.get(y if y else 0, 0.0) + km

    year_distribution = [
        {"year": y, "km": _fmt(km)}
        for y, km in sorted(by_year.items(), key=lambda kv: (kv[0] == 0, kv[0]))
    ]

    # top-5 longest routes
    route_totals = [
        {
            "route_id": rid,
            "route_text": " – ".join(s["from"] for s in r["segments"]) + " – " + r["segments"][-1]["to"],
            "km": _fmt(sum(s["distance_km"] for s in r["segments"])),
            "year": r["year"],
        }
        for rid, r in routes.items()
    ]
    top_routes = sorted(route_totals, key=lambda x: -x["km"])[:5]

    # top-5 cities by frequency
    city_counter: Counter = Counter()
    for s in segments:
        city_counter[s["from"]] += 1
        city_counter[s["to"]] += 1
    top_cities = [{"city": c, "count": n} for c, n in city_counter.most_common(5)]

    return {
        "total_km": _fmt(total_km),
        "total_miles": _fmt(total_km / config.KM_PER_MILE),
        "equators": _fmt(total_km / config.EARTH_EQUATOR_KM),
        "moon_distance": _fmt(total_km / config.MOON_DISTANCE_KM),
        "avg_km_per_route": _fmt(total_km / n_routes) if n_routes else 0.0,
        "total_hours": _fmt(total_dur / 60),
        "total_days": _fmt(total_dur / 60 / 24),
        "routes_count": n_routes,
        "segments_count": len(segments),
        "transport_share": transport_share,
        "year_distribution": year_distribution,
        "top_routes": top_routes,
        "top_cities": top_cities,
    }
