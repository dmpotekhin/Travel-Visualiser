/* Studio export: aspect-ratio + quality + watermark/titles/music + tier limits.
 * Captures whichever view is active (2D MapLibre canvas or 3D Cesium canvas). */
(function () {
  'use strict';

  const G = window.GeoUtils;
  const $ = (id) => document.getElementById(id);
  const CDN = { mp4muxer: '/vendor/mp4-muxer.min.js', gifjs: '/vendor/gif.js', gifworker: '/vendor/gif.worker.js' };

  function loadScript(src) {
    return new Promise((resolve, reject) => {
      const s = document.createElement('script');
      s.src = src; s.onload = resolve; s.onerror = () => reject(new Error('Не удалось загрузить ' + src));
      document.head.appendChild(s);
    });
  }
  let scriptsLoaded = false;
  async function ensureScripts() {
    if (scriptsLoaded) return;
    await loadScript(CDN.mp4muxer);
    await loadScript(CDN.gifjs);
    scriptsLoaded = true;
  }

  function resolveDims(aspect, quality) {
    const q = { '720p': 720, '1080p': 1080, '2160p': 2160 }[quality] || 1080;
    const [aw, ah] = aspect.split(':').map(Number);
    let w, h;
    if (aw >= ah) { h = q; w = Math.round(q * aw / ah); }
    else { w = q; h = Math.round(q * ah / aw); }
    w -= w % 2; h -= h % 2;
    return { w, h };
  }

  // draw the DOM vehicle marker (2D mode) onto the composite canvas — the marker
  // is an HTML overlay, absent from the WebGL canvas.
  function drawMarker(ctx, W, H) {
    const map = Studio.getMap();
    const lngLat = Studio.getMarkerLngLat();
    if (!map || !lngLat) return;
    const src = map.getCanvas();
    const sw = src.width, sh = src.height;
    if (!sw || !sh) return;
    const scale = Math.max(W / sw, H / sh);
    const dw = sw * scale, dh = sh * scale;
    const cssW = map.getContainer().clientWidth || sw;
    const k = dw / cssW;
    const p = map.project(lngLat);
    const cx = (W - dw) / 2 + p.x * k;
    const cy = (H - dh) / 2 + p.y * k;
    const pad = 60 * k;
    if (cx < -pad || cx > W + pad || cy < -pad || cy > H + pad) return;

    const emoji = Studio.getMarkerEmoji() || '🚗';
    const rotation = Studio.getMarkerRotation() || 0;
    const iconSize = 44 * k;
    const iconCy = cy - 4 * k;

    ctx.save();
    ctx.fillStyle = 'rgba(0,0,0,0.35)';
    ctx.beginPath();
    ctx.ellipse(cx, iconCy + iconSize * 0.34, iconSize * 0.28, iconSize * 0.20, 0, 0, Math.PI * 2);
    ctx.fill();
    ctx.restore();

    ctx.save();
    ctx.translate(cx, iconCy);
    ctx.rotate(rotation * Math.PI / 180);
    ctx.font = Math.round(30 * k) + 'px "Apple Color Emoji", "Segoe UI Emoji", sans-serif';
    ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
    ctx.fillText(emoji, 0, 0);
    ctx.restore();
  }

  function drawComposite(ctx, W, H, opts, frac, elapsed, totalMs) {
    ctx.fillStyle = '#000';
    ctx.fillRect(0, 0, W, H);
    const canvas = Studio.getActiveCanvas();
    if (canvas && canvas.width && canvas.height) {
      const scale = Math.max(W / canvas.width, H / canvas.height);
      const dw = canvas.width * scale, dh = canvas.height * scale;
      ctx.drawImage(canvas, (W - dw) / 2, (H - dh) / 2, dw, dh);
    }
    if (Studio.mode() === '2d') drawMarker(ctx, W, H);

    if (opts.watermark) {
      ctx.font = 'bold ' + Math.round(W * 0.025) + 'px -apple-system, Segoe UI, Roboto, sans-serif';
      ctx.fillStyle = 'rgba(255,255,255,0.85)';
      ctx.shadowColor = 'rgba(0,0,0,0.7)'; ctx.shadowBlur = 6;
      const pad = Math.round(W * 0.02);
      const tw = ctx.measureText(opts.watermark).width;
      let x = pad, y = H - pad;
      if (opts.wmPos.includes('right')) x = W - tw - pad;
      if (opts.wmPos.includes('top')) y = pad + Math.round(W * 0.04);
      ctx.fillText(opts.watermark, x, y);
      ctx.shadowBlur = 0;
    }

    const introMs = 2000, outroMs = 2500;
    if (opts.intro && elapsed < introMs) drawTitle(ctx, W, H, opts.intro, Math.min(1, elapsed / 300));
    if (opts.outro && elapsed > totalMs - outroMs) drawTitle(ctx, W, H, opts.outro, Math.min(1, (totalMs - elapsed) / 300));
  }
  function drawTitle(ctx, W, H, text, alpha) {
    ctx.fillStyle = 'rgba(0,0,0,' + (0.55 * alpha) + ')';
    ctx.fillRect(0, H * 0.42, W, H * 0.16);
    ctx.fillStyle = 'rgba(255,255,255,' + alpha + ')';
    ctx.font = 'bold ' + Math.round(W * 0.045) + 'px -apple-system, Segoe UI, Roboto, sans-serif';
    ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
    ctx.fillText(text, W / 2, H / 2);
    ctx.textAlign = 'left'; ctx.textBaseline = 'alphabetic';
  }

  function downloadBlob(blob, filename) {
    const url = URL.createObjectURL(blob);
    const a = $('export-download');
    a.href = url; a.download = filename;
    a.textContent = '⬇ Скачать ' + filename;
    a.classList.remove('hidden');
  }

  async function decodeAudio(thing, ctx) {
    const arr = (thing instanceof Blob) ? await thing.arrayBuffer() : await (await fetch(thing)).arrayBuffer();
    return ctx.decodeAudioData(arr);
  }

  function startAudioTrack(audioCtx, audioBuf) {
    const dest = audioCtx.createMediaStreamDestination();
    const src = audioCtx.createBufferSource();
    src.buffer = audioBuf; src.loop = true; src.connect(dest); src.start();
    return { src, dest };
  }

  // prefill export modal from the project's video settings
  function prefill() {
    const v = Studio.project.video || {};
    if (v.aspect) $('exp-aspect').value = v.aspect;
    if (v.quality) $('exp-quality').value = v.quality;
    if (v.watermark) $('exp-watermark').value = v.watermark;
    if (v.wmPos) $('exp-wm-pos').value = v.wmPos;
    if (v.intro) $('exp-intro').value = v.intro;
    if (v.outro) $('exp-outro').value = v.outro;
    const t = G.tier;
    let note = t.isPro()
      ? 'Тариф Pro: без лимитов и без водяного знака приложения.'
      : 'Бесплатный тариф: ' + t.remaining() + ' экспорт(а) осталось в этом месяце, добавляется водяной знак приложения.';
    if ($('exp-quality').value === '2160p') note += ' 4K записывается дольше и требователен к памяти.';
    $('export-tier-note').textContent = note;
  }

  async function startExport() {
    if (!window.Studio) { alert('Студия ещё не готова'); return; }

    const t = G.tier;
    if (!t.canExport()) {
      alert('Достигнут лимит бесплатного тарифа (3 экспорта в месяц).\nОбновите до Pro, чтобы снять лимит.');
      return;
    }

    const format = $('exp-format').value;
    const dims = resolveDims($('exp-aspect').value, $('exp-quality').value);
    const fps = parseInt($('exp-fps').value, 10) || 30;
    const bitrate = 12000 * 1000;

    // free tier always stamps the app watermark
    let userWm = $('exp-watermark').value.trim();
    const forced = t.forcedWatermark();
    const watermark = t.isPro() ? userWm : (userWm ? userWm + ' · ' + forced : forced);
    const wmPos = $('exp-wm-pos').value;
    const opts = {
      watermark, wmPos,
      intro: $('exp-intro').value.trim(),
      outro: $('exp-outro').value.trim(),
      audio: $('exp-audio').files[0] || (Studio.project.video && Studio.project.video.music) || null,
    };

    let W = dims.w, H = dims.h;
    if (format === 'gif') { const maxW = 640; if (W > maxW) { H = Math.round(H * maxW / W); W = maxW; } }

    $('export-progress').classList.remove('hidden');
    const bar = $('export-bar'), status = $('export-status');
    $('export-download').classList.add('hidden');
    $('export-start').disabled = true;
    const setStatus = (txt, p) => { status.textContent = txt; bar.style.width = p + '%'; };

    try { await ensureScripts(); }
    catch (e) { setStatus('Ошибка загрузки библиотек: ' + e.message, 0); $('export-start').disabled = false; return; }

    const D = Studio.state.DURATION;
    const totalMs = D;
    const composite = document.createElement('canvas');
    composite.width = W; composite.height = H;
    const ctx2d = composite.getContext('2d');

    // pause live, reset
    Studio.state.playing = false;
    Studio.state.baseFrac = 0;
    Studio.state.trail = [];
    Studio.state.currentSeg = -1; Studio.state.currentSeg3d = -1; Studio.state.lastPoint = -1;
    Studio.update(0);
    await new Promise((r) => setTimeout(r, 120));

    let audioCtx = null, audioSrc = null;
    let recorder = null, videoEncoder = null, muxer = null, gif = null;

    try {
      if (format === 'gif') {
        gif = new GIF({ workers: 2, quality: 10, width: W, height: H, workerScript: CDN.gifworker });
        gif.on('progress', (p) => setStatus('Кодирование GIF… ' + Math.round(p * 100) + '%', 100));
        gif.on('finished', (blob) => {
          downloadBlob(blob, 'travel.gif');
          setStatus('Готово — файл можно скачать.', 100);
          t.record();
          $('export-start').disabled = false;
        });
      } else {
        const stream = composite.captureStream(fps);
        if (format === 'mp4' && window.VideoEncoder && window.Mp4Muxer) {
          const { Muxer, ArrayBufferTarget } = window.Mp4Muxer;
          muxer = new Muxer({ target: new ArrayBufferTarget(), video: { codec: 'avc', width: W, height: H }, fastStart: 'in-memory' });
          videoEncoder = new VideoEncoder({
            output: (chunk, meta) => muxer.addVideoChunk(chunk, meta),
            error: (e) => { throw e; },
          });
          const supported = await VideoEncoder.isConfigSupported({ codec: 'avc1.42001f', width: W, height: H, bitrate, framerate: fps });
          if (!supported.supported) throw new Error('H.264 не поддерживается');
          videoEncoder.configure({ codec: 'avc1.42001f', width: W, height: H, bitrate, framerate: fps, avc: { format: 'avc' } });
        } else {
          let mime, isMp4 = format === 'mp4';
          if (isMp4) mime = ['video/mp4;codecs=avc1', 'video/mp4'].find((m) => MediaRecorder.isTypeSupported(m));
          else mime = ['video/webm;codecs=vp9', 'video/webm;codecs=vp8', 'video/webm'].find((m) => MediaRecorder.isTypeSupported(m));
          if (!mime) throw new Error('Нет поддерживаемого кодека для ' + format);

          const tracks = [stream.getVideoTracks()[0]];
          if (opts.audio && !isMp4) {
            audioCtx = new (window.AudioContext || window.webkitAudioContext)();
            const buf = await decodeAudio(opts.audio, audioCtx);
            if (buf) { const tr = startAudioTrack(audioCtx, buf); audioSrc = tr.src; tracks.push(tr.dest.getAudioTracks()[0]); }
          }
          recorder = new MediaRecorder(new MediaStream(tracks), { mimeType: mime, videoBitsPerSecond: bitrate });
          const chunks = [];
          recorder.ondataavailable = (e) => { if (e.data.size) chunks.push(e.data); };
          recorder.onstop = () => {
            downloadBlob(new Blob(chunks, { type: mime }), format === 'mp4' ? 'travel.mp4' : 'travel.webm');
            t.record();
            $('export-start').disabled = false;
          };
          recorder.start(200);
        }
      }

      const start = performance.now();
      let lastCapture = 0, frameIndex = 0;
      const interval = 1000 / fps;

      await new Promise((resolve, reject) => {
        function frame(now) {
          const elapsed = now - start;
          const frac = Math.min(1, elapsed / totalMs);
          Studio.update(frac);
          drawComposite(ctx2d, W, H, opts, frac, elapsed, totalMs);

          if (videoEncoder) {
            if (elapsed - lastCapture >= interval) {
              lastCapture = elapsed;
              const f = new VideoFrame(composite, { timestamp: Math.round(frameIndex * 1e6 / fps), duration: Math.round(1e6 / fps) });
              videoEncoder.encode(f, { keyFrame: frameIndex % (fps * 2) === 0 });
              f.close(); frameIndex++;
            }
          } else if (gif) {
            if (elapsed - lastCapture >= interval) {
              lastCapture = elapsed;
              gif.addFrame(composite, { copy: true, delay: interval });
            }
          }

          setStatus(format === 'gif' ? 'Запись кадров…' : 'Запись…', Math.round(frac * 100));
          if (frac >= 1) {
            setStatus('Финализация…', 100);
            finish(resolve, reject);
            return;
          }
          requestAnimationFrame(frame);
        }
        requestAnimationFrame(frame);
      });

      async function finish(resolve, reject) {
        try {
          if (videoEncoder) { await videoEncoder.flush(); muxer.finalize(); downloadBlob(new Blob([muxer.target.buffer], { type: 'video/mp4' }), 'travel.mp4'); t.record(); $('export-start').disabled = false; }
          else if (gif) gif.render();
          else if (recorder) recorder.stop();
          if (audioSrc) audioSrc.stop();
          if (audioCtx) audioCtx.close();
          resolve();
        } catch (e) { reject(e); }
      }

      if (format !== 'gif') setStatus('Готово — файл можно скачать.', 100);
    } catch (e) {
      console.error(e);
      setStatus('Ошибка: ' + e.message, 0);
      $('export-start').disabled = false;
      if (audioSrc) audioSrc.stop();
      if (audioCtx) audioCtx.close();
    } finally {
      Studio.state.playing = false;
      Studio.state.baseFrac = 1;
    }
  }

  // ---- wire UI ------------------------------------------------------------
  // Only wire up if the studio actually initialized (a project was present).
  // Without a project studio.js wipes the overlay and Studio is undefined.
  if (!window.Studio) return;

  $('btn-export').addEventListener('click', () => { prefill(); $('export-modal').classList.remove('hidden'); });
  $('export-close').addEventListener('click', () => $('export-modal').classList.add('hidden'));
  $('export-cancel').addEventListener('click', () => $('export-modal').classList.add('hidden'));
  $('export-start').addEventListener('click', startExport);
  $('exp-format').addEventListener('change', () => {
    const f = $('exp-format').value;
    $('exp-fps').parentElement.style.display = f === 'gif' ? 'none' : '';
  });
})();
