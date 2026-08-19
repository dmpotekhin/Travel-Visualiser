# Plan: Video Constructor for Travel Bloggers (v3 Studio)

## Goal
Turn Travel Visualizer into a mult.dev-style route-video constructor: multi-step
wizard (route input → transport → photos → style → video settings → export) and a
hybrid 2D (MapLibre) / 3D (CesiumJS) animation/export studio, while keeping all
existing v1/v2 functionality intact.

## Design decisions
- D1: **New pages, not rewrites.** `wizard.html` (constructor) and `studio.html`
  (hybrid viewer + export) are additive. Legacy `/`, `/animate`, `/upload`,
  `/map/{id}` untouched. Backward compatible.
- D2: **Project handoff via localStorage.** The wizard builds a project object
  (points + segments with geometry + transport + photos(base64) + style + video
  settings) and passes it to the studio through `localStorage` under
  `travel-studio-project`. No server round-trip needed for edits; photos stay
  client-side per spec.
- D3: **CesiumJS via CDN** (jsdelivr), OSM imagery (no Ion token required), flat
  ellipsoid terrain by default. Real terrain + other imagery optional via
  `CESIUM_ION_TOKEN` (injected into studio page). Graceful degradation: if Cesium
  fails to load, 2D keeps working.
- D4: **Single shared state + one RAF loop.** `Studio.state.frac` is the source of
  truth; `mapView.render(frac)` and `globeView.render(frac)` both read it, so a
  2D↔3D switch at any moment shows the same animation position.
- D5: **Backend parsing is format-agnostic and dependency-light.** GPX/KML parsed
  with stdlib ElementTree (`{*}t` namespace wildcard), GeoJSON with stdlib json —
  no gpxpy/togeojson native deps. Track coordinates become segments directly
  (no city geocoding), transport defaulted by distance heuristic.
- D6: **AI parsing optional + deterministic fallback.** DeepSeek via httpx
  (OpenAI-compatible `/chat/completions`) only if `DEEPSEEK_API_KEY` set; otherwise
  a heuristic NL→route-string normalizer (из X в Y, запятые/«потом»/«затем»).
- D7: **Tier = client-side stub.** Free: 3 exports/month + forced watermark;
  Pro: unlimited + no watermark. Upgrade button is a placeholder (Stripe/YooKassa
  out of scope). Enforced in `localStorage`.
- D8: **Aspect ratio (9:16 / 16:9 / 1:1) + 4K** added to export; render is cover-
  cropped onto the target canvas (existing drawComposite pattern extended).

## Backend (additive)
- `backend/track.py`: `parse_gpx`, `parse_kml`, `parse_geojson`,
  `parse_gmaps_url`, `coords_to_segments`, plus `simplify()` (Douglas-Peucker).
- `backend/ai.py`: `parse_natural_language(text)` → route string (DeepSeek or
  heuristic fallback).
- `backend/pipeline.py`: add `preview_route(route_text)` (no DB save) and
  `route_from_coords(coords, transport, ...)`.
- `backend/routers/studio.py`: `POST /api/parse` (kind: text|nl|gmaps) and
  `POST /api/parse-file` (multipart gpx/kml/geojson) → normalized route preview.
- `backend/config.py` + `.env.example`: `DEEPSEEK_API_KEY`, `DEEPSEEK_MODEL`,
  `CESIUM_ION_TOKEN`.
- `backend/app.py`: register studio router (before static mount).

## Frontend (additive)
- `wizard.html` + `js/wizard.js`: 6-step wizard; templates (Кинематографичный /
  Быстрый / Для блога / Минимал); transport per segment; photos+descriptions per
  point (base64, ≤5); style preview (2D + 3D); video settings; builds project →
  localStorage → `/studio`.
- `studio.html` + `js/studio.js`: shared state + RAF loop; MapLibre 2D + Cesium 3D
  with 2D/3D toggle; play/pause/restart/speed; photo popup on point arrival;
  endpoint markers; style application.
- `js/studio-export.js`: aspect ratio + quality (HD/FHD/4K) + watermark/titles/
  music + tier limits; reuse mp4-muxer/gif.js vendor + drawComposite approach.
- `css/studio.css`: wizard + studio styling (additive).
- `index.html`: link to the constructor.

## Verification
- pytest: new track/ai/studio tests + existing 30 stay green.
- Boot smoke: server starts, `/api/parse`, `/api/parse-file`, `/studio`,
  `/wizard` respond.
- Browser smoke: wizard and studio pages load without JS errors (best-effort;
  WebGL/Cesium may be limited in headless).
