/* Map page: cinematic route visualization with MapLibre GL JS. */
(function () {
  'use strict';

  const EQUATOR = 40075;
  const MOON = 384400;

  const STYLES = [
    { id: 'cartoon',   name: 'Мультяшный',   url: '/styles/cartoon.json' },
    { id: 'voyager',   name: 'Voyager',      url: 'https://basemaps.cartocdn.com/gl/voyager-gl-style/style.json' },
    { id: 'liberty',   name: 'Liberty',      url: 'https://tiles.openfreemap.org/styles/liberty' },
    { id: 'positron',  name: 'Positron',     url: 'https://basemaps.cartocdn.com/gl/positron-gl-style/style.json' },
    { id: 'dark',      name: 'Dark Matter',  url: 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json' },
  ];

  const OSM_RASTER_STYLE = {
    version: 8,
    sources: { osm: { type: 'raster', tiles: ['https://tile.openstreetmap.org/{z}/{x}/{y}.png'], tileSize: 256, attribution: '© OpenStreetMap contributors' } },
    layers: [{ id: 'osm', type: 'raster', source: 'osm' }],
  };

  // ----- helpers -----------------------------------------------------------
  function formatDuration(min) {
    if (min === null || min === undefined) return '—';
    const d = Math.floor(min / 1440);
    const h = Math.floor((min % 1440) / 60);
    const m = Math.round(min % 60);
    let out = '';
    if (d) out += d + ' д ';
    if (h) out += h + ' ч ';
    out += m + ' мин';
    return out.trim();
  }

  function flattenCoords(geojson) {
    const coords = [];
    for (const f of geojson.features) {
      if (f.geometry.type === 'LineString') coords.push(...f.geometry.coordinates);
    }
    return coords;
  }

  // merge segment coordinates into one LineString, deduping shared endpoints
  function mergedLineCoords(coords) {
    const out = [];
    for (const c of coords) {
      const last = out[out.length - 1];
      if (last && last[0] === c[0] && last[1] === c[1]) continue;
      out.push(c);
    }
    return out;
  }

  function distKm(a, b) {
    const R = 6371;
    const dLat = (b[1] - a[1]) * Math.PI / 180;
    const dLng = (b[0] - a[0]) * Math.PI / 180;
    const la1 = a[1] * Math.PI / 180, la2 = b[1] * Math.PI / 180;
    const h = Math.sin(dLat / 2) ** 2 + Math.cos(la1) * Math.cos(la2) * Math.sin(dLng / 2) ** 2;
    return 2 * R * Math.asin(Math.sqrt(h));
  }

  function cumLengths(coords) {
    const cum = [0];
    for (let i = 1; i < coords.length; i++) cum.push(cum[i - 1] + distKm(coords[i - 1], coords[i]));
    return cum;
  }

  function interpolate(coords, cum, frac) {
    const total = cum[cum.length - 1];
    if (!coords.length) return null;
    if (total <= 0) return coords[0];
    const target = frac * total;
    let i = 1;
    while (i < cum.length && cum[i] < target) i++;
    if (i >= cum.length) return coords[coords.length - 1];
    const a = coords[i - 1], b = coords[i];
    const seg = cum[i] - cum[i - 1] || 1;
    const t = (target - cum[i - 1]) / seg;
    return [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t];
  }

  function bearingDeg(a, b) {
    if (!a || !b) return 0;
    const dLng = (b[0] - a[0]) * Math.PI / 180;
    const la1 = a[1] * Math.PI / 180, la2 = b[1] * Math.PI / 180;
    const y = Math.sin(dLng) * Math.cos(la2);
    const x = Math.cos(la1) * Math.sin(la2) - Math.sin(la1) * Math.cos(la2) * Math.cos(dLng);
    return (Math.atan2(y, x) * 180 / Math.PI + 360) % 360;
  }

  const $ = (id) => document.getElementById(id);

  // ----- build city "stops" for popups / segment info ----------------------
  function buildStops(route) {
    const segs = route.segments;
    const stops = []; // { name, coord, cumKm, nextKm, nextDur, emoji, transportName }
    const pointByCity = {};
    for (const f of route.geojson.features) {
      if (f.geometry.type === 'Point') pointByCity[f.properties.city] = f.geometry.coordinates;
    }
    let cum = 0;
    segs.forEach((s, i) => {
      stops.push({
        name: s.from, coord: pointByCity[s.from],
        cumKm: cum, nextKm: s.distance_km, nextDur: s.duration_min,
        emoji: route.geojson.features.find((f) => f.properties && f.properties.from === s.from && f.properties.to === s.to)?.properties?.emoji || s.emoji,
        transportName: s.transport_name,
      });
      cum += s.distance_km;
      if (i === segs.length - 1) {
        stops.push({ name: s.to, coord: pointByCity[s.to], cumKm: cum, nextKm: null, nextDur: null, emoji: null, transportName: null });
      }
    });
    return stops;
  }

  // ----- render info panel --------------------------------------------------
  function renderInfo(route) {
    $('r-title').textContent = route.route_text;

    const byT = {};
    for (const f of route.geojson.features) {
      if (f.geometry.type !== 'LineString') continue;
      const p = f.properties;
      byT[p.transport] = byT[p.transport] || { km: 0, name: p.transport_name, color: p.color, emoji: p.emoji };
      byT[p.transport].km += p.distance_km;
    }

    const totalKm = route.total_distance_km;
    const legend = $('legend');
    legend.innerHTML = '';
    for (const t of Object.keys(byT)) {
      const b = byT[t];
      const pct = totalKm ? (b.km / totalKm * 100).toFixed(1) : 0;
      const item = document.createElement('span');
      item.className = 'item';
      item.innerHTML = '<span class="emoji">' + b.emoji + '</span>' +
        b.name + ' · ' + Math.round(b.km).toLocaleString('ru-RU') + ' км (' + pct + '%)';
      legend.appendChild(item);
    }

    const rows = [
      ['Всего', Math.round(totalKm).toLocaleString('ru-RU') + ' км'],
      ['Экваторов', (totalKm / EQUATOR).toFixed(2) + '×'],
      ['До Луны', (totalKm / MOON * 100).toFixed(2) + '% пути'],
      ['Сегментов', String(route.segments.length)],
      ['Время в пути', formatDuration(route.total_duration_min)],
    ];
    const info = $('info-rows');
    info.innerHTML = '';
    for (const [k, v] of rows) {
      const row = document.createElement('div');
      row.className = 'info-row';
      row.innerHTML = '<span class="k">' + k + '</span><span class="v">' + v + '</span>';
      info.appendChild(row);
    }
  }

  // ----- gradient + pulse paint helpers -------------------------------------
  function gradientPaint() {
    return {
      'line-color': ['interpolate', ['linear'], ['line-progress'],
        0, '#3b82f6', 0.5, '#8b5cf6', 1, '#ef4444'],
      'line-width': 5,
      'line-opacity': 0.95,
      'line-blur': 0.5,
    };
  }
  function glowPaint() {
    return {
      'line-color': ['interpolate', ['linear'], ['line-progress'],
        0, '#3b82f6', 0.5, '#8b5cf6', 1, '#ef4444'],
      'line-width': 11,
      'line-opacity': 0.18,
      'line-blur': 1.5,
    };
  }

  // moving bright "firefly" along the line, driven by line-gradient stops
  function pulsePaint(frac) {
    const w = 0.05;
    const head = Math.min(Math.max(frac, 0), 1);
    const stops = [[0, 'rgba(255,255,255,0)']];
    const a = Math.max(0, head - w);
    const b = Math.min(1, head + w);
    if (a > 0) stops.push([a, 'rgba(255,255,255,0)']);
    stops.push([head, 'rgba(255,255,255,0.95)']);
    if (b < 1) stops.push([b, 'rgba(255,255,255,0)']);
    stops.push([1, 'rgba(255,255,255,0)']);
    // enforce strictly increasing positions
    const clean = [];
    let last = -1;
    for (const [t, c] of stops) {
      const tt = Math.min(Math.max(t, 0), 1);
      if (tt <= last) continue;
      clean.push(tt, c);
      last = tt;
    }
    return { 'line-color': ['interpolate', ['linear'], ['line-progress'], ...clean], 'line-width': 6, 'line-opacity': 0.9 };
  }

  // ==========================================================================
  // main()
  // ==========================================================================
  async function main() {
    const cfg = window.ROUTE_CONFIG;
    let route;
    try {
      if (cfg.inline) route = cfg.inline;
      else if (cfg.fetch_id) {
        const r = await fetch('/api/geojson/' + cfg.fetch_id);
        if (!r.ok) throw new Error('Маршрут не найден');
        route = await r.json();
      } else throw new Error('Нет данных маршрута');
    } catch (e) {
      $('overlay').innerHTML = '<a class="back btn-link" href="/">← Назад</a><p>' + e.message + '</p>';
      return;
    }

    renderInfo(route);
    const stops = buildStops(route);
    const coords = flattenCoords(route.geojson);
    const merged = mergedLineCoords(coords);
    const cum = cumLengths(coords);

    const map = new maplibregl.Map({
      container: 'map',
      style: STYLES[0].url,
      center: [30, 50],
      zoom: 2,
      canvasContextAttributes: { preserveDrawingBuffer: true, antialias: true },
    });
    map.addControl(new maplibregl.NavigationControl(), 'top-right');

    // ----- state ------------------------------------------------------------
    const state = {
      playing: true,
      frac: 0,
      speedFactor: 1,
      follow: true,
      sound: true,
      baseFrac: 0,
      startTime: 0,
      DURATION: 30000,
      trail: [],        // traveled coordinates (for trail layer)
      currentSeg: -1,
    };

    // ----- sound (synthesized, no assets) ----------------------------------
    let audioCtx = null;
    function ensureAudio() {
      if (!audioCtx) {
        try { audioCtx = new (window.AudioContext || window.webkitAudioContext)(); } catch (e) { audioCtx = null; }
      }
      if (audioCtx && audioCtx.state === 'suspended') audioCtx.resume();
      return audioCtx;
    }
    function tone(freq, dur, type, gainVal) {
      if (!state.sound) return;
      const ctx = ensureAudio();
      if (!ctx) return;
      const t = ctx.currentTime;
      const osc = ctx.createOscillator();
      const g = ctx.createGain();
      osc.type = type || 'sine';
      osc.frequency.setValueAtTime(freq, t);
      g.gain.setValueAtTime(0.0001, t);
      g.gain.exponentialRampToValueAtTime(gainVal || 0.08, t + 0.02);
      g.gain.exponentialRampToValueAtTime(0.0001, t + dur);
      osc.connect(g).connect(ctx.destination);
      osc.start(t); osc.stop(t + dur + 0.05);
    }
    function whoosh() {
      if (!state.sound) return;
      const ctx = ensureAudio();
      if (!ctx) return;
      const t = ctx.currentTime;
      const len = 0.6;
      const buf = ctx.createBuffer(1, ctx.sampleRate * len, ctx.sampleRate);
      const data = buf.getChannelData(0);
      for (let i = 0; i < data.length; i++) data[i] = (Math.random() * 2 - 1) * (1 - i / data.length);
      const src = ctx.createBufferSource(); src.buffer = buf;
      const filter = ctx.createBiquadFilter(); filter.type = 'bandpass';
      filter.frequency.setValueAtTime(200, t);
      filter.frequency.exponentialRampToValueAtTime(1600, t + len);
      const g = ctx.createGain(); g.gain.value = 0.15;
      src.connect(filter).connect(g).connect(ctx.destination);
      src.start(t);
    }

    // ----- DOM marker -------------------------------------------------------
    const markerEl = document.createElement('div');
    markerEl.className = 'travel-marker';
    markerEl.innerHTML = '<span class="travel-marker-icon">🚗</span><span class="travel-marker-shadow"></span>';
    const marker = new maplibregl.Marker({ element: markerEl, anchor: 'center' }).setLngLat(coords[0]).addTo(map);

    function setMarkerIcon(transport) {
      markerEl.querySelector('.travel-marker-icon').textContent = transport.emoji;
    }
    function setMarkerRotation(deg) {
      markerEl.querySelector('.travel-marker-icon').style.transform = 'rotate(' + deg + 'deg)';
    }

    // start / finish DOM markers
    function addEndpointMarkers() {
      const start = coords[0];
      const end = coords[coords.length - 1];
      const mk = (label, iconCls) => {
        const el = document.createElement('div');
        el.className = 'endpoint';
        el.innerHTML = '<span class="endpoint-flag ' + iconCls + '"></span><span class="endpoint-label">' + label + '</span>';
        return el;
      };
      new maplibregl.Marker({ element: mk('Старт', 'start'), anchor: 'bottom' }).setLngLat(start).addTo(map);
      new maplibregl.Marker({ element: mk('Финиш', 'finish'), anchor: 'bottom' }).setLngLat(end).addTo(map);
    }

    // ----- sources & layers -------------------------------------------------
    function addRouteLayers() {
      if (map.getSource('route')) return;

      map.addSource('route', { type: 'geojson', data: route.geojson, lineMetrics: true });
      map.addSource('route-gradient', {
        type: 'geojson',
        lineMetrics: true,
        data: { type: 'Feature', properties: {}, geometry: { type: 'LineString', coordinates: merged } },
      });
      map.addSource('route-trail', { type: 'geojson', lineMetrics: true, data: { type: 'Feature', properties: {}, geometry: { type: 'LineString', coordinates: [] } } });

      // gradient base
      map.addLayer({ id: 'route-glow', type: 'line', source: 'route-gradient',
        layout: { 'line-join': 'round', 'line-cap': 'round' }, paint: glowPaint() });
      map.addLayer({ id: 'route-gradient', type: 'line', source: 'route-gradient',
        layout: { 'line-join': 'round', 'line-cap': 'round' }, paint: gradientPaint() });

      // per-segment transport tint
      map.addLayer({ id: 'route-transport', type: 'line', source: 'route', filter: ['==', '$type', 'LineString'],
        layout: { 'line-join': 'round', 'line-cap': 'round' },
        paint: { 'line-color': ['get', 'color'], 'line-width': 1.6, 'line-opacity': 0.55 } });

      // static dashed texture + moving firefly
      map.addLayer({ id: 'route-dashes', type: 'line', source: 'route', filter: ['==', '$type', 'LineString'],
        layout: { 'line-join': 'round', 'line-cap': 'round' },
        paint: { 'line-color': '#ffffff', 'line-width': 4, 'line-opacity': 0.28, 'line-dasharray': [1.5, 2.5] } });
      map.addLayer({ id: 'route-pulse', type: 'line', source: 'route-gradient',
        layout: { 'line-join': 'round', 'line-cap': 'round' }, paint: pulsePaint(0) });

      // trail (traveled portion)
      map.addLayer({ id: 'route-trail-glow', type: 'line', source: 'route-trail',
        layout: { 'line-join': 'round', 'line-cap': 'round' },
        paint: { 'line-color': '#ffffff', 'line-width': 9, 'line-opacity': 0.18 } });
      map.addLayer({ id: 'route-trail', type: 'line', source: 'route-trail',
        layout: { 'line-join': 'round', 'line-cap': 'round' },
        paint: { 'line-color': '#ffffff', 'line-width': 4.5, 'line-opacity': 0.95 } });

      // city dots + labels
      map.addLayer({ id: 'city-dots', type: 'circle', source: 'route', filter: ['==', '$type', 'Point'],
        paint: { 'circle-radius': 5, 'circle-color': '#ffffff', 'circle-stroke-color': '#1f2937', 'circle-stroke-width': 2 } });
      map.addLayer({ id: 'city-labels', type: 'symbol', source: 'route', filter: ['==', '$type', 'Point'],
        layout: { 'text-field': ['get', 'city'], 'text-font': ['Noto Sans Regular'], 'text-size': 13, 'text-offset': [0, 1.5], 'text-anchor': 'top' },
        paint: { 'text-color': '#ffffff', 'text-halo-color': '#000000', 'text-halo-width': 1.5 } });
    }

    // ----- hover popups on cities ------------------------------------------
    const popup = new maplibregl.Popup({ closeButton: false, closeOnClick: false, offset: 12 });
    function bindCityPopups() {
      map.on('mouseenter', 'city-dots', (e) => {
        map.getCanvas().style.cursor = 'pointer';
        const name = e.features[0].properties.city;
        const stop = stops.find((s) => s.name === name);
        if (!stop) return;
        let html = '<strong>' + name + '</strong>';
        if (stop.nextKm != null) {
          html += '<br><span class="popup-row">До следующей: ' + Math.round(stop.nextKm).toLocaleString('ru-RU') + ' км</span>';
          html += '<br><span class="popup-row">В пути: ' + formatDuration(stop.nextDur) + '</span>';
        }
        html += '<br><span class="popup-row">Нарастающим: ' + Math.round(stop.cumKm).toLocaleString('ru-RU') + ' км</span>';
        popup.setLngLat(stop.coord).setHTML(html).addTo(map);
      });
      map.on('mouseleave', 'city-dots', () => {
        map.getCanvas().style.cursor = '';
        popup.remove();
      });
    }

    // transient segment card (fades)
    let segTimer = null;
    const segCard = document.createElement('div');
    segCard.className = 'segment-card hidden';
    document.body.appendChild(segCard);
    function showSegmentCard(text) {
      segCard.innerHTML = text;
      segCard.classList.remove('hidden');
      clearTimeout(segTimer);
      segTimer = setTimeout(() => segCard.classList.add('hidden'), 3800);
    }

    function segmentIndexAt(frac) {
      // fraction of total length -> which segment
      const totalKm = route.total_distance_km || 1;
      const target = frac * totalKm;
      let acc = 0;
      for (let i = 0; i < route.segments.length; i++) {
        acc += route.segments[i].distance_km;
        if (target < acc) return i;
      }
      return route.segments.length - 1;
    }

    // ----- camera follow ----------------------------------------------------
    function followCamera(pos) {
      if (!state.follow) return;
      const cur = map.getCenter();
      const k = 0.06;
      map.jumpTo({ center: [cur.lng + (pos[0] - cur.lng) * k, cur.lat + (pos[1] - cur.lat) * k] });
    }

    // ----- core update ------------------------------------------------------
    function update(frac) {
      state.frac = frac;
      const pos = interpolate(coords, cum, frac);
      if (!pos) return;

      // marker position + bearing
      const ahead = interpolate(coords, cum, Math.min(1, frac + 0.004));
      marker.setLngLat(pos);
      setMarkerRotation(bearingDeg(pos, ahead));

      // segment / transport icon
      const si = segmentIndexAt(frac);
      if (si !== state.currentSeg) {
        state.currentSeg = si;
        const s = route.segments[si];
        setMarkerIcon(s);
        showSegmentCard(s.emoji + ' ' + s.transport_name + ' · ' + s.from + ' → ' + s.to +
          ' · ' + Math.round(s.distance_km).toLocaleString('ru-RU') + ' км');
        if (state.playing) tone(660, 0.12, 'sine', 0.05);
      }

      // trail: append traveled point
      const lastTrail = state.trail[state.trail.length - 1];
      if (!lastTrail || lastTrail[0] !== pos[0] || lastTrail[1] !== pos[1]) state.trail.push([pos[0], pos[1]]);
      if (map.getSource('route-trail')) {
        map.getSource('route-trail').setData({ type: 'Feature', properties: {}, geometry: { type: 'LineString', coordinates: state.trail } });
      }
      if (map.getLayer('route-pulse')) map.setPaintProperty('route-pulse', 'line-color', pulsePaint(frac)['line-color']);

      // progress bar + label
      $('progress-bar').style.width = (frac * 100).toFixed(1) + '%';
      $('progress-label').textContent = 'Прогресс: ' + (frac * 100).toFixed(1) + '%';

      followCamera(pos);
    }

    // ----- live animation loop ---------------------------------------------
    function tick(now) {
      if (state.playing) {
        const frac = (state.baseFrac + (now - state.startTime) * state.speedFactor / state.DURATION) % 1;
        update(frac);
      }
      requestAnimationFrame(tick);
    }

    function resetTrail() { state.trail = []; }

    // ----- controls ---------------------------------------------------------
    $('btn-play').addEventListener('click', () => {
      if (state.playing) {
        state.playing = false;
        state.baseFrac = (state.baseFrac + (performance.now() - state.startTime) * state.speedFactor / state.DURATION) % 1;
        $('btn-play').textContent = '▶ Играть';
      } else {
        state.playing = true;
        state.startTime = performance.now();
        $('btn-play').textContent = '⏸ Пауза';
      }
    });

    $('btn-restart').addEventListener('click', () => {
      state.playing = true;
      state.baseFrac = 0;
      state.startTime = performance.now();
      state.currentSeg = -1;
      $('btn-play').textContent = '⏸ Пауза';
      resetTrail();
      update(0);
      whoosh();
    });

    $('speed').addEventListener('input', (e) => {
      state.speedFactor = parseFloat(e.target.value);
      $('speed-val').textContent = state.speedFactor.toFixed(2).replace(/\.?0+$/, '') + '×';
    });

    $('follow').addEventListener('change', (e) => { state.follow = e.target.checked; });
    $('sound').addEventListener('change', (e) => { state.sound = e.target.checked; });

    map.on('dragstart', () => { state.follow = false; $('follow').checked = false; });
    $('follow').addEventListener('change', () => {
      if (state.follow) followCamera(interpolate(coords, cum, state.frac));
    });

    // ----- style switcher ---------------------------------------------------
    const sel = $('style-select');
    sel.innerHTML = '';
    for (const s of STYLES) {
      const o = document.createElement('option');
      o.value = s.url; o.textContent = s.name;
      sel.appendChild(o);
    }
    sel.value = STYLES[0].url;
    sel.addEventListener('change', (e) => {
      const url = e.target.value;
      map.setStyle(url === 'osm' ? OSM_RASTER_STYLE : url);
      // MapLibre v4 setStyle emits `styledata` (not `style.load`), with timing
      // that races `isStyleLoaded()`. Poll until the new style is ready and the
      // route sources are gone, then re-add them — deterministic and idempotent.
      const attempt = () => {
        if (map.isStyleLoaded() && !map.getSource('route')) {
          addRouteLayers();
          bindCityPopups();
          return;
        }
        setTimeout(attempt, 120);
      };
      attempt();
    });

    // ----- assemble on load -------------------------------------------------
    map.on('load', () => {
      addRouteLayers();
      bindCityPopups();
      addEndpointMarkers();

      if (coords.length) {
        const bounds = coords.reduce((b, c) => b.extend(c), new maplibregl.LngLatBounds(coords[0], coords[0]));
        map.fitBounds(bounds, { padding: 90, duration: 900 });
      }

      state.startTime = performance.now();
      resetTrail();
      update(0);
      whoosh();
      requestAnimationFrame(tick);
    });

    // ----- expose API for the export module --------------------------------
    window.TravelMap = {
      map, route, coords, cum, state,
      interpolate: (f) => interpolate(coords, cum, f),
      update,
      setSpeed: (v) => { state.speedFactor = v; $('speed').value = v; $('speed-val').textContent = v + '×'; },
      getMap: () => map,
    };
  }

  main();
})();
