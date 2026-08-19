#!/usr/bin/env python3
"""RED/GREEN e2e check: the recorded route video must contain the vehicle
marker (train/plane/car emoji) — it is a DOM overlay, absent from the WebGL
canvas, and is re-drawn by export.js drawMarker().

Usage:  python3 scripts/verify_marker_export.py
Exit 0 = marker pixels found in the exported GIF (GREEN).
Exit 1 = marker pixels missing (RED — bug present).
"""
import base64
import os
import subprocess
import sys
import time
import urllib.request

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SERVER = "http://127.0.0.1:8000"
THRESHOLD = 20  # min RED pixels (🚗 car body) in the marker box


def server_up() -> bool:
    try:
        urllib.request.urlopen(SERVER + "/", timeout=2)
        return True
    except Exception:
        return False


def main() -> int:
    from playwright.sync_api import sync_playwright

    proc = None
    if not server_up():
        print("server down — starting uvicorn...")
        proc = subprocess.Popen(
            [sys.executable, "main.py"], cwd=BASE,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        for _ in range(60):
            if server_up():
                break
            time.sleep(1)
        if not server_up():
            print("FAIL: server did not start")
            return 1

    res = None
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1280, "height": 800})

            console_msgs = []
            page.on("console", lambda m: console_msgs.append(f"{m.type}: {m.text}"))
            page_errors = []
            page.on("pageerror", lambda e: page_errors.append(str(e)))
            failed_reqs = []
            page.on("requestfailed", lambda r: failed_reqs.append(f"{r.url} :: {r.failure}"))
            slow_bad = []
            page.on(
                "response",
                lambda r: slow_bad.append(f"{r.status} {r.url}")
                if r.status >= 400
                else None,
            )

            # Deterministic offline run: external base-map tiles/glyphs hang in
            # headless Chromium here, which blocks the map 'load' event. Stub
            # them with a valid empty tilejson + blank tiles so the style loads
            # instantly; the route line/trail/cities are local GeoJSON sources.
            def stub_openfreemap(route):
                url = route.request.url
                if url.endswith("/planet") or "/planet?" in url:
                    route.fulfill(
                        status=200,
                        content_type="application/json",
                        body=(
                            '{"tilejson":"3.0.0",'
                            '"tiles":["https://tiles.openfreemap.org/planet/{z}/{x}/{y}.pbf"],'
                            '"minzoom":0,"maxzoom":14}'
                        ),
                    )
                else:
                    route.fulfill(status=200, content_type="application/octet-stream", body=b"")

            page.route("**tiles.openfreemap.org/**", stub_openfreemap)

            page.goto(SERVER + "/", wait_until="load")
            page.click('form[action="/animate"] button[type="submit"]')
            page.wait_for_url("**/animate", timeout=30000)
            try:
                page.wait_for_function(
                    "() => window.TravelMap && window.TravelMap.getMarkerLngLat",
                    timeout=30000,
                )
            except Exception:
                print("=== TRAVELMAP NOT READY — diagnostics ===")
                print("URL:", page.url)
                body = page.evaluate("() => document.body.innerText.slice(0, 500)")
                print("BODY:", body)
                print("CONSOLE:")
                for m in console_msgs[-25:]:
                    print(" ", m)
                print("PAGE ERRORS:")
                for e in page_errors[-10:]:
                    print(" ", e)
                raise
            try:
                page.wait_for_function(
                    "() => { const m = window.TravelMap.getMap(); return m.getSource && m.getSource('route'); }",
                    timeout=30000,
                )
            except Exception:
                print("=== MAP NOT LOADED / NO ROUTE SOURCE — diagnostics ===")
                diag = page.evaluate(
                    """() => {
                      const m = window.TravelMap.getMap();
                      return {
                        loaded: m.loaded ? m.loaded() : null,
                        styleLoaded: m.isStyleLoaded ? m.isStyleLoaded() : null,
                        styleObj: m.getStyle ? { layers: (m.getStyle().layers || []).length, sources: Object.keys(m.getStyle().sources || {}) } : null,
                        hasRoute: !!m.getSource('route'),
                        hasMarker: !!document.querySelector('.travel-marker'),
                      };
                    }"""
                )
                print("DIAG:", diag)
                print("FAILED REQUESTS:")
                for r_ in failed_reqs[-15:]:
                    print(" ", r_)
                print("HTTP >= 400:")
                for r_ in slow_bad[-15:]:
                    print(" ", r_)
                print("CONSOLE:")
                for m_ in console_msgs[-25:]:
                    print(" ", m_)
                print("PAGE ERRORS:")
                for e in page_errors[-10:]:
                    print(" ", e)
                raise

            page.wait_for_timeout(800)  # let WebGL render a frame

            info = page.evaluate(
                "() => ({ emoji: window.TravelMap.getMarkerEmoji(),"
                " rotation: window.TravelMap.getMarkerRotation(),"
                " hasLngLat: !!window.TravelMap.getMarkerLngLat(),"
                " segs: window.TravelMap.route.segments.length })"
            )
            print("marker api:", info)
            if info["emoji"] != "🚗":
                print("note: marker emoji is", repr(info["emoji"]))

            # configure export: small GIF, fast
            page.click("#btn-export")
            page.select_option("#exp-format", "gif")
            page.select_option("#exp-res", "640x360")
            page.select_option("#exp-fps", "15")
            page.select_option("#exp-speed", "4")
            page.click("#export-start")
            page.wait_for_selector("#export-download:not(.hidden)", timeout=240000)

            res = page.evaluate(
                """async () => {
                  const W = 640, H = 360;
                  const a = document.getElementById('export-download');
                  const blob = await fetch(a.href).then(r => r.blob());
                  const url = URL.createObjectURL(blob);
                  const img = new Image();
                  await new Promise((res, rej) => {
                    img.onload = res;
                    img.onerror = () => rej(new Error('gif decode failed'));
                    img.src = url;
                  });
                  const c = document.createElement('canvas');
                  c.width = W; c.height = H;
                  const ctx = c.getContext('2d');
                  ctx.drawImage(img, 0, 0, W, H);

                  // GIF frame 0 = first captured frame (frac ~0), marker at the
                  // START of the route. Its exact position was recorded by the
                  // first drawMarker() call (composite px).
                  const fp = window.__firstMarkerPos;
                  const TM = window.TravelMap;
                  const map = TM.getMap();
                  const src = map.getCanvas();
                  const sw = src.width, sh = src.height;
                  const scale = Math.max(W / sw, H / sh);
                  const dw = sw * scale, dh = sh * scale;
                  const cssW = map.getContainer().clientWidth || sw;
                  const k = dw / cssW;
                  const startPt = map.project(TM.coords[0]);
                  const mkCx = fp ? fp[0] : (W - dw) / 2 + startPt.x * k;
                  const mkIconCy = fp ? fp[1] : (H - dh) / 2 + startPt.y * k - 4 * k;

                  // Generous box around the icon. Signal: RED pixels — the
                  // 🚗 car body. The route line at the START is blue/white,
                  // so red pixels in this box only come from the marker.
                  const mkBox = { x: Math.round(mkCx - 25), y: Math.round(mkIconCy - 10), w: 55, h: 40 };
                  const count = (b, pred) => {
                    const x0 = Math.max(0, b.x), y0 = Math.max(0, b.y);
                    const w = Math.min(b.w, W - x0), h = Math.min(b.h, H - y0);
                    if (w <= 0 || h <= 0) return 0;
                    const d = ctx.getImageData(x0, y0, w, h).data;
                    let n = 0;
                    for (let i = 0; i < d.length; i += 4) {
                      if (pred(d[i], d[i + 1], d[i + 2])) n++;
                    }
                    return n;
                  };
                  const isRed = (r, g, b) => r > 170 && g < 130 && b < 130;
                  const isNonBg = (r, g, b) =>
                    Math.abs(r - 246) + Math.abs(g - 239) + Math.abs(b - 224) > 45;
                  const markerRed = count(mkBox, isRed);
                  const markerNonBg = count(mkBox, isNonBg);

                  const crop = document.createElement('canvas');
                  crop.width = mkBox.w; crop.height = mkBox.h;
                  const cctx = crop.getContext('2d');
                  cctx.drawImage(c, Math.max(0, mkBox.x), Math.max(0, mkBox.y), mkBox.w, mkBox.h, 0, 0, crop.width, crop.height);
                  return {
                    markerRed, markerNonBg, size: blob.size,
                    firstPos: fp, k,
                    debugPng: crop.toDataURL('image/png'),
                  };
                }"""
            )
            browser.close()
    finally:
        if proc:
            proc.terminate()

    print("RESULT:", {k: v for k, v in res.items() if k != "debugPng"})
    png = res.get("debugPng", "").split(",", 1)[-1]
    if png:
        with open("/tmp/marker_debug.png", "wb") as f:
            f.write(base64.b64decode(png))
        print("debug crop saved: /tmp/marker_debug.png")

    marker_red = res.get("markerRed", 0)
    marker_nonbg = res.get("markerNonBg", 0)
    print(f"marker red pixels in GIF frame0: {marker_red}, non-bg: {marker_nonbg} (threshold {THRESHOLD})")
    return 0 if marker_red >= THRESHOLD else 1


if __name__ == "__main__":
    sys.exit(main())
