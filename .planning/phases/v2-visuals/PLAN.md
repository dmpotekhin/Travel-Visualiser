# Plan: Cinematic visual upgrade (v2)

## Scope (by spec sections)
1. Map visual FX (frontend): gradient line (1a), running dashes (1b),
   transport-icon marker with rotation (1c), fading trail (1d), hover/auto
   info popups (1e), camera follow (1f), start/finish markers (1g).
2. Map style switcher + custom cartoon style (2).
3. Client-side video/GIF export (3).
4. Analytics integration unchanged — verify (4).
5. Extend, don't rewrite existing backend (5).

## Backend (minimal)
- transport.py: add EMOJI map + emoji() helper.
- geojson.py: emit `emoji` + `icon_key` on LineString feature properties.

## Frontend
- map.html: new overlay controls (style select, speed slider, follow toggle,
  sound toggle, export button) + export modal; lazy-load mp4-muxer + gif.js.
- map.js: rewrite — gradient line (lineMetrics source opt + line-gradient),
  animated dasharray layer, DOM transport marker (emoji + rotate), trail
  source, popups, camera follow (lerp), start/finish markers, style switcher,
  speed slider, synthesized sound.
- export.js: new module — MediaRecorder (WebM/MP4-native), WebCodecs+mp4-muxer
  (MP4 on Chrome), gif.js (GIF), optional audio mix, watermark + titles.
- style.css: styles for controls, modal, marker, progress.
- styles/cartoon.json: custom cartoon vector style (OpenFreeMap tiles/glyphs).

## Verification
- pytest (backend still green).
- Playwright: load demo route «СПб – Москва – Пекин», assert no console errors,
  style switch works, animation runs, export produces a downloadable file.
