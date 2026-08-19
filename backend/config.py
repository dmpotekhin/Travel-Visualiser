"""Central configuration loaded from environment / .env."""
from __future__ import annotations

import json
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

# --- HERE API (optional) ---
HERE_API_KEY = os.getenv("HERE_API_KEY", "").strip()

# --- Routing providers (HERE / OSRM / GraphHopper) ---
# Comma-separated provider priority: "auto" = HERE,OSRM,GRAPHHOPPER,GREAT_CIRCLE
ROUTING_PROVIDER_ORDER = os.getenv("ROUTING_PROVIDER_ORDER", "auto").strip()
# When true (default), a failed external provider silently falls through to
# the next one and finally to the deterministic great-circle model. When
# false, provider errors propagate to the caller (strict mode).
ROUTING_FALLBACK_ENABLED = os.getenv("ROUTING_FALLBACK_ENABLED", "true").strip().lower() in (
    "1", "true", "yes", "on",
)
OSRM_BASE_URL = os.getenv("OSRM_BASE_URL", "").strip()
GRAPHHOPPER_API_KEY = os.getenv("GRAPHHOPPER_API_KEY", "").strip()
GRAPHHOPPER_BASE_URL = os.getenv(
    "GRAPHHOPPER_BASE_URL", "https://graphhopper.com/api/1"
).strip()
ROUTING_TIMEOUT_S = float(os.getenv("ROUTING_TIMEOUT_S", "15"))

# --- LLM (optional, for natural-language route parsing) ---
# OpenAI-compatible endpoint: DeepSeek by default, or any compatible provider
# (e.g. HuggingFace Inference: https://router.huggingface.co/v1/chat/completions).
LLM_API_KEY = os.getenv("LLM_API_KEY", os.getenv("DEEPSEEK_API_KEY", "")).strip()
LLM_MODEL = os.getenv("LLM_MODEL", os.getenv("DEEPSEEK_MODEL", "deepseek-chat")).strip()
LLM_URL = os.getenv(
    "LLM_URL", os.getenv("DEEPSEEK_URL", "https://api.deepseek.com/chat/completions")
).strip()
LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "1024"))
# Optional extra JSON body merged into the chat/completions payload, e.g.
# Qwen on HF: {"chat_template_kwargs":{"enable_thinking":false}}
_extra = os.getenv("LLM_EXTRA_JSON", "").strip()
LLM_EXTRA_JSON = json.loads(_extra) if _extra else {}
# Legacy aliases so existing .env / tests keep working
DEEPSEEK_API_KEY = LLM_API_KEY
DEEPSEEK_MODEL = LLM_MODEL
DEEPSEEK_URL = LLM_URL

# --- CesiumJS Ion token (optional, for 3D terrain/imagery) ---
CESIUM_ION_TOKEN = os.getenv("CESIUM_ION_TOKEN", "").strip()

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
