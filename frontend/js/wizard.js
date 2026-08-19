/* Wizard (multi-step video constructor) for the studio. */
(function () {
  'use strict';

  const G = window.GeoUtils;
  const $ = (id) => document.getElementById(id);

  const TEMPLATES = [
    { id: 'cinematic', name: '🎥 Кинематографичный', style2d: 'dark', style3d: 'dark',
      aspect: '16:9', duration: 60, intro: 'Моё путешествие', outro: 'Спасибо за просмотр', watermark: '@traveler' },
    { id: 'fast', name: '⚡ Быстрый', style2d: 'voyager', style3d: 'light',
      aspect: '9:16', duration: 15, intro: '', outro: '', watermark: '' },
    { id: 'blog', name: '📱 Для блога', style2d: 'liberty', style3d: 'light',
      aspect: '1:1', duration: 30, intro: '', outro: '', watermark: '' },
    { id: 'minimal', name: '◽ Минимал', style2d: 'positron', style3d: 'light',
      aspect: '16:9', duration: 30, intro: '', outro: '', watermark: '' },
  ];

  const state = {
    step: 1,
    mode: 'text',
    route_text: '',
    points: [],                 // [{name, coord, photos:[], description}]
    transportOverride: {},      // { "from→to": transportKey }
    style2d: 'voyager',
    style3d: 'dark',
    video: { aspect: '16:9', quality: '1080p', duration: 30, watermark: '', wmPos: 'bottom-right', intro: '', outro: '', music: null, template: 'default' },
  };

  // ----- toast -------------------------------------------------------------
  let toastTimer = null;
  function toast(msg, ok) {
    const t = $('toast');
    t.textContent = msg;
    t.className = 'toast ' + (ok ? 'success' : 'error');
    t.classList.remove('hidden');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => t.classList.add('hidden'), 4500);
  }

  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, (c) => (
      { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]
    ));
  }

  // ----- derived segments --------------------------------------------------
  function currentSegments() {
    const overrides = state.points.slice(0, -1).map((p, i) => state.transportOverride[p.name + '→' + state.points[i + 1].name]);
    return G.buildSegments(state.points, overrides);
  }

  // ----- step navigation ---------------------------------------------------
  function showStep(n) {
    state.step = n;
    document.querySelectorAll('.step-panel').forEach((p) => p.classList.toggle('active', +p.dataset.step === n));
    document.querySelectorAll('#steps li').forEach((li) => li.classList.toggle('active', +li.dataset.step === n));
    $('btn-back').classList.toggle('hidden', n === 1);
    $('btn-next').textContent = n === 6 ? 'Готово' : 'Далее →';
    if (n === 4) initPreview();     // lazy MapLibre style preview
    if (n === 5) renderTierNote();
    if (n === 6) renderReview();
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  // ----- STEP 1: input tabs ------------------------------------------------
  function initTabs() {
    $('input-tabs').addEventListener('click', (e) => {
      const btn = e.target.closest('.tab');
      if (!btn) return;
      state.mode = btn.dataset.mode;
      document.querySelectorAll('#input-tabs .tab').forEach((b) => b.classList.toggle('active', b === btn));
      document.querySelectorAll('.tab-pane').forEach((p) => p.classList.toggle('active', p.dataset.pane === state.mode));
      $('nl-help').textContent = state.mode === 'nl'
        ? (G.tier.isPro() ? '' : 'Без ключа DeepSeek используется упрощённый парсер. Подключите DEEPSEEK_API_KEY для точного распознавания.')
        : '';
    });
  }

  async function parseInput() {
    const status = $('parse-status');
    status.textContent = 'Распознаю…';
    const btn = $('btn-parse'); btn.disabled = true;
    try {
      let preview;
      if (state.mode === 'file') {
        const f = $('in-file').files[0];
        if (!f) { toast('Выберите файл', false); return; }
        const fd = new FormData();
        fd.append('file', f);
        const r = await fetch('/api/parse-file', { method: 'POST', body: fd });
        preview = await r.json();
        if (!r.ok) throw new Error(preview.detail || 'Ошибка файла');
      } else {
        const input = {
          text: $('in-text').value,
          gmaps: $('in-gmaps').value,
          nl: $('in-nl').value,
        }[state.mode];
        if (!input.trim()) { toast('Введите данные', false); return; }
        const r = await fetch('/api/parse', {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ kind: state.mode, input }),
        });
        preview = await r.json();
        if (!r.ok) throw new Error(preview.detail || 'Ошибка распознавания');
      }

      state.route_text = preview.route_text;
      state.points = (preview.points || []).map((p) => ({ name: p.name, coord: p.coord, photos: [], description: '' }));
      state.transportOverride = {};
      if (state.points.length < 2) throw new Error('Нужно минимум две точки.');
      status.textContent = 'Готово: ' + state.points.length + ' точек, ' + (state.points.length - 1) + ' участков.';
      $('points-card').classList.remove('hidden');
      renderPoints();
      renderTransports();
      renderPhotos();
    } catch (e) {
      status.textContent = '';
      toast(e.message, false);
    } finally {
      btn.disabled = false;
    }
  }

  // ----- STEP 1: points list ----------------------------------------------
  function renderPoints() {
    const list = $('points-list');
    list.innerHTML = '';
    $('points-count').textContent = '(' + state.points.length + ')';
    state.points.forEach((p, i) => {
      const row = document.createElement('div');
      row.className = 'point-row';
      const btns = (cls, label, title, fn) => {
        const b = document.createElement('button');
        b.className = cls; b.textContent = label; b.title = title;
        b.addEventListener('click', fn);
        return b;
      };
      row.appendChild(btns('icon-btn', '↑', 'Вверх', () => { if (i > 0) { swap(i, i - 1); } }));
      row.appendChild(btns('icon-btn', '↓', 'Вниз', () => { if (i < state.points.length - 1) { swap(i, i + 1); } }));
      const name = document.createElement('span');
      name.className = 'point-name';
      name.textContent = (i + 1) + '. ' + p.name;
      row.appendChild(name);
      const coord = document.createElement('span');
      coord.className = 'muted small';
      coord.textContent = p.coord[1].toFixed(3) + ', ' + p.coord[0].toFixed(3);
      row.appendChild(coord);
      row.appendChild(btns('icon-btn danger', '✕', 'Удалить', () => {
        if (state.points.length <= 2) { toast('Нужно минимум две точки', false); return; }
        state.points.splice(i, 1);
        renderPoints(); renderTransports(); renderPhotos();
      }));
      list.appendChild(row);
    });
  }

  function swap(a, b) {
    const t = state.points[a]; state.points[a] = state.points[b]; state.points[b] = t;
    renderPoints(); renderTransports(); renderPhotos();
  }

  $('btn-add-point').addEventListener('click', async () => {
    const name = prompt('Название города:');
    if (!name) return;
    try {
      const r = await fetch('/api/geocode', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ name }) });
      const data = await r.json();
      if (!r.ok) throw new Error(data.detail || 'Не удалось геокодировать');
      state.points.push({ name: data.name, coord: data.coord, photos: [], description: '' });
      renderPoints(); renderTransports(); renderPhotos();
    } catch (e) { toast(e.message, false); }
  });

  // ----- STEP 2: transport -------------------------------------------------
  function renderTransports() {
    const box = $('transport-list');
    box.innerHTML = '';
    const segs = currentSegments();
    segs.forEach((s, i) => {
      const row = document.createElement('div');
      row.className = 'transport-row';
      row.innerHTML = '<span class="seg">' + esc(s.from) + ' → ' + esc(s.to) + '</span>' +
        '<span class="muted small">' + Math.round(s.distance_km).toLocaleString('ru-RU') + ' км</span>';
      const sel = document.createElement('select');
      for (const key of Object.keys(G.TRANSPORTS)) {
        const m = G.TRANSPORTS[key];
        const o = document.createElement('option');
        o.value = key; o.textContent = m.emoji + ' ' + m.name;
        o.selected = key === s.transport;
        sel.appendChild(o);
      }
      sel.addEventListener('change', () => {
        state.transportOverride[s.from + '→' + s.to] = sel.value;
        renderTransports();
      });
      row.appendChild(sel);
      box.appendChild(row);
    });
  }

  // ----- STEP 3: photos ----------------------------------------------------
  function renderPhotos() {
    const box = $('photo-list');
    box.innerHTML = '';
    state.points.forEach((p, i) => {
      const card = document.createElement('div');
      card.className = 'photo-card';
      card.innerHTML = '<div class="photo-title">' + (i + 1) + '. ' + esc(p.name) + '</div>';
      const file = document.createElement('input');
      file.type = 'file'; file.accept = 'image/*'; file.multiple = true;
      file.addEventListener('change', async () => {
        for (const f of Array.from(file.files)) {
          if (p.photos.length >= 5) { toast('Не более 5 фото на точку', false); break; }
          try { p.photos.push(await compressImage(f)); } catch (err) { toast('Не удалось прочитать фото', false); }
        }
        renderPhotos();
      });
      card.appendChild(file);
      const desc = document.createElement('textarea');
      desc.rows = 2; desc.placeholder = 'Описание (необязательно)';
      desc.value = p.description || '';
      desc.addEventListener('input', () => { p.description = desc.value; });
      card.appendChild(desc);
      if (p.photos.length) {
        const thumbs = document.createElement('div');
        thumbs.className = 'thumbs';
        p.photos.forEach((src, k) => {
          const img = document.createElement('img');
          img.src = src; img.className = 'thumb';
          img.title = 'Удалить';
          img.addEventListener('click', () => { p.photos.splice(k, 1); renderPhotos(); });
          thumbs.appendChild(img);
        });
        card.appendChild(thumbs);
      }
      box.appendChild(card);
    });
  }

  function compressImage(file, maxW, quality) {
    maxW = maxW || 800; quality = quality || 0.7;
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => {
        const img = new Image();
        img.onload = () => {
          const scale = Math.min(1, maxW / img.width);
          const c = document.createElement('canvas');
          c.width = Math.round(img.width * scale);
          c.height = Math.round(img.height * scale);
          c.getContext('2d').drawImage(img, 0, 0, c.width, c.height);
          resolve(c.toDataURL('image/jpeg', quality));
        };
        img.onerror = reject;
        img.src = reader.result;
      };
      reader.onerror = reject;
      reader.readAsDataURL(file);
    });
  }

  // ----- STEP 4: styles ----------------------------------------------------
  function renderStyles() {
    const s2 = $('style-2d');
    s2.innerHTML = '';
    for (const s of G.STYLES_2D) {
      const o = document.createElement('option');
      o.value = s.id; o.textContent = s.name; o.selected = s.id === state.style2d;
      s2.appendChild(o);
    }
    s2.addEventListener('change', () => { state.style2d = s2.value; updatePreview(); });

    const s3 = $('style-3d');
    s3.innerHTML = '';
    for (const s of G.STYLES_3D) {
      const o = document.createElement('option');
      o.value = s.id; o.textContent = s.name; o.selected = s.id === state.style3d;
      s3.appendChild(o);
    }
    s3.addEventListener('change', () => { state.style3d = s3.value; });
  }

  let previewMap = null;
  function initPreview() {
    renderStyles();
    if (!previewMap && window.maplibregl) {
      try {
        previewMap = new maplibregl.Map({
          container: 'style-preview',
          style: styleUrl(state.style2d),
          center: [37.6, 55.7],
          zoom: 4,
        });
        previewMap.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'top-right');
      } catch (e) { /* preview is non-critical */ }
    } else if (previewMap) {
      updatePreview();
    }
  }
  function updatePreview() {
    if (previewMap) previewMap.setStyle(styleUrl(state.style2d));
  }
  function styleUrl(id) {
    const s = G.STYLES_2D.find((x) => x.id === id) || G.STYLES_2D[0];
    return s.url;
  }

  // ----- STEP 5: video + templates ----------------------------------------
  function renderTemplates() {
    const box = $('templates');
    box.innerHTML = '';
    for (const t of TEMPLATES) {
      const b = document.createElement('button');
      b.className = 'template';
      b.textContent = t.name;
      b.addEventListener('click', () => applyTemplate(t));
      box.appendChild(b);
    }
  }

  function applyTemplate(t) {
    state.style2d = t.style2d;
    state.style3d = t.style3d;
    Object.assign(state.video, {
      aspect: t.aspect, duration: t.duration, intro: t.intro, outro: t.outro, watermark: t.watermark, template: t.id,
    });
    syncVideoUI();
    renderStyles();
  }

  function syncVideoUI() {
    $('v-aspect').value = state.video.aspect;
    $('v-quality').value = state.video.quality;
    $('v-duration').value = state.video.duration;
    $('v-duration-val').textContent = state.video.duration + ' с';
    $('v-watermark').value = state.video.watermark;
    $('v-wm-pos').value = state.video.wmPos;
    $('v-intro').value = state.video.intro;
    $('v-outro').value = state.video.outro;
  }

  function renderTierNote() {
    const t = G.tier;
    $('tier-note').textContent = t.isPro()
      ? 'Тариф Pro: без лимитов и без водяного знака приложения.'
      : 'Бесплатный тариф: до 3 экспортов в месяц, добавляется водяной знак приложения. ' +
        'Осталось экспортов: ' + t.remaining() + '.';
  }

  function initVideoUI() {
    renderTemplates();
    syncVideoUI();
    $('v-duration').addEventListener('input', (e) => {
      state.video.duration = parseInt(e.target.value, 10);
      $('v-duration-val').textContent = state.video.duration + ' с';
    });
    const bind = (id, key) => $(id).addEventListener('input', (e) => { state.video[key] = e.target.value; });
    bind('v-aspect', 'aspect'); bind('v-quality', 'quality'); bind('v-watermark', 'watermark');
    bind('v-wm-pos', 'wmPos'); bind('v-intro', 'intro'); bind('v-outro', 'outro');
    $('v-music').addEventListener('change', async () => {
      const f = $('v-music').files[0];
      if (!f) { state.video.music = null; return; }
      if (f.size > 4 * 1024 * 1024) { toast('Музыка слишком большая (макс 4 МБ)', false); return; }
      state.video.music = await fileToDataURL(f);
      toast('Музыка добавлена: ' + f.name, true);
    });
  }

  function fileToDataURL(file) {
    return new Promise((resolve, reject) => {
      const r = new FileReader();
      r.onload = () => resolve(r.result);
      r.onerror = reject;
      r.readAsDataURL(file);
    });
  }

  // ----- STEP 6: review ----------------------------------------------------
  function renderReview() {
    const segs = currentSegments();
    const totalKm = segs.reduce((a, s) => a + s.distance_km, 0);
    let html = '<p><strong>Маршрут:</strong> ' + esc(state.route_text || '—') + '</p>';
    html += '<p><strong>Точки:</strong> ' + state.points.length +
      ' · <strong>Участки:</strong> ' + segs.length +
      ' · <strong>Расстояние:</strong> ' + Math.round(totalKm).toLocaleString('ru-RU') + ' км</p>';
    html += '<p><strong>Транспорт:</strong> ' + segs.map((s) => s.emoji + ' ' + s.transport_name).join(' · ') + '</p>';
    const nPhotos = state.points.reduce((a, p) => a + p.photos.length, 0);
    html += '<p><strong>Фото:</strong> ' + nPhotos + '</p>';
    html += '<p><strong>Стиль:</strong> 2D ' + (G.STYLES_2D.find((x) => x.id === state.style2d) || {}).name +
      ' · 3D ' + (G.STYLES_3D.find((x) => x.id === state.style3d) || {}).name + '</p>';
    const v = state.video;
    html += '<p><strong>Видео:</strong> ' + v.aspect + ' · ' + v.quality + ' · ' + v.duration + ' с' +
      (v.watermark ? ' · знак «' + esc(v.watermark) + '»' : '') + (v.music ? ' · музыка' : '') + '</p>';
    $('review').innerHTML = html;
  }

  // ----- build project + open studio --------------------------------------
  function buildProject() {
    const segs = currentSegments();
    return {
      route_text: state.route_text,
      points: state.points,
      segments: segs,
      total_distance_km: Math.round(segs.reduce((a, s) => a + s.distance_km, 0) * 100) / 100,
      total_duration_min: Math.round(segs.reduce((a, s) => a + s.duration_min, 0) * 10) / 10,
      geojson: G.buildGeojson(segs, state.points),
      style: { map2d: state.style2d, globe: state.style3d },
      video: state.video,
    };
  }

  $('btn-open-studio').addEventListener('click', () => {
    try {
      const project = buildProject();
      localStorage.setItem('travel-studio-project', JSON.stringify(project));
      window.location.href = '/studio';
    } catch (e) {
      toast('Проект слишком большой для хранения (фото/музыка). Уменьшите размер файлов.', false);
    }
  });

  // ----- tier badge --------------------------------------------------------
  function renderTierBadge() {
    $('tier-label').textContent = G.tier.label();
    $('tier-upgrade').classList.toggle('hidden', G.tier.isPro());
  }
  $('tier-upgrade').addEventListener('click', () => G.tier.upgrade());

  // ----- nav ---------------------------------------------------------------
  $('btn-next').addEventListener('click', () => {
    if (state.step === 1 && state.points.length < 2) { toast('Сначала распознайте маршрут (минимум 2 точки)', false); return; }
    showStep(Math.min(6, state.step + 1));
  });
  $('btn-back').addEventListener('click', () => showStep(Math.max(1, state.step - 1)));

  // ----- boot --------------------------------------------------------------
  initTabs();
  renderPoints();
  renderTransports();
  renderPhotos();
  renderStyles();
  initVideoUI();
  renderTierBadge();
  $('btn-parse').addEventListener('click', parseInput);
})();
