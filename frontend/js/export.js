/* Client-side export of the animated map to WebM / MP4 / GIF. */
(function () {
  'use strict';

  const $ = (id) => document.getElementById(id);
  const CDN = {
    mp4muxer: '/vendor/mp4-muxer.min.js',
    gifjs: '/vendor/gif.js',
    gifworker: '/vendor/gif.worker.js',
  };

  function loadScript(src) {
    return new Promise((resolve, reject) => {
      const s = document.createElement('script');
      s.src = src;
      s.onload = resolve;
      s.onerror = () => reject(new Error('Не удалось загрузить ' + src));
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

  function parseRes(v) { const [w, h] = v.split('x').map(Number); return { w, h }; }

  // draw map canvas into a WxH composite, cover-cropped, plus overlays
  function drawComposite(ctx, W, H, opts, frac, elapsed, totalMs) {
    ctx.fillStyle = '#000';
    ctx.fillRect(0, 0, W, H);
    const map = window.TravelMap.getMap();
    const src = map.getCanvas();
    const sw = src.width, sh = src.height;
    if (sw && sh) {
      const scale = Math.max(W / sw, H / sh);
      const dw = sw * scale, dh = sh * scale;
      ctx.drawImage(src, (W - dw) / 2, (H - dh) / 2, dw, dh);
    }

    // watermark
    if (opts.watermark && opts.wmPos !== 'none') {
      ctx.font = 'bold ' + Math.round(W * 0.025) + 'px -apple-system, Segoe UI, Roboto, sans-serif';
      ctx.fillStyle = 'rgba(255,255,255,0.85)';
      ctx.shadowColor = 'rgba(0,0,0,0.7)';
      ctx.shadowBlur = 6;
      const pad = Math.round(W * 0.02);
      const tw = ctx.measureText(opts.watermark).width;
      let x = pad, y = H - pad;
      if (opts.wmPos.includes('right')) x = W - tw - pad;
      if (opts.wmPos.includes('top')) y = pad + Math.round(W * 0.04);
      ctx.fillText(opts.watermark, x, y);
      ctx.shadowBlur = 0;
    }

    // intro / outro titles
    const introMs = 2000, outroMs = 2500;
    if (opts.intro && elapsed < introMs) {
      drawTitle(ctx, W, H, opts.intro, Math.min(1, elapsed / 300));
    }
    if (opts.outro && elapsed > totalMs - outroMs) {
      drawTitle(ctx, W, H, opts.outro, Math.min(1, (totalMs - elapsed) / 300));
    }
  }
  function drawTitle(ctx, W, H, text, alpha) {
    ctx.fillStyle = 'rgba(0,0,0,' + (0.55 * alpha) + ')';
    ctx.fillRect(0, H * 0.42, W, H * 0.16);
    ctx.fillStyle = 'rgba(255,255,255,' + alpha + ')';
    ctx.font = 'bold ' + Math.round(W * 0.045) + 'px -apple-system, Segoe UI, Roboto, sans-serif';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText(text, W / 2, H / 2);
    ctx.textAlign = 'left';
    ctx.textBaseline = 'alphabetic';
  }

  function downloadBlob(blob, filename) {
    const url = URL.createObjectURL(blob);
    const a = $('export-download');
    a.href = url;
    a.download = filename;
    a.textContent = '⬇ Скачать ' + filename;
    a.classList.remove('hidden');
  }

  // ----- audio mixing (for MediaRecorder paths) -----------------------------
  async function prepareAudio(file, ctx) {
    if (!file) return null;
    const arr = await file.arrayBuffer();
    const buf = await ctx.decodeAudioData(arr);
    return buf;
  }

  function startAudioTrack(audioCtx, audioBuf) {
    const dest = audioCtx.createMediaStreamDestination();
    const src = audioCtx.createBufferSource();
    src.buffer = audioBuf;
    src.loop = true;
    src.connect(dest);
    src.start();
    return { src, dest };
  }

  // ----- main record flow ---------------------------------------------------
  async function startExport() {
    const TM = window.TravelMap;
    if (!TM) { alert('Карта ещё не готова'); return; }

    const format = $('exp-format').value;
    const res = parseRes($('exp-res').value);
    const fps = parseInt($('exp-fps').value, 10) || 30;
    const speedFactor = parseFloat($('exp-speed').value) || 1;
    const bitrate = (parseInt($('exp-bitrate').value, 10) || 8000) * 1000;
    const opts = {
      watermark: $('exp-watermark').value.trim(),
      wmPos: $('exp-wm-pos').value,
      intro: $('exp-intro').value.trim(),
      outro: $('exp-outro').value.trim(),
      audioFile: $('exp-audio').files[0] || null,
    };

    // GIF resolution cap
    let W = res.w, H = res.h;
    if (format === 'gif') {
      const maxW = 640;
      if (W > maxW) { H = Math.round(H * maxW / W); W = maxW; }
    }

    $('export-progress').classList.remove('hidden');
    const bar = $('export-bar'), status = $('export-status');
    $('export-download').classList.add('hidden');
    $('export-start').disabled = true;
    const setStatus = (t, p) => { status.textContent = t; bar.style.width = p + '%'; };

    try {
      await ensureScripts();
    } catch (e) {
      setStatus('Ошибка загрузки библиотек: ' + e.message, 0);
      $('export-start').disabled = false;
      return;
    }

    const D = TM.state.DURATION;
    const totalMs = D / speedFactor;
    const map = TM.getMap();
    const composite = document.createElement('canvas');
    composite.width = W; composite.height = H;
    const ctx2d = composite.getContext('2d');

    // pause live animation, reset to start
    TM.state.playing = false;
    TM.state.baseFrac = 0;
    TM.state.trail = [];
    TM.state.currentSeg = -1;
    TM.update(0);
    await new Promise((r) => setTimeout(r, 120)); // let a frame settle

    let audioCtx = null, audioSrc = null, audioTrack = null;
    let recorder = null, videoEncoder = null, muxer = null, gif = null;

    try {
      // --- set up format-specific capture -------------------------------
      if (format === 'gif') {
        gif = new GIF({ workers: 2, quality: 10, width: W, height: H, workerScript: CDN.gifworker });
        gif.on('progress', (p) => setStatus('Кодирование GIF… ' + Math.round(p * 100) + '%', 100));
        gif.on('finished', (blob) => {
          downloadBlob(blob, 'travel.gif');
          setStatus('Готово — файл можно скачать.', 100);
          $('export-start').disabled = false;
        });
      } else {
        const canvasStream = composite.captureStream ? composite.captureStream(fps) : null;
        if (!canvasStream) throw new Error('captureStream не поддерживается');

        if (format === 'mp4' && window.VideoEncoder && window.Mp4Muxer) {
          // WebCodecs + mp4-muxer (Chrome/Edge)
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
          // MediaRecorder path (WebM, or MP4 native on Safari)
          let mime, isMp4 = format === 'mp4';
          if (isMp4) {
            mime = ['video/mp4;codecs=avc1', 'video/mp4'].find((m) => MediaRecorder.isTypeSupported(m));
          } else {
            mime = ['video/webm;codecs=vp9', 'video/webm;codecs=vp8', 'video/webm'].find((m) => MediaRecorder.isTypeSupported(m));
          }
          if (!mime) throw new Error('Нет поддерживаемого кодека для ' + format);

          const tracks = [canvasStream.getVideoTracks()[0]];
          // audio mix (MediaRecorder only)
          if (opts.audioFile && !isMp4) {
            audioCtx = new (window.AudioContext || window.webkitAudioContext)();
            const buf = await prepareAudio(opts.audioFile, audioCtx);
            if (buf) { const t = startAudioTrack(audioCtx, buf); audioSrc = t.src; tracks.push(t.dest.getAudioTracks()[0]); }
          }
          const stream = new MediaStream(tracks);
          recorder = new MediaRecorder(stream, { mimeType: mime, videoBitsPerSecond: bitrate });
          const chunks = [];
          recorder.ondataavailable = (e) => { if (e.data.size) chunks.push(e.data); };
          recorder.onstop = () => {
            const blob = new Blob(chunks, { type: mime });
            downloadBlob(blob, format === 'mp4' ? 'travel.mp4' : 'travel.webm');
            $('export-start').disabled = false;
          };
          recorder.start(200);
        }
      }

      // --- drive animation + capture -----------------------------------
      const start = performance.now();
      let lastCapture = 0, frameIndex = 0;
      const interval = 1000 / fps;

      await new Promise((resolve, reject) => {
        function frame(now) {
          const elapsed = now - start;
          const frac = Math.min(1, (elapsed * speedFactor) / D);
          TM.update(frac);
          drawComposite(ctx2d, W, H, opts, frac, elapsed, totalMs);

          if (videoEncoder) {
            if (elapsed - lastCapture >= interval) {
              lastCapture = elapsed;
              const f = new VideoFrame(composite, { timestamp: Math.round(frameIndex * 1e6 / fps), duration: Math.round(1e6 / fps) });
              videoEncoder.encode(f, { keyFrame: frameIndex % (fps * 2) === 0 });
              f.close();
              frameIndex++;
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
          if (videoEncoder) {
            await videoEncoder.flush();
            muxer.finalize();
            const buf = muxer.target.buffer;
            downloadBlob(new Blob([buf], { type: 'video/mp4' }), 'travel.mp4');
            $('export-start').disabled = false;
          } else if (gif) {
            gif.render();
          } else if (recorder) {
            recorder.stop();
          }
          if (audioSrc) audioSrc.stop();
          if (audioCtx) audioCtx.close();
          resolve();
        } catch (e) { reject(e); }
      }

      // GIF completes asynchronously in its 'finished' handler; other formats
      // are done synchronously here.
      if (format !== 'gif') setStatus('Готово — файл можно скачать.', 100);
    } catch (e) {
      console.error(e);
      setStatus('Ошибка: ' + e.message, 0);
      $('export-start').disabled = false;
      if (audioSrc) audioSrc.stop();
      if (audioCtx) audioCtx.close();
    } finally {
      // leave animation paused at the end
      TM.state.playing = false;
      TM.state.baseFrac = 1;
    }
  }

  // ----- wire UI ------------------------------------------------------------
  $('btn-export').addEventListener('click', () => $('export-modal').classList.remove('hidden'));
  $('export-close').addEventListener('click', () => $('export-modal').classList.add('hidden'));
  $('export-cancel').addEventListener('click', () => $('export-modal').classList.add('hidden'));
  $('export-start').addEventListener('click', startExport);

  $('exp-format').addEventListener('change', () => {
    const f = $('exp-format').value;
    $('exp-bitrate').parentElement.style.display = f === 'gif' ? 'none' : '';
  });
})();
