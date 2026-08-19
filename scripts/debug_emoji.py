#!/usr/bin/env python3
"""Quick check: does headless Chromium render color emoji into a 2D canvas?"""
import subprocess
import time
import urllib.request
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SERVER = "http://127.0.0.1:8000"


def server_up() -> bool:
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
                """() => {
                  const c = document.createElement('canvas');
                  c.width = 120; c.height = 120;
                  const ctx = c.getContext('2d');
                  ctx.fillStyle = '#f6efe0';
                  ctx.fillRect(0, 0, 120, 120);
                  // 1) plain emoji
                  ctx.font = '40px "Apple Color Emoji", "Segoe UI Emoji", sans-serif';
                  ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
                  ctx.fillText('🚗', 30, 30);
                  // 2) emoji + translate + rotate (as in drawMarker) + small font
                  ctx.save();
                  ctx.translate(80, 60);
                  ctx.rotate(134 * Math.PI / 180);
                  ctx.font = '15px "Apple Color Emoji", "Segoe UI Emoji", sans-serif';
                  ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
                  ctx.fillText('🚗', 0, 0);
                  ctx.restore();
                  const d = ctx.getImageData(0, 0, 120, 120).data;
                  const n1 = count(d, 0, 0, 60, 60);
                  const n2 = count(d, 60, 0, 60, 60);
                  function count(d, x0, y0, w, h) {
                    let n = 0;
                    for (let y = y0; y < y0 + h; y++) {
                      for (let x = x0; x < x0 + w; x++) {
                        const i = (y * 120 + x) * 4;
                        const diff = Math.abs(d[i]-246)+Math.abs(d[i+1]-239)+Math.abs(d[i+2]-224);
                        if (diff > 20) n++;
                      }
                    }
                    return n;
                  }
                  return { plain: n1, rotated_small: n2 };
                }"""
            )
            print("emoji canvas test:", res)
            b.close()
    finally:
        if proc:
            proc.terminate()


if __name__ == "__main__":
    main()
