"""GET /stats, /history, /map/{id}, /api/geojson/{id}."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from .. import analytics, database, pipeline
from ..views import render_map_html

router = APIRouter()


@router.get("/stats")
async def stats():
    return analytics.compute_stats()


@router.get("/history")
async def history():
    rows = database.list_routes()
    return [
        {
            "id": r["id"],
            "route_text": r["route_text"],
            "year": r["year"],
            "note": r["note"],
            "total_distance_km": round(r["total_distance_km"] or 0, 2),
            "total_duration_min": round(r["total_duration_min"] or 0, 1),
            "created_at": r["created_at"],
            "map_url": f"/map/{r['id']}",
        }
        for r in rows
    ]


@router.get("/map/{route_id}")
async def map_page(route_id: int):
    if database.get_route(route_id) is None:
        raise HTTPException(status_code=404, detail="Маршрут не найден.")
    return render_map_html(fetch_id=route_id)


@router.get("/api/geojson/{route_id}")
async def geojson_route(route_id: int):
    route = pipeline.route_from_db(route_id)
    if route is None:
        raise HTTPException(status_code=404, detail="Маршрут не найден.")
    return route
