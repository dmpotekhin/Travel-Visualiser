"""Studio endpoints for the video-constructor wizard.

- ``POST /api/parse``      — parse a route string, natural-language description,
  or Google-Maps link into a normalized preview (no DB save).
- ``POST /api/parse-file`` — parse an uploaded GPX/KML/GeoJSON into a preview.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, UploadFile

from .. import ai, config, geocoding, pipeline, track

router = APIRouter()


@router.get("/api/config")
async def api_config():
    return {
        "cesium_ion_token": config.CESIUM_ION_TOKEN,
        "deepseek": bool(config.DEEPSEEK_API_KEY),
        "here": bool(config.HERE_API_KEY),
    }


@router.post("/api/geocode")
async def geocode(request: Request):
    data = await request.json()
    name = (data.get("name") or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Пустое название.")
    try:
        lat, lon = geocoding.geocode_city(name)
        return {"name": name, "coord": [lon, lat]}
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.post("/api/parse")
async def parse(request: Request):
    data = await request.json()
    kind = data.get("kind", "text")
    text = (data.get("input") or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="Пустой ввод.")

    try:
        if kind == "gmaps":
            coords = track.parse_gmaps_url(text)
            return pipeline.preview_track(coords, route_text="Маршрут из Google Maps")
        if kind == "nl":
            text = ai.parse_natural_language(text)
        return pipeline.preview_route(text)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.post("/api/parse-file")
async def parse_file(file: UploadFile):
    if not file.filename:
        raise HTTPException(status_code=400, detail="Файл не выбран.")

    content = await file.read()
    try:
        coords = track.parse_track(content, file.filename)
        coords = track.simplify_to(coords, max_points=24)
        return pipeline.preview_track(coords, route_text=file.filename)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
