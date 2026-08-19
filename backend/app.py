"""FastAPI application assembly."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import config, database
from .routers import animate, stats, studio, upload


@asynccontextmanager
async def lifespan(app: FastAPI):
    database.init_db()
    yield


app = FastAPI(title="Travel Visualizer", version="1.0.0", lifespan=lifespan)

# Routers MUST be registered before the static mount (which shadows "/").
app.include_router(animate.router)
app.include_router(upload.router)
app.include_router(stats.router)
app.include_router(studio.router)


@app.get("/health")
async def health():
    return {"status": "ok", "here_api_key": bool(config.HERE_API_KEY)}


@app.get("/wizard")
async def wizard():
    return FileResponse(config.FRONTEND_DIR / "wizard.html")


@app.get("/studio")
async def studio_page():
    return FileResponse(config.FRONTEND_DIR / "studio.html")


# Static frontend LAST.
app.mount("/", StaticFiles(directory=str(config.FRONTEND_DIR), html=True), name="frontend")
