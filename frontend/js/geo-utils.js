/* Shared geo + transport helpers for the wizard and the studio.
 * Loaded before wizard.js / studio.js. Exposes window.GeoUtils and
 * window.GeoUtils.tier (free/pro export limits). */
(function () {
  'use strict';

  const TRANSPORTS = {
    air:   { name: 'Самолёт',    emoji: '✈️', color: '#3182ce', speed: 850 },
    rail:  { name: 'Поезд',      emoji: '🚂', color: '#2f855a', speed: 80 },
    car:   { name: 'Авто',       emoji: '🚗', color: '#c53030', speed: 90 },
    bus:   { name: 'Автобус',    emoji: '🚌', color: '#b7791f', speed: 70 },
    ferry: { name: 'Паром',      emoji: '⛴️', color: '#2c7a7b', speed: 35 },
    bike:  { name: 'Велосипед',  emoji: '🚲', color: '#d69e2e', speed: 18 },
    foot:  { name: 'Пешком',     emoji: '🚶', color: '#805ad5', speed: 5 },
  };

  const R = 6371.0088;

  // a, b are [lon, lat]
  function haversineKm(a, b) {
    const p1 = a[1] * Math.PI / 180, p2 = b[1] * Math.PI / 180;
    const dp = (b[1] - a[1]) * Math.PI / 180;
    const dl = (b[0] - a[0]) * Math.PI / 180;
    const h = Math.sin(dp / 2) ** 2 + Math.cos(p1) * Math.cos(p2) * Math.sin(dl / 2) ** 2;
    return 2 * R * Math.asin(Math.min(1, Math.sqrt(h)));
  }

  // great-circle interpolation between two [lon,lat] points -> array of [lon,lat]
  function geodesicPoints(a, b, n) {
    n = n || 64;
    const lat1 = a[1] * Math.PI / 180, lon1 = a[0] * Math.PI / 180;
    const lat2 = b[1] * Math.PI / 180, lon2 = b[0] * Math.PI / 180;
    const xyz = (lat, lon) => [Math.cos(lat) * Math.cos(lon), Math.cos(lat) * Math.sin(lon), Math.sin(lat)];
    const p1 = xyz(lat1, lon1), p2 = xyz(lat2, lon2);
    const dot = Math.max(-1, Math.min(1, p1[0] * p2[0] + p1[1] * p2[1] + p1[2] * p2[2]));
    const omega = Math.acos(dot);
    if (omega < 1e-9) return [[a[0], a[1]], [b[0], b[1]]];
    const out = [];
    for (let i = 0; i <= n; i++) {
      const t = i / n;
      const s = Math.sin((1 - t) * omega) / Math.sin(omega);
      const q = Math.sin(t * omega) / Math.sin(omega);
      const x = s * p1[0] + q * p2[0];
      const y = s * p1[1] + q * p2[1];
      const z = s * p1[2] + q * p2[2];
      const lat = Math.atan2(z, Math.sqrt(x * x + y * y));
      const lon = Math.atan2(y, x);
      out.push([lon * 180 / Math.PI, lat * 180 / Math.PI]);
    }
    return out;
  }

  function autoTransport(d) {
    if (d > 1000) return 'air';
    if (d > 200) return 'rail';
    if (d > 30) return 'car';
    return 'foot';
  }

  // points: [{name, coord}], transports: optional per-segment keys
  function buildSegments(points, transports) {
    const segs = [];
    for (let i = 0; i < points.length - 1; i++) {
      const a = points[i].coord, b = points[i + 1].coord;
      const d = haversineKm(a, b);
      const t = (transports && transports[i]) || autoTransport(d);
      const m = TRANSPORTS[t] || TRANSPORTS.car;
      segs.push({
        from: points[i].name, to: points[i + 1].name, transport: t,
        transport_name: m.name, emoji: m.emoji, color: m.color,
        distance_km: Math.round(d * 100) / 100,
        duration_min: Math.round(d / m.speed * 60 * 10) / 10,
        geometry: geodesicPoints(a, b),
      });
    }
    return segs;
  }

  function buildGeojson(segments, points) {
    const features = [];
    for (const s of segments) {
      features.push({
        type: 'Feature',
        geometry: { type: 'LineString', coordinates: s.geometry },
        properties: {
          from: s.from, to: s.to, transport: s.transport,
          transport_name: s.transport_name, emoji: s.emoji, color: s.color,
          distance_km: s.distance_km, duration_min: s.duration_min,
        },
      });
    }
    for (const p of points) {
      features.push({
        type: 'Feature',
        geometry: { type: 'Point', coordinates: p.coord },
        properties: { city: p.name },
      });
    }
    return { type: 'FeatureCollection', features };
  }

  function flattenCoords(geojson) {
    const out = [];
    for (const f of geojson.features) {
      if (f.geometry.type === 'LineString') out.push(...f.geometry.coordinates);
    }
    return out;
  }

  // ------------------------------------------------------------------------
  // map / globe style presets
  // ------------------------------------------------------------------------
  const STYLES_2D = [
    { id: 'voyager',  name: 'Voyager',     url: 'https://basemaps.cartocdn.com/gl/voyager-gl-style/style.json' },
    { id: 'positron', name: 'Positron',    url: 'https://basemaps.cartocdn.com/gl/positron-gl-style/style.json' },
    { id: 'dark',     name: 'Dark Matter', url: 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json' },
    { id: 'liberty',  name: 'Liberty',     url: 'https://tiles.openfreemap.org/styles/liberty' },
    { id: 'cartoon',  name: 'Мультяшный',  url: '/styles/cartoon.json' },
  ];
  // 3D globe imagery — all free, no Ion token required
  const STYLES_3D = [
    { id: 'dark',  name: 'Тёмный',      url: 'https://basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png' },
    { id: 'light', name: 'Светлый',     url: 'https://basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}.png' },
    { id: 'sat',   name: 'Спутниковый', url: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}' },
  ];

  // ------------------------------------------------------------------------
  // free / pro export limits (client-side stub; Stripe/YooKassa out of scope)
  // ------------------------------------------------------------------------
  const tier = {
    isPro() { return localStorage.getItem('travel-pro') === '1'; },
    upgrade() {
      const ok = confirm('Pro-подписка пока заглушка (Stripe / ЮKassa не подключены).\nСбросить лимит бесплатных экспортов на этот месяц?');
      if (ok) { localStorage.setItem('travel-pro', '1'); alert('Pro включён (заглушка).'); }
    },
    monthKey() { return 'travel-exports-' + new Date().toISOString().slice(0, 7); },
    count() { return parseInt(localStorage.getItem(this.monthKey()) || '0', 10); },
    limit() { return this.isPro() ? Infinity : 3; },
    canExport() { return this.count() < this.limit(); },
    remaining() { return this.isPro() ? Infinity : Math.max(0, this.limit() - this.count()); },
    record() { localStorage.setItem(this.monthKey(), String(this.count() + 1)); },
    // free tier forces an app watermark; pro removes it
    forcedWatermark() { return this.isPro() ? '' : 'travel visualizer'; },
    label() { return this.isPro() ? 'Pro' : 'Free'; },
  };

  window.GeoUtils = {
    TRANSPORTS, haversineKm, geodesicPoints, autoTransport,
    buildSegments, buildGeojson, flattenCoords, tier,
    STYLES_2D, STYLES_3D,
  };
})();
