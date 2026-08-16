"""HTML rendering helpers for the map page."""
from __future__ import annotations

import json
from typing import Optional

from fastapi.responses import HTMLResponse

from . import config

_template_cache: Optional[str] = None


def _template() -> str:
    global _template_cache
    if _template_cache is None:
        _template_cache = (config.FRONTEND_DIR / "map.html").read_text(encoding="utf-8")
    return _template_cache


def _safe_json(obj) -> str:
    return json.dumps(obj, ensure_ascii=False).replace("</", "<\\/")


def render_map_html(inline: Optional[dict] = None, fetch_id: Optional[int] = None) -> HTMLResponse:
    """Render the map page, either with inline route data or a fetch id."""
    cfg = {"inline": inline, "fetch_id": fetch_id}
    html = _template().replace("__ROUTE_CONFIG__", _safe_json(cfg))
    return HTMLResponse(html)
