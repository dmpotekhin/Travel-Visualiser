"""SQLite persistence for processed routes."""
from __future__ import annotations

import json
import sqlite3
from typing import Optional

from . import config

_SCHEMA = """
CREATE TABLE IF NOT EXISTS routes (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    route_text        TEXT NOT NULL,
    year              INTEGER,
    note              TEXT,
    total_distance_km REAL,
    total_duration_min REAL,
    segments_json     TEXT NOT NULL,
    geojson_path      TEXT,
    created_at        TEXT DEFAULT (datetime('now', 'localtime'))
);
"""


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with get_connection() as conn:
        conn.execute(_SCHEMA)


def save_route(
    route_text: str,
    segments: list[dict],
    total_distance_km: float,
    total_duration_min: float,
    year: Optional[int] = None,
    note: Optional[str] = None,
    geojson_path: Optional[str] = None,
) -> int:
    with get_connection() as conn:
        cur = conn.execute(
            """INSERT INTO routes
               (route_text, year, note, total_distance_km, total_duration_min,
                segments_json, geojson_path)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                route_text,
                year,
                note,
                total_distance_km,
                total_duration_min,
                json.dumps(segments, ensure_ascii=False),
                geojson_path,
            ),
        )
        return cur.lastrowid


def list_routes(limit: int = 1000) -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM routes ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(r) for r in rows]


def get_route(route_id: int) -> Optional[dict]:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM routes WHERE id = ?", (route_id,)).fetchone()
    return dict(row) if row else None


def all_segments() -> list[dict]:
    """Flatten every saved route's segments (for global analytics)."""
    out = []
    for r in list_routes():
        try:
            segs = json.loads(r["segments_json"])
        except (TypeError, json.JSONDecodeError):
            continue
        for s in segs:
            s = dict(s)
            s["route_id"] = r["id"]
            s["year"] = r["year"]
            out.append(s)
    return out
