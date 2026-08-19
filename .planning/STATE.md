# Project State

**Project:** Travel Visualizer

## Current Position

- **Milestone:** M3 — Video constructor (wizard + hybrid 2D/3D + export settings)
- **Phase:** P3 — Studio (wizard + CesiumJS + aspect-ratio export)
- **Status:** verify
- **Current task:** docs + final verification done (59 tests, browser smoke green)
- **Last updated:** 2026-08-17

## Active Decisions

- [x] D1: HERE API optional; Nominatim + haversine/geodesic fallback
- [x] D2: Frontend vanilla JS + MapLibre GL JS (no build step)
- [x] D3: SQLite via stdlib sqlite3
- [x] D4: Transport hint via inline annotation + keyword detection
- [x] D5: Video/GIF export fully client-side; WebM native, MP4 via
      native-or-WebCodecs+mp4-muxer, GIF via gif.js
- [x] D6: Custom cartoon style = self-hosted OpenFreeMap vector style
- [x] D7: Export libs vendored in frontend/vendor/ (no CDN at export time)
- [x] D8: New pages (wizard/studio) additive; legacy paths unchanged
- [x] D9: Project handoff wizard→studio via localStorage (photos stay client-side)
- [x] D10: CesiumJS via CDN, OSM imagery, flat terrain; Ion token optional
- [x] D11: Single shared state + one RAF loop for 2D/3D sync
- [x] D12: GPX/KML via stdlib ElementTree, GeoJSON via json (no native deps)
- [x] D13: AI parsing optional (DeepSeek) + deterministic NL fallback
- [x] D14: Tier stub (Free 3/mo + watermark, Pro unlimited) client-side
- [x] D15: Aspect ratio 9:16/16:9/1:1 + 4K in export

## Blockers

(нет)

## Progress

- [x] Phase 1: backend + routers + frontend + tests (M1, 30 passing)
- [x] Phase 2: gradient + running light + marker + trail + popups + follow
- [x] Phase 2: style switcher + cartoon style
- [x] Phase 2: WebM / MP4 / GIF export (verified via Playwright)
- [x] Phase 3: wizard (6-step) + hybrid 2D/3D + aspect-ratio export — verified

## Recent Activity

- 2026-08-17 — M3 verified: 59 tests green; browser smoke (wizard parse →
      studio 2D render → 3D Cesium switch → export modal) all pass with 0 JS
      errors; Cesium `baseLayer:false` removes the 401-without-token noise.
- 2026-08-17 — M3 kickoff: PLAN.md written; baseline 30 tests green
- 2026-08-16 23:30 — M2 verified end-to-end (Playwright)
- 2026-08-16 12:30 — M1 shipped (pushed to origin/main)
