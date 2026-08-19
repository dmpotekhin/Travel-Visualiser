/* Studio: hybrid 2D (MapLibre) / 3D (CesiumJS) route animation with a single
 * shared state + one requestAnimationFrame loop. `state.frac` is the single
 * source of truth; both views read it, so switching 2D↔3D at any moment shows
 * the same position. */
(function () {
  'use strict';

  const G = window.GeoUtils;
  const $ = (id) => document.getElementById(id);

  // ---- load project -------------------------------------------------------
  let project = null;
  try { project = JSON.parse(localStorage.getItem('travel-studio-project')); } catch (e) { project = null; }
  if (!project || !project.points || project.points.length < 2) {
    $('overlay').innerHTML =
      '<a class="back btn-link" href="/wizard">← Конструктор</a>' +
      '<p>Проект не найден. Создайте маршрут в <a class="btn-link" href="/wizard">конструкторе</a>.</p>';
    return;
  }

  const points = project.points;
  const segments = project.segments;
  const geojson = project.geojson;
  const coords = G.flattenCoords(geojson);

  // ---- geo helpers --------------------------------------------------------
  function distKm(a, b) { return G.haversineKm(a, b); }
  function cumLengths(cs) {
    const cum = [0];
    for (let i = 1; i < cs.length; i++) cum.push(cum[i - 1] + distKm(cs[i - 1], cs[i]));
    return cum;
  }
  function interpolate(cs, cum, frac) {
    const total = cum[cum.length - 1];
    if (!cs.length) return null;
    if (total <= 0) return cs[0];
    const target = frac * total;
    let i = 1;
    while (i < cum.length && cum[i] < target) i++;
    if (i >= cum.length) return cs[cs.length - 1];
    const a = cs[i - 1], b = cs[i];
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
  function mergedLineCoords(cs) {
    const out = [];
    for (const c of cs) {
      const last = out[out.length - 1];
      if (last && last[0] === c[0] && last[1] === c[1]) continue;
      out.push(c);
    }
    return out;
  }

  const cum = cumLengths(coords);
  const merged = mergedLineCoords(coords);

  // point arrival fractions (for photo popups)
  const segLengths = segments.map((s) => s.geometry.reduce((acc, c, j, arr) => (j ? acc + distKm(arr[j - 1], c) : 0), 0));
  const totalLen = segLengths.reduce((a, b) => a + b, 0) || 1;
  const pointFrac = [0];
  let acc = 0;
  for (const l of segLengths) { acc += l; pointFrac.push(acc / totalLen); }

  // ---- shared state -------------------------------------------------------
  const state = {
    playing: true, frac: 0, speedFactor: 1, follow: true, mode: '2d',
    baseFrac: 0, startTime: 0,
    DURATION: ((project.video && project.video.duration) || 30) * 1000,
    currentSeg: -1, currentSeg3d: -1, lastPoint: -1, trail: [],
  };

  $('r-title').textContent = project.route_text || 'Маршрут';
  if (project.video && project.video.duration) {
    $('speed').value = 1;
    $('speed-val').textContent = '1×';
  }

  // ---- 2D: MapLibre -------------------------------------------------------
  let map = null, marker = null, markerEl = null;

  function styleUrl2d(id) {
    const s = G.STYLES_2D.find((x) => x.id === id) || G.STYLES_2D[0];
    return s.url;
  }

  function initMap() {
    const styleId = (project.style && project.style.map2d) || 'voyager';
    map = new maplibregl.Map({
      container: 'map-2d',
      style: styleUrl2d(styleId),
      center: [30, 50], zoom: 2,
      canvasContextAttributes: { preserveDrawingBuffer: true, antialias: true },
    });
    map.addControl(new maplibregl.NavigationControl(), 'top-right');

    // DOM marker (emoji + rotation)
    markerEl = document.createElement('div');
    markerEl.className = 'travel-marker';
    markerEl.innerHTML = '<span class="travel-marker-icon">🚗</span><span class="travel-marker-shadow"></span>';
    marker = new maplibregl.Marker({ element: markerEl, anchor: 'center' }).setLngLat(coords[0]).addTo(map);

    map.on('load', () => {
      addRouteLayers();
      if (coords.length) {
        const bounds = coords.reduce((b, c) => b.extend(c), new maplibregl.LngLatBounds(coords[0], coords[0]));
        map.fitBounds(bounds, { padding: 90, duration: 900 });
      }
      state.startTime = performance.now();
      update(0);
      requestAnimationFrame(tick);
    });

    // style select
    const sel = $('style-2d');
    sel.innerHTML = '';
    for (const s of G.STYLES_2D) {
      const o = document.createElement('option');
      o.value = s.id; o.textContent = s.name; o.selected = s.id === styleId;
      sel.appendChild(o);
    }
    sel.addEventListener('change', () => {
      map.setStyle(styleUrl2d(sel.value));
      const attempt = () => {
        if (map.isStyleLoaded() && !map.getSource('route')) { addRouteLayers(); return; }
        setTimeout(attempt, 120);
      };
      attempt();
    });

    map.on('dragstart', () => { state.follow = false; $('follow').checked = false; });
  }

  function addRouteLayers() {
    if (map.getSource('route')) return;
    map.addSource('route', { type: 'geojson', data: geojson, lineMetrics: true });
    map.addSource('route-gradient', {
      type: 'geojson', lineMetrics: true,
      data: { type: 'Feature', properties: {}, geometry: { type: 'LineString', coordinates: merged } },
    });
    map.addSource('route-trail', { type: 'geojson', lineMetrics: true, data: { type: 'Feature', properties: {}, geometry: { type: 'LineString', coordinates: [] } } });

    const gradient = ['interpolate', ['linear'], ['line-progress'], 0, '#3b82f6', 0.5, '#8b5cf6', 1, '#ef4444'];
    map.addLayer({ id: 'route-glow', type: 'line', source: 'route-gradient',
      layout: { 'line-join': 'round', 'line-cap': 'round' },
      paint: { 'line-color': gradient, 'line-width': 11, 'line-opacity': 0.18, 'line-blur': 1.5 } });
    map.addLayer({ id: 'route-gradient', type: 'line', source: 'route-gradient',
      layout: { 'line-join': 'round', 'line-cap': 'round' },
      paint: { 'line-color': gradient, 'line-width': 5, 'line-opacity': 0.95, 'line-blur': 0.5 } });
    map.addLayer({ id: 'route-transport', type: 'line', source: 'route', filter: ['==', '$type', 'LineString'],
      layout: { 'line-join': 'round', 'line-cap': 'round' },
      paint: { 'line-color': ['get', 'color'], 'line-width': 1.6, 'line-opacity': 0.55 } });
    map.addLayer({ id: 'route-trail-glow', type: 'line', source: 'route-trail',
      layout: { 'line-join': 'round', 'line-cap': 'round' },
      paint: { 'line-color': '#ffffff', 'line-width': 9, 'line-opacity': 0.18 } });
    map.addLayer({ id: 'route-trail', type: 'line', source: 'route-trail',
      layout: { 'line-join': 'round', 'line-cap': 'round' },
      paint: { 'line-color': '#ffffff', 'line-width': 4.5, 'line-opacity': 0.95 } });
    map.addLayer({ id: 'city-dots', type: 'circle', source: 'route', filter: ['==', '$type', 'Point'],
      paint: { 'circle-radius': 5, 'circle-color': '#ffffff', 'circle-stroke-color': '#1f2937', 'circle-stroke-width': 2 } });
    map.addLayer({ id: 'city-labels', type: 'symbol', source: 'route', filter: ['==', '$type', 'Point'],
      layout: { 'text-field': ['get', 'city'], 'text-font': ['Noto Sans Regular'], 'text-size': 13, 'text-offset': [0, 1.5], 'text-anchor': 'top' },
      paint: { 'text-color': '#ffffff', 'text-halo-color': '#000000', 'text-halo-width': 1.5 } });
  }

  function renderMap(frac) {
    if (!map || !marker) return;
    const pos = interpolate(coords, cum, frac);
    if (!pos) return;
    const ahead = interpolate(coords, cum, Math.min(1, frac + 0.004));
    marker.setLngLat(pos);
    markerEl.querySelector('.travel-marker-icon').style.transform = 'rotate(' + bearingDeg(pos, ahead) + 'deg)';

    const si = segmentIndexAt(frac);
    if (si !== state.currentSeg) {
      state.currentSeg = si;
      markerEl.querySelector('.travel-marker-icon').textContent = segments[si].emoji;
    }

    const last = state.trail[state.trail.length - 1];
    if (!last || last[0] !== pos[0] || last[1] !== pos[1]) state.trail.push([pos[0], pos[1]]);
    if (map.getSource('route-trail')) {
      map.getSource('route-trail').setData({ type: 'Feature', properties: {}, geometry: { type: 'LineString', coordinates: state.trail } });
    }

    if (state.follow) {
      const cur = map.getCenter();
      map.jumpTo({ center: [cur.lng + (pos[0] - cur.lng) * 0.06, cur.lat + (pos[1] - cur.lat) * 0.06] });
    }
  }

  function segmentIndexAt(frac) {
    const totalKm = project.total_distance_km || 1;
    const target = frac * totalKm;
    let a = 0;
    for (let i = 0; i < segments.length; i++) { a += segments[i].distance_km; if (target < a) return i; }
    return segments.length - 1;
  }

  // ---- 3D: Cesium ---------------------------------------------------------
  let viewer = null, markerEntity = null, traveledEntity = null;

  function emojiUrl(emoji) {
    const c = document.createElement('canvas'); c.width = 96; c.height = 96;
    const ctx = c.getContext('2d');
    ctx.font = '72px "Apple Color Emoji","Segoe UI Emoji",sans-serif';
    ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
    ctx.fillText(emoji, 48, 54);
    return c.toDataURL('image/png');
  }

  function initGlobe() {
    if (viewer || !window.Cesium) return viewer;
    const Cesium = window.Cesium;
    Cesium.Ion.defaultAccessToken = window.CESIUM_ION_TOKEN || '';

    const style3d = G.STYLES_3D.find((s) => s.id === (project.style && project.style.globe)) || G.STYLES_3D[0];

    viewer = new Cesium.Viewer('globe-3d', {
      baseLayerPicker: false, geocoder: false, homeButton: false, sceneModePicker: false,
      navigationHelpButton: false, animation: false, timeline: false, fullscreenButton: false,
      infoBox: false, selectionIndicator: false,
      baseLayer: false,   // don't create the default Ion imagery (avoids 401 without a token)
      contextOptions: { webgl: { preserveDrawingBuffer: true, antialias: true } },
    });
    viewer.imageryLayers.removeAll();
    viewer.imageryLayers.addImageryProvider(new Cesium.UrlTemplateImageryProvider({ url: style3d.url }));

    const flat = [];
    for (const c of coords) flat.push(c[0], c[1]);
    viewer.entities.add({
      polyline: {
        positions: Cesium.Cartesian3.fromDegreesArray(flat), width: 2.5,
        material: Cesium.Color.fromCssColorString('#3b82f6').withAlpha(0.85),
      },
    });
    traveledEntity = viewer.entities.add({
      polyline: { positions: [], width: 4, material: Cesium.Color.fromCssColorString('#ffffff').withAlpha(0.9) },
    });
    markerEntity = viewer.entities.add({
      position: Cesium.Cartesian3.fromDegrees(coords[0][0], coords[0][1]),
      billboard: { image: emojiUrl('🚗'), scale: 0.6, verticalOrigin: Cesium.VerticalOrigin.CENTER },
    });

    const lons = coords.map((c) => c[0]), lats = coords.map((c) => c[1]);
    const rect = Cesium.Rectangle.fromDegrees(Math.min(...lons), Math.min(...lats), Math.max(...lons), Math.max(...lats));
    viewer.camera.flyTo({ destination: rect, duration: 0 });
    return viewer;
  }

  function renderGlobe(frac) {
    if (!viewer) return;
    const Cesium = window.Cesium;
    const pos = interpolate(coords, cum, frac);
    if (!pos) return;
    markerEntity.position = Cesium.Cartesian3.fromDegrees(pos[0], pos[1]);

    const i = indexAtFrac(frac);
    const flat = [];
    for (let k = 0; k < i; k++) flat.push(coords[k][0], coords[k][1]);
    flat.push(pos[0], pos[1]);
    traveledEntity.polyline.positions = Cesium.Cartesian3.fromDegreesArray(flat);

    const si = segmentIndexAt(frac);
    if (si !== state.currentSeg3d) {
      state.currentSeg3d = si;
      markerEntity.billboard.image = emojiUrl(segments[si].emoji);
    }
    if (state.follow) viewer.trackedEntity = markerEntity;
    if (state.mode === '3d') viewer.render();
  }

  function indexAtFrac(frac) {
    const total = cum[cum.length - 1];
    if (total <= 0) return 0;
    const target = frac * total;
    let i = 1;
    while (i < cum.length && cum[i] < target) i++;
    return i;
  }

  // ---- photo popup --------------------------------------------------------
  let photoTimer = null;
  function checkPointArrival(frac) {
    let idx = 0;
    for (let i = 0; i < pointFrac.length; i++) { if (pointFrac[i] <= frac) idx = i; else break; }
    if (idx === state.lastPoint) return;
    state.lastPoint = idx;
    const p = points[idx];
    if (p && (p.photos.length || p.description)) showPhotoPopup(p);
  }
  function showPhotoPopup(p) {
    $('photo-title').textContent = p.name;
    $('photo-desc').textContent = p.description || '';
    const strip = $('photo-strip');
    strip.innerHTML = '';
    for (const src of p.photos) {
      const img = document.createElement('img');
      img.src = src; img.className = 'popup-photo';
      strip.appendChild(img);
    }
    $('photo-popup').classList.remove('hidden');
    clearTimeout(photoTimer);
    photoTimer = setTimeout(() => $('photo-popup').classList.add('hidden'), 3500);
  }

  // ---- shared update + loop ----------------------------------------------
  function update(frac) {
    state.frac = frac;
    renderMap(frac);
    renderGlobe(frac);
    checkPointArrival(frac);
    $('progress-bar').style.width = (frac * 100).toFixed(1) + '%';
    $('progress-label').textContent = 'Прогресс: ' + (frac * 100).toFixed(1) + '%';
  }

  function tick(now) {
    if (state.playing) {
      const frac = (state.baseFrac + (now - state.startTime) * state.speedFactor / state.DURATION) % 1;
      update(frac);
    }
    requestAnimationFrame(tick);
  }

  // ---- mode toggle --------------------------------------------------------
  function setMode(mode) {
    if (state.mode === mode) return;
    state.mode = mode;
    $('map-2d').classList.toggle('hidden', mode !== '2d');
    $('globe-3d').classList.toggle('hidden', mode !== '3d');
    $('btn-mode-2d').classList.toggle('active', mode === '2d');
    $('btn-mode-3d').classList.toggle('active', mode === '3d');
    $('style-2d').parentElement.style.display = mode === '2d' ? '' : 'none';
    if (mode === '3d') {
      if (!viewer) initGlobe();
      setTimeout(() => { if (viewer) viewer.resize(); update(state.frac); }, 60);
    } else {
      if (map) { map.resize(); update(state.frac); }
    }
  }
  $('btn-mode-2d').addEventListener('click', () => setMode('2d'));
  $('btn-mode-3d').addEventListener('click', () => setMode('3d'));

  // ---- controls -----------------------------------------------------------
  $('btn-play').addEventListener('click', () => {
    if (state.playing) {
      state.playing = false;
      state.baseFrac = (state.baseFrac + (performance.now() - state.startTime) * state.speedFactor / state.DURATION) % 1;
      $('btn-play').textContent = '▶ Играть';
    } else {
      state.playing = true; state.startTime = performance.now();
      $('btn-play').textContent = '⏸ Пауза';
    }
  });
  $('btn-restart').addEventListener('click', () => {
    state.playing = true; state.baseFrac = 0; state.startTime = performance.now();
    state.currentSeg = -1; state.currentSeg3d = -1; state.lastPoint = -1; state.trail = [];
    $('btn-play').textContent = '⏸ Пауза';
    update(0);
  });
  $('speed').addEventListener('input', (e) => {
    state.speedFactor = parseFloat(e.target.value);
    $('speed-val').textContent = state.speedFactor.toFixed(2).replace(/\.?0+$/, '') + '×';
  });
  $('follow').addEventListener('change', (e) => { state.follow = e.target.checked; });
  $('photo-close').addEventListener('click', () => $('photo-popup').classList.add('hidden'));

  // ---- expose API for export module --------------------------------------
  window.Studio = {
    state, project, segments, points,
    getMap: () => map,
    mode: () => state.mode,
    update,
    getActiveCanvas: () => (state.mode === '3d' && viewer ? viewer.scene.canvas : (map ? map.getCanvas() : null)),
    getMarkerLngLat: () => (marker ? marker.getLngLat() : null),
    getMarkerEmoji: () => (markerEl ? markerEl.querySelector('.travel-marker-icon').textContent : '🚗'),
    getMarkerRotation: () => {
      const el = markerEl && markerEl.querySelector('.travel-marker-icon');
      const m = el && (el.style.transform || '').match(/rotate\((-?[\d.]+)deg\)/);
      return m ? parseFloat(m[1]) : 0;
    },
  };

  // ---- boot ---------------------------------------------------------------
  initMap();
})();
