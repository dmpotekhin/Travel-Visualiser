/* Main page: forms, stats, analytics, history. */
(function () {
  'use strict';

  const TRANSPORT_COLORS = {
    air: '#3182ce', rail: '#2f855a', car: '#c53030', bus: '#b7791f',
    ferry: '#2c7a7b', bike: '#d69e2e', foot: '#805ad5',
  };

  const toast = document.getElementById('toast');
  let toastTimer = null;
  function showToast(msg, ok) {
    toast.textContent = msg;
    toast.className = 'toast ' + (ok ? 'success' : 'error');
    toast.classList.remove('hidden');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => toast.classList.add('hidden'), 5000);
  }

  const fmtKm = (v) => Math.round(v).toLocaleString('ru-RU');

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

  let charts = {};

  function renderStats(stats) {
    const cards = document.getElementById('stat-cards');
    cards.innerHTML = '';
    const items = [
      ['Общий пробег', fmtKm(stats.total_km) + ' км'],
      ['В милях', fmtKm(stats.total_miles) + ' миль'],
      ['Экваторов', (stats.equators).toFixed(2) + '×'],
      ['До Луны', (stats.moon_distance * 100).toFixed(2) + '%'],
      ['Средний / маршрут', fmtKm(stats.avg_km_per_route) + ' км'],
      ['Время в пути', (stats.total_days).toFixed(1) + ' сут'],
      ['Маршрутов', String(stats.routes_count)],
      ['Сегментов', String(stats.segments_count)],
    ];
    for (const [label, value] of items) {
      const d = document.createElement('div');
      d.className = 'stat';
      d.innerHTML = '<div class="value">' + value + '</div><div class="label">' + label + '</div>';
      cards.appendChild(d);
    }
  }

  function renderCharts(stats) {
    if (charts.years) charts.years.destroy();
    charts.years = new Chart(document.getElementById('chart-years'), {
      type: 'bar',
      data: {
        labels: stats.year_distribution.map((x) => String(x.year)),
        datasets: [{ label: 'Км', data: stats.year_distribution.map((x) => x.km), backgroundColor: '#3b82f6' }],
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: {
          y: { ticks: { color: '#8b98a5' }, grid: { color: '#2a323c' } },
          x: { ticks: { color: '#8b98a5' }, grid: { display: false } },
        },
      },
    });

    if (charts.transport) charts.transport.destroy();
    charts.transport = new Chart(document.getElementById('chart-transport'), {
      type: 'doughnut',
      data: {
        labels: stats.transport_share.map((x) => x.name),
        datasets: [{
          data: stats.transport_share.map((x) => x.km),
          backgroundColor: stats.transport_share.map((x) => TRANSPORT_COLORS[x.transport] || '#889'),
        }],
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: { legend: { position: 'bottom', labels: { color: '#8b98a5' } } },
      },
    });
  }

  function renderTop(stats) {
    const routes = document.getElementById('top-routes');
    routes.innerHTML = '';
    for (const r of stats.top_routes) {
      routes.innerHTML += '<tr><td>' + esc(r.route_text) + '</td><td>' + fmtKm(r.km) + '</td></tr>';
    }
    if (!stats.top_routes.length) routes.innerHTML = '<tr><td colspan="2" class="muted">Пока нет маршрутов</td></tr>';

    const cities = document.getElementById('top-cities');
    cities.innerHTML = '';
    for (const c of stats.top_cities) {
      cities.innerHTML += '<tr><td>' + esc(c.city) + '</td><td>' + c.count + '</td></tr>';
    }
    if (!stats.top_cities.length) cities.innerHTML = '<tr><td colspan="2" class="muted">Пока нет городов</td></tr>';
  }

  function renderHistory(rows) {
    const tbody = document.getElementById('history');
    tbody.innerHTML = '';
    if (!rows.length) {
      tbody.innerHTML = '<tr><td colspan="6" class="muted">История пуста — добавьте первый маршрут.</td></tr>';
      return;
    }
    for (const r of rows) {
      const row = document.createElement('tr');
      row.innerHTML =
        '<td>' + esc(r.route_text) + '</td>' +
        '<td>' + (r.year || '—') + '</td>' +
        '<td>' + fmtKm(r.total_distance_km) + '</td>' +
        '<td>' + formatDuration(r.total_duration_min) + '</td>' +
        '<td class="muted small">' + esc(r.created_at || '') + '</td>' +
        '<td><a class="btn-link" href="' + r.map_url + '">Карта ↗</a></td>';
      tbody.appendChild(row);
    }
  }

  function renderUpload(data) {
    const box = document.getElementById('upload-result');
    box.classList.remove('hidden');
    let html = '<h3 style="margin-top:0">Обработано: ' + data.processed + ' маршрутов';
    if (data.errors) html += ' <span class="muted">(' + data.errors + ' ошибок)</span>';
    html += '</h3>';

    if (data.routes.length) {
      html += '<table><thead><tr><th>Маршрут</th><th>Год</th><th>Ваша оценка, км</th><th>Расчёт, км</th><th></th></tr></thead><tbody>';
      for (const r of data.routes) {
        if (r.error) {
          html += '<tr><td>' + esc(r.route_text) + '</td><td>' + (r.year || '—') + '</td>' +
            '<td colspan="2" style="color:#fca5a5">' + esc(r.error) + '</td><td></td></tr>';
        } else {
          html += '<tr><td>' + esc(r.route_text) + '</td><td>' + (r.year || '—') + '</td>' +
            '<td>' + (r.declared_km != null ? fmtKm(r.declared_km) : '—') + '</td>' +
            '<td>' + fmtKm(r.computed_km) + '</td>' +
            '<td><a class="btn-link" href="' + r.map_url + '">Карта ↗</a></td></tr>';
        }
      }
      html += '</tbody></table>';
    }
    box.innerHTML = html;
  }

  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, (c) => (
      { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]
    ));
  }

  async function loadAll() {
    try {
      const [s, h] = await Promise.all([fetch('/stats'), fetch('/history')]);
      const stats = await s.json();
      const history = await h.json();
      renderStats(stats);
      renderCharts(stats);
      renderTop(stats);
      renderHistory(history);
    } catch (e) {
      showToast('Не удалось загрузить данные: ' + e.message, false);
    }
  }

  document.getElementById('upload-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const fileInput = document.getElementById('file');
    if (!fileInput.files.length) { showToast('Выберите файл', false); return; }
    const fd = new FormData();
    fd.append('file', fileInput.files[0]);
    const btn = e.target.querySelector('button');
    btn.disabled = true;
    btn.textContent = '…';
    try {
      const r = await fetch('/upload', { method: 'POST', body: fd });
      const data = await r.json();
      if (!r.ok) { showToast(data.detail || 'Ошибка обработки', false); return; }
      renderUpload(data);
      showToast('Обработано маршрутов: ' + data.processed, true);
      loadAll();
    } catch (err) {
      showToast(err.message, false);
    } finally {
      btn.disabled = false;
      btn.textContent = '⬆ Обработать';
    }
  });

  loadAll();
})();
