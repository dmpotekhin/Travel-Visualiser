#!/usr/bin/env python3
"""Debug: what is actually in the exported GIF frames?"""
import subprocess, time, urllib.request, os, sys, json, base64

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
            page = b.new_page(viewport={"width": 1280, "height": 800})
            console_msgs = []
            page.on("console", lambda m: console_msgs.append(f"{m.type}: {m.text}"))

            def stub_openfreemap(route):
                url = route.request.url
                if url.endswith("/planet") or "/planet?" in url:
                    route.fulfill(status=200, content_type="application/json",
                                  body='{"tilejson":"3.0.0","tiles":["https://tiles.openfreemap.org/planet/{z}/{x}/{y}.pbf"],"minzoom":0,"maxzoom":14}')
                else:
                    route.fulfill(status=200, content_type="application/octet-stream", body=b"")

            page.route("**tiles.openfreemap.org/**", stub_openfreemap)
            page.goto(SERVER + "/", wait_until="load")
            page.click('form[action="/animate"] button[type="submit"]')
            page.wait_for_url("**/animate", timeout=30000)
            page.wait_for_function("() => window.TravelMap && window.TravelMap.getMarkerLngLat", timeout=30000)
            page.wait_for_function("() => window.TravelMap.getMap().getSource && window.TravelMap.getMap().getSource('route')", timeout=30000)
            page.wait_for_timeout(800)

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
                  await new Promise((res, rej) => { img.onload = res; img.onerror = () => rej(new Error('decode')); img.src = url; });
                  const c = document.createElement('canvas'); c.width = W; c.height = H;
                  const ctx = c.getContext('2d');
                  ctx.drawImage(img, 0, 0, W, H);
                  const d = ctx.getImageData(0, 0, W, H).data;
                  // find non-cream pixels bbox + count + sample colors
                  let minX = W, minY = H, maxX = 0, maxY = 0, n = 0;
                  const hist = {};
                  for (let y = 0; y < H; y++) {
                    for (let x = 0; x < W; x++) {
                      const i = (y * W + x) * 4;
                      const diff = Math.abs(d[i]-246)+Math.abs(d[i+1]-239)+Math.abs(d[i+2]-224);
                      if (diff > 25) {
                        n++; if (x<minX)minX=x; if (x>maxX)maxX=x; if (y<minY)minY=y; if (y>maxY)maxY=y;
                        const key = Math.round(d[i]/40)+','+Math.round(d[i+1]/40)+','+Math.round(d[i+2]/40);
                        hist[key] = (hist[key]||0)+1;
                      }
                    }
                  }
                  // marker projected pos at end, current camera
                  const TM = window.TravelMap;
                  const map = TM.getMap();
                  const pt = map.project(TM.coords[TM.coords.length-1]);
                  const cssW = map.getContainer().clientWidth;
                  const sw = map.getCanvas().width;
                  const k = (sw * Math.max(W/sw, H/map.getCanvas().height)) / cssW;
                  return {
                    n, bbox: n ? [minX, minY, maxX, maxY] : null,
                    hist: Object.entries(hist).sort((a,b)=>b[1]-a[1]).slice(0,10),
                    endProject: [Math.round(pt.x*k), Math.round(pt.y*k)],
                    gifW: img.naturalWidth, gifH: img.naturalHeight, size: blob.size,
                    marker: {
                      emoji: TM.getMarkerEmoji(),
                      lngLat: TM.getMarkerLngLat() ? TM.getMarkerLngLat().lng + ',' + TM.getMarkerLngLat().lat : null,
                      end: TM.coords[TM.coords.length-1],
                    },
                  };
                }"""
            )
            print(json.dumps(res, ensure_ascii=False, indent=1))
            # Sample the last composite frame directly (pre-GIF) at marker pos
            comp = page.evaluate(
                """() => {
                  const c = window.__lastComposite;
                  if (!c) return { missing: true };
                  const W = c.width, H = c.height;
                  const ctx = c.getContext('2d');
                  const d = ctx.getImageData(0, 0, W, H).data;
                  const TM = window.TravelMap;
                  const map = TM.getMap();
                  const pt = map.project(TM.coords[TM.coords.length-1]);
                  const cssW = map.getContainer().clientWidth;
                  const sw = map.getCanvas().width, sh = map.getCanvas().height;
                  const scale = Math.max(W/sw, H/sh);
                  const dw = sw*scale;
                  const k = dw/cssW;
                  const cx = (W-dw)/2 + pt.x*k;
                  const cy = (H - sh*scale)/2 + pt.y*k;
                  const iconCy = cy - 4*k;
                  let n = 0;
                  for (let y = Math.round(iconCy-20*k); y < Math.round(iconCy-4*k); y++) {
                    for (let x = Math.round(cx-28*k); x < Math.round(cx+28*k); x++) {
                      if (x<0||y<0||x>=W||y>=H) continue;
                      const i = (y*W+x)*4;
                      const diff = Math.abs(d[i]-246)+Math.abs(d[i+1]-239)+Math.abs(d[i+2]-224);
                      if (diff > 45) n++;
                    }
                  }
                  return { markerPxDirect: n, cx: Math.round(cx), iconCy: Math.round(iconCy), k, W, H };
                }"""
            )
            print("composite direct sample:", comp)
            # ASCII-render GIF frame 0 around the first marker position
            ascii_art = page.evaluate(
                """async () => {
                  const a = document.getElementById('export-download');
                  const blob = await fetch(a.href).then(r => r.blob());
                  const url = URL.createObjectURL(blob);
                  const img = new Image();
                  await new Promise((res, rej) => { img.onload = res; img.onerror = () => rej(new Error('gif decode failed')); img.src = url; });
                  const W = 640, H = 360;
                  const c = document.createElement('canvas'); c.width = W; c.height = H;
                  const ctx = c.getContext('2d');
                  ctx.drawImage(img, 0, 0, W, H);
                  const fp = window.__firstMarkerPos || [287, 162];
                  const x0 = Math.round(fp[0] - 40), y0 = Math.round(fp[1] - 25);
                  const w = 80, h = 50;
                  const d = ctx.getImageData(Math.max(0, x0), Math.max(0, y0), w, h).data;
                  let art = '';
                  for (let y = 0; y < h; y++) {
                    for (let x = 0; x < w; x++) {
                      const i = (y * w + x) * 4;
                      const diff = Math.abs(d[i]-246)+Math.abs(d[i+1]-239)+Math.abs(d[i+2]-224);
                      if (diff > 45) art += '#';
                      else if (diff > 20) art += '+';
                      else art += '.';
                    }
                    art += '\\n';
                  }
                  return { x0, y0, art };
                }"""
            )
            print("ASCII frame0 around firstPos:")
            print(ascii_art["art"])
            print("x0,y0:", ascii_art["x0"], ascii_art["y0"])
            print("=== DEBUG-marker console ===")
            for m_ in console_msgs:
                if "DEBUG-marker" in m_:
                    print(" ", m_)
            b.close()
    finally:
        if proc:
            proc.terminate()


if __name__ == "__main__":
    main()
