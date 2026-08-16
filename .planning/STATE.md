# Project State

**Project:** Travel Visualizer

## Current Position

- **Milestone:** M1 — MVP (single route + upload + analytics)
- **Phase:** P1 — Core build
- **Status:** done
- **Current task:** n/a
- **Last updated:** 2026-08-16 12:30

## Active Decisions

- [x] D1: HERE API optional; Nominatim + haversine/geodesic as default fallback — implemented
- [x] D2: Frontend vanilla JS + MapLibre GL JS (no build step, no React) — implemented
- [x] D3: SQLite via stdlib sqlite3 (no SQLAlchemy) — implemented
- [x] D4: Transport hint via inline `Город [тип]` annotation, keyword detection, default car — implemented

## Blockers

(нет)

## Progress

- [x] Phase 1: backend (transport/geo/geocoding/routing/parsing/analytics/db/pipeline) — shipped 2026-08-16
- [x] Phase 2: FastAPI app + routers (animate/upload/stats/history/map) — shipped 2026-08-16
- [x] Phase 3: frontend (index + map + animation + charts) — shipped 2026-08-16
- [x] Phase 4: tests (30 passing) + end-to-end demo route — shipped 2026-08-16

## Recent Activity

- 2026-08-16 12:22 — verify: end-to-end demo «СПб – Москва – Пекин» = 6425.55 км, upload 5 маршрутов из sample CSV
- 2026-08-16 12:15 — test: 30 passed (fixed hyphenated-city split bug in transport.py)
- 2026-08-16 12:07 — state: project initialized, vibe-tracking started
