/* Map page: render route GeoJSON with MapLibre and animate a marker. */
(function () {
  'use strict';

  const EQUATOR = 40075;
  const MOON = 384400;

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

  function renderInfo(route) {
    document.getElementById('r-title').textContent = route.route_text;

    // aggregate by transport from LineString features
    const byT = {};
    for (const f of route.geojson.features) {
      if (f.geometry.type !== 'LineString') continue;
      const p = f.properties;
      byT[p.transport] = byT[p.transport] || { km: 0, name: p.transport_name, color: p.color };
      byT[p.transport].km += p.distance_km;
    }

    const totalKm = route.total_distance_km;
    const legend = document.getElementById('legend');
    legend.innerHTML = '';
    for (const t of Object.keys(byT)) {
      const b = byT[t];
      const pct = totalKm ? (b.km / totalKm * 100).toFixed(1) : 0;
      const item = document.createElement('span');
      item.className = 'item';
      item.innerHTML = '<span class="dot" style="background:' + b.color + '"></span>' +
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
    const info = document.getElementById('info-rows');
    info.innerHTML = '';
    for (const [k, v] of rows) {
      const row = document.createElement('div');
      row.className = 'info-row';
      row.innerHTML = '<span class="k">' + k + '</span><span class="v">' + v + '</span>';
      info.appendChild(row);
    }
  }

  function startAnimation(map, coords) {
    if (!coords.length) return;
    const cum = cumLengths(coords);

    const el = document.createElement('div');
    el.innerHTML = '<div style="width:18px;height:18px;background:#fff;border:3px solid #3b82f6;border-radius:50%;box-shadow:0 0 12px rgba(59,130,246,.95)"></div>';
    const marker = new maplibregl.Marker({ element: el }).setLngLat(coords[0]).addTo(map);

    let playing = true;
    let startTime = performance.now();
    let baseFrac = 0;
    const DURATION = 30000;

    const btnPlay = document.getElementById('btn-play');
    const btnRestart = document.getElementById('btn-restart');
    const bar = document.getElementById('progress-bar');
    const label = document.getElementById('progress-label');

    function tick(now) {
      if (playing) {
        const frac = (baseFrac + (now - startTime) / DURATION) % 1;
        marker.setLngLat(interpolate(coords, cum, frac));
        bar.style.width = (frac * 100).toFixed(1) + '%';
        label.textContent = 'Прогресс: ' + (frac * 100).toFixed(1) + '%';
      }
      requestAnimationFrame(tick);
    }

    btnPlay.addEventListener('click', () => {
      if (playing) {
        playing = false;
        baseFrac = (baseFrac + (performance.now() - startTime) / DURATION) % 1;
        btnPlay.textContent = '▶ Играть';
      } else {
        playing = true;
        startTime = performance.now();
        btnPlay.textContent = '⏸ Пауза';
      }
    });

    btnRestart.addEventListener('click', () => {
      playing = true;
      baseFrac = 0;
      startTime = performance.now();
      btnPlay.textContent = '⏸ Пауза';
      marker.setLngLat(coords[0]);
    });

    requestAnimationFrame(tick);
  }

  async function main() {
    const cfg = window.ROUTE_CONFIG;
    let route;
    try {
      if (cfg.inline) {
        route = cfg.inline;
      } else if (cfg.fetch_id) {
        const r = await fetch('/api/geojson/' + cfg.fetch_id);
        if (!r.ok) throw new Error('Маршрут не найден');
        route = await r.json();
      } else {
        throw new Error('Нет данных маршрута');
      }
    } catch (e) {
      document.getElementById('overlay').innerHTML =
        '<a class="back btn-link" href="/">← Назад</a><p>' + e.message + '</p>';
      return;
    }

    renderInfo(route);

    const map = new maplibregl.Map({
      container: 'map',
      style: {
        version: 8,
        sources: {
          osm: {
            type: 'raster',
            tiles: ['https://tile.openstreetmap.org/{z}/{x}/{y}.png'],
            tileSize: 256,
            attribution: '© OpenStreetMap contributors',
          },
        },
        layers: [{ id: 'osm', type: 'raster', source: 'osm' }],
      },
      center: [30, 50],
      zoom: 2,
    });
    map.addControl(new maplibregl.NavigationControl(), 'top-right');

    map.on('load', () => {
      map.addSource('route', { type: 'geojson', data: route.geojson });

      map.addLayer({
        id: 'route-lines',
        type: 'line',
        source: 'route',
        filter: ['==', '$type', 'LineString'],
        layout: { 'line-join': 'round', 'line-cap': 'round' },
        paint: { 'line-color': ['get', 'color'], 'line-width': 4, 'line-opacity': 0.85 },
      });

      map.addLayer({
        id: 'city-dots',
        type: 'circle',
        source: 'route',
        filter: ['==', '$type', 'Point'],
        paint: { 'circle-radius': 5, 'circle-color': '#ffffff', 'circle-stroke-color': '#1f2937', 'circle-stroke-width': 2 },
      });

      map.addLayer({
        id: 'city-labels',
        type: 'symbol',
        source: 'route',
        filter: ['==', '$type', 'Point'],
        layout: { 'text-field': ['get', 'city'], 'text-size': 13, 'text-offset': [0, 1.4], 'text-anchor': 'top' },
        paint: { 'text-color': '#ffffff', 'text-halo-color': '#000000', 'text-halo-width': 1.5 },
      });

      const coords = flattenCoords(route.geojson);
      if (coords.length) {
        const bounds = coords.reduce(
          (b, c) => b.extend(c),
          new maplibregl.LngLatBounds(coords[0], coords[0])
        );
        map.fitBounds(bounds, { padding: 80, duration: 800 });
      }
      startAnimation(map, coords);
    });
  }

  main();
})();
