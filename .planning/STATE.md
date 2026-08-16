# Project State

**Project:** Travel Visualizer

## Current Position

- **Milestone:** M2 — Cinematic visuals + style switcher + video export
- **Phase:** P2 — Visual upgrade
- **Status:** done
- **Current task:** n/a
- **Last updated:** 2026-08-16 23:30

## Active Decisions

- [x] D1: HERE API optional; Nominatim + haversine/geodesic fallback
- [x] D2: Frontend vanilla JS + MapLibre GL JS (no build step)
- [x] D3: SQLite via stdlib sqlite3
- [x] D4: Transport hint via inline annotation + keyword detection
- [x] D5: Video/GIF export fully client-side; WebM native, MP4 via
      native-or-WebCodecs+mp4-muxer, GIF via gif.js
- [x] D6: Custom cartoon style = self-hosted OpenFreeMap vector style;
      line-gradient via GeoJSON source `lineMetrics: true`
- [x] D7: Export libs (mp4-muxer, gif.js+worker) vendored in frontend/vendor/
      (no CDN at export time); Positron/Dark Matter use Carto (no MapTiler key)

## Blockers

(нет)

## Progress

- [x] Phase 1: backend + routers + frontend + tests (M1, 30 passing)
- [x] Phase 2: gradient line + running light + transport marker + trail +
      popups + camera follow + start/finish
- [x] Phase 2: style switcher (5 styles) + custom cartoon style
- [x] Phase 2: WebM / MP4 / GIF export (verified: real 2MB WebM, 5MB MP4,
      4.5MB GIF produced in Playwright)
- [x] Phase 2: backend segment enrichment (emoji/transport_name/color)

## Recent Activity

- 2026-08-16 23:30 — M2 verified end-to-end (Playwright): demo route renders,
      style switch round-trip, WebM/MP4/GIF export all produce files
- 2026-08-16 22:00 — M2 kickoff: plan + backend emoji props
- 2026-08-16 12:30 — M1 shipped (pushed to origin/main)
