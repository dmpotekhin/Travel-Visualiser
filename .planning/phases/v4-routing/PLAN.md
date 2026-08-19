# M4 — Routing & Map Enhancement (v4-routing)

**Branch:** feature/routing-providers
**Type:** architecture-change
**Date:** 2026-08-19

## Summary

Route calculation becomes a replaceable backend service. A provider abstraction
(`RoutingProvider`) sits between the pipeline and external routing APIs
(HERE / OSRM / GraphHopper) with a deterministic great-circle fallback. The
frontend keeps receiving provider-independent GeoJSON; per-transport dash
styles + legend make transport types visually distinct. Existing API, HERE
integration and animation engine stay backward compatible.

## Context (analysis results)

- FastAPI + vanilla JS + MapLibre GL JS, no build step, SQLite via stdlib.
- `backend/routing.py` — HERE Routing v8 + Matrix fallback + haversine/geodesic
  fallback, hard-wired to HERE. Transport keys: `air rail car bus ferry bike foot`.
- `backend/pipeline.py` — parse → geocode → route → geojson → persist; used by
  `/animate`, `/upload`, studio (`preview_route`, `preview_track`).
- `backend/geojson.py` — FeatureCollection, per-segment properties already include
  `transport/color/emoji/distance_km/duration_min`.
- `frontend/js/map.js` — animation engine already segment-agnostic (flattened
  coords + cumulative distances, marker emoji switch via `segmentIndexAt`).
  Per-segment color already data-driven (`['get','color']`).
- Baseline: 59 tests green. HERE optional (no key → Nominatim + great-circle).

## Design decisions (D1…)

- D1: `TransportType(str, Enum)` — members `CAR="car" TRAIN="rail" PLANE="air"
  WALK="foot" BICYCLE="bike" BUS="bus" FERRY="ferry"`. Enum values = existing
  internal keys → stored JSON / GeoJSON / frontend untouched (backward compat).
  `coerce_transport()` accepts uppercase/English aliases ("CAR", "TRAIN",
  "PLANE", "WALK", "BICYCLE", "BIKE") for the new API.
- D2: `backend/routing.py` → `backend/routing/` package:
  `base.py` (RouteResult + RoutingProvider ABC + error hierarchy),
  `here.py`, `osrm.py`, `graphhopper.py`, `fallback.py`
  (GreatCircleRoutingProvider), `factory.py`, `__init__.py` re-exports
  `route_segment` (pipeline import `from . import routing` keeps working).
- D3: Provider chain built from config; priority = provider order
  (`ROUTING_PROVIDER_ORDER`, default auto = HERE → OSRM → GRAPHHOPPER →
  GREAT_CIRCLE). `get_provider_for(transport)` picks the first configured
  provider that supports the transport. Per-segment: try each candidate in
  order, log the reason on failure, use first success; ultimate fallback =
  great-circle (always available, no network). `ROUTING_FALLBACK_ENABLED=false`
  → propagate the error instead of silent fallback.
- D4: HERE keeps current semantics exactly: used for `car bus bike foot ferry`,
  skipped for `air rail` (as today); polyline decode + Matrix fallback moved
  verbatim into `routing/here.py`.
- D5: OSRM: `GET {base}/route/v1/{profile}/{lon},{lat};{lon},{lat}?overview=full&geometries=geojson`.
  profiles: car→driving, bike→cycling, foot→walking. Enabled when
  `OSRM_BASE_URL` set (default `https://router.project-osrm.org`).
- D6: GraphHopper: `GET {base}/route?point=lat,lon&point=lat,lon&vehicle=…&points_encoded=false&key=…`.
  Same HTTP+JSON pattern → implemented (not deferred). Enabled when
  `GRAPHHOPPER_API_KEY` set; base `GRAPHHOPPER_BASE_URL` (default
  `https://graphhopper.com/api/1`).
- D7: No transport has a rail/air road provider → `TRAIN`/`PLANE` fall through
  to great-circle (documented; same as today for rail, air already was).
- D8: New endpoint `POST /api/routes` (no persistence — preview semantics):
  `{"segments":[{"from","to","transport"?}],"year"?,"note"?}` → same shape as
  pipeline output + `provider`/`provider_fallback` per segment. Plus
  `GET /api/providers` diagnostics (configured providers + supported transports).
- D9: GeoJSON properties gain `provider` (additive, non-breaking).
- D10: Frontend: data-driven `line-dasharray` on route-transport layer via match
  expression (car/bus/ferry solid, train dashed, walk dotted, bike dash-dot,
  air solid-arc). Small legend on map page. Segment card shows provider.
  Animation engine untouched.

## Non-goals

- No rewrite, no MapLibre replacement, no HERE removal, no frontend build step.
- No live-API calls in automated tests (all httpx mocked).
- No secrets in frontend.

## Tasks

### T1 (P2) Transport model + routing package skeleton
- `backend/transport.py`: add `TransportType`, `coerce_transport()`, canonical aliases.
- `backend/routing/` package: `base.py` (RouteResult, RoutingProvider ABC,
  RoutingError/ProviderConfigurationError/ProviderUnavailableError/
  ProviderNoRouteError/UnsupportedTransportError), `fallback.py`
  (GreatCircleRoutingProvider), `__init__.py` with compat `route_segment`.
- Tests: coercion, selection, great-circle conversion. Commit.

### T2 (P3) HERE behind the abstraction
- `routing/here.py`: move `_HERE_MODE`, `_here_route`, `_here_matrix`; keep
  decode + matrix fallback behavior identical.
- `routing/factory.py`: chain building, `route_segment` compat wrapper using
  new chain; config env: `ROUTING_PROVIDER_ORDER`, `ROUTING_FALLBACK_ENABLED`.
- Segments get `provider` + `provider_fallback` (pipeline enrichment).
- Tests: HERE parse, HERE failure → fallback, chain order. Commit.

### T3 (P4) OSRM provider
- `routing/osrm.py`: request build, response parse, GeoJSON geometry conversion.
- Config: `OSRM_BASE_URL`.
- Tests: mocked OSRM success (car/bike/foot), timeout/500 → RoutingError. Commit.

### T4 (P5) GraphHopper + fallback wiring
- `routing/graphhopper.py`: request build, parse.
- Config: `GRAPHHOPPER_API_KEY`, `GRAPHHOPPER_BASE_URL`.
- Fallback-disabled mode + tests (provider failure propagates). Commit.

### T5 (P6) GeoJSON/API
- `geojson.py`: add `provider` to properties.
- New router `backend/routers/routes.py`: `POST /api/routes`, `GET /api/providers`;
  schemas in `schemas.py` (`SegmentRequest`, `RoutesRequest`, `RoutesResponse`).
- Tests: happy path, unknown city 422, bad transport 422, empty segments 422,
  provider diagnostics. Commit.

### T6 (P7+P8) Frontend + animation verification
- `map.js`: dash style match expression, legend wiring, provider in segment card.
- `map.html` + `style.css`: legend markup/styles.
- Verify multi-segment animation (Moscow→Berlin car, Berlin→Paris train,
  Paris→Madrid plane) via browser smoke; animation engine unchanged.
- Commit.

### T7 (P9) Test sweep + regression
- Full `pytest -q` green; count new tests. Commit if fixes.

### T8 (P10) Docs
- `.env.example`: OSRM/GRAPHHOPPER/ROUTING_* vars.
- README: architecture diagram (Mermaid), providers, transports, env table,
  fallback behaviour, API examples, limitations.
- ADR: `docs/adr/0001-routing-provider-abstraction.md`.
- Update STATE.md (phase done). Commit.

## Testing strategy

- pytest + monkeypatch (project convention, no new deps; httpx.get patched per
  provider module).
- No live external calls in tests.
- Browser smoke via Playwright at T6 (animation, legend, style switch).

## Risks

- Breaking pipeline import (`routing.py` → package) — mitigated by `__init__.py`
  re-export; all callers use `from . import routing`.
- Backward compat of stored DB rows (legacy transport keys) — enum values are
  the legacy keys, so rows remain valid.
- OSRM public server rate limits — only used when configured; fallback covers.
