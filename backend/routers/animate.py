"""POST /animate — accepts a route string, returns an HTML map page."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from .. import pipeline
from ..views import render_map_html

router = APIRouter()


async def _extract(request: Request) -> dict:
    ct = request.headers.get("content-type", "")
    if "application/json" in ct:
        return await request.json()
    form = await request.form()
    year = form.get("year")
    return {
        "route": form.get("route"),
        "year": year,
        "note": form.get("note"),
    }


@router.post("/animate")
async def animate(request: Request):
    data = await _extract(request)
    route = (data.get("route") or "").strip()
    if not route:
        raise HTTPException(status_code=400, detail="Поле 'route' обязательно.")

    year = data.get("year")
    try:
        year = int(year) if year not in (None, "") else None
    except (TypeError, ValueError):
        year = None

    try:
        result = pipeline.process_route(route, year=year, note=data.get("note"))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    return render_map_html(inline=result)
