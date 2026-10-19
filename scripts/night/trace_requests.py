"""trace_requests.py — night pass A: open one URL headless and print every /api/ request's start, end and status,
and when a data-testid paints. Usage: python scripts/night/trace_requests.py <url> [testid] [seconds-after]"""
import sys
import time

from playwright.sync_api import sync_playwright

url = sys.argv[1]
testid = sys.argv[2] if len(sys.argv) > 2 else "inspector"
after = float(sys.argv[3]) if len(sys.argv) > 3 else 3
if ":8765" in url or ":8766" in url:
    sys.exit("refusing 8765/8766")
with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    pg = b.new_page(viewport={"width": 1440, "height": 900})
    t0 = time.perf_counter()
    starts = {}
    pg.on("request", lambda r: "/api/" in r.url and starts.__setitem__(r, time.perf_counter()))

    def done(r):
        req = r.request
        if req in starts:
            path = req.url.split("/api/", 1)[1][:110]
            print(f"{starts[req] - t0:6.2f} -> {time.perf_counter() - t0:6.2f}  {r.status} /api/{path}", flush=True)
    pg.on("response", done)
    pg.on("requestfailed", lambda r: print("FAILED", r.url, r.failure, flush=True))
    pg.on("console", lambda m: m.type in ("error", "warning") and print("CONSOLE", m.type, m.text[:200], flush=True))
    pg.on("pageerror", lambda e: print("PAGEERROR", str(e)[:200], flush=True))
    pg.goto(url)
    try:
        pg.wait_for_selector(f'[data-testid="{testid}"]', timeout=120000)
        print("PAINT", round(time.perf_counter() - t0, 2), flush=True)
    except Exception as e:  # noqa: BLE001
        print("NO PAINT", str(e)[:200])
    pg.wait_for_timeout(after * 1000)
    b.close()
