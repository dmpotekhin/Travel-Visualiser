#!/usr/bin/env python3
"""Controlled test: does this vendored gif.js preserve canvas content?
Draw a red square, encode 1-frame GIF, decode, check red pixels."""
import subprocess, time, urllib.request, os, sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SERVER = "http://127.0.0.1:8000"


def server_up():
    try:
        urllib.request.urlopen(SERVER + "/", timeout=2)
        return True
    except Exception:
        return False


def main():
    proc = None
    if not server_up():
        proc = subprocess.Popen([sys.executable, "main.py"], cwd=BASE,
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(60):
            if server_up():
                break
            time.sleep(1)

    from playwright.sync_api import sync_playwright
    try:
        with sync_playwright() as p:
            b = p.chromium.launch(headless=True)
            page = b.new_page()
            page.goto(SERVER + "/", wait_until="load")
            res = page.evaluate(
                """async () => {
                  // load vendor scripts manually
                  await new Promise((res, rej) => {
                    const s = document.createElement('script');
                    s.src = '/vendor/gif.js'; s.onload = res; s.onerror = () => rej(new Error('gif.js'));
                    document.head.appendChild(s);
                  });
                  const W = 64, H = 64;
                  const c = document.createElement('canvas'); c.width = W; c.height = H;
                  const ctx = c.getContext('2d');
                  ctx.fillStyle = '#00ff00';
                  ctx.fillRect(0, 0, W, H);
                  ctx.fillStyle = '#ff0000';
                  ctx.fillRect(20, 20, 24, 24);   // red square at center
                  const g = new GIF({ workers: 1, quality: 10, width: W, height: H, workerScript: '/vendor/gif.worker.js' });
                  g.addFrame(c, { copy: true, delay: 50 });
                  const finishedP = new Promise((res) => g.on('finished', res));
                  g.render();
                  const finished = await finishedP;
                  // decode
                  const dec = new ImageDecoder({ type: 'image/gif', data: await finished.arrayBuffer() });
                  const out = await dec.decode();
                  const img = out.image;
                  const cv = document.createElement('canvas'); cv.width = W; cv.height = H;
                  const c2 = cv.getContext('2d');
                  c2.drawImage(img, 0, 0);
                  img.close();
                  const d = c2.getImageData(0, 0, W, H).data;
                  let red = 0, green = 0;
                  for (let i = 0; i < d.length; i += 4) {
                    if (d[i] > 200 && d[i+1] < 100 && d[i+2] < 100) red++;
                    if (d[i+1] > 200 && d[i] < 100) green++;
                  }
                  return { red, green, size: finished.size };
                }"""
            )
            print("gif.js controlled test:", res)
            b.close()
    finally:
        if proc:
            proc.terminate()


if __name__ == "__main__":
    main()
