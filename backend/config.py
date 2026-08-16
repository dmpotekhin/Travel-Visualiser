"""Central configuration loaded from environment / .env."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

# --- HERE API (optional) ---
HERE_API_KEY = os.getenv("HERE_API_KEY", "").strip()

# --- Paths ---
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "travel.db"
GEOJSON_DIR = DATA_DIR / "maps"
FRONTEND_DIR = BASE_DIR / "frontend"

# --- Server ---
HOST = os.getenv("HOST", "127.0.0.1")
PORT = int(os.getenv("PORT", "8000"))

# --- External API endpoints ---
HERE_GEOCODE_URL = "https://geocode.search.hereapi.com/v1/geocode"
HERE_ROUTING_URL = "https://router.hereapi.com/v8/routes"
HERE_MATRIX_URL = "https://matrix.router.hereapi.com/v8/matrix"
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
NOMINATIM_USER_AGENT = "travel-visualizer/1.0 (local personal app)"

# --- Constants ---
EARTH_EQUATOR_KM = 40_075.0
MOON_DISTANCE_KM = 384_400.0
KM_PER_MILE = 1.609344

for _d in (DATA_DIR, GEOJSON_DIR):
    _d.mkdir(parents=True, exist_ok=True)
