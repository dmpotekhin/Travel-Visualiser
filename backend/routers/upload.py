"""POST /upload — parse CSV/Excel, process all routes, return summary + maps."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, UploadFile

from .. import analytics, parsing, pipeline

router = APIRouter()


@router.post("/upload")
async def upload(file: UploadFile):
    if file.filename is None or file.filename == "":
        raise HTTPException(status_code=400, detail="Файл не выбран.")

    content = await file.read()
    try:
        rows = parsing.parse_upload(file.filename, content)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    results = []
    for row in rows:
        try:
            route = pipeline.process_route(row["route"], year=row["year"], note=row["note"])
        except ValueError as e:
            results.append(
                {
                    "route_text": row["route"],
                    "year": row["year"],
                    "error": str(e),
                }
            )
            continue
        results.append(
            {
                "id": route["id"],
                "route_text": route["route_text"],
                "year": route["year"],
                "declared_km": row.get("declared_km"),
                "computed_km": route["total_distance_km"],
                "segments": len(route["segments"]),
                "map_url": f"/map/{route['id']}",
            }
        )

    return {
        "processed": len([r for r in results if "id" in r]),
        "errors": len([r for r in results if "error" in r]),
        "routes": results,
        "maps": [r["map_url"] for r in results if "id" in r],
        "stats": analytics.compute_stats(),
    }
