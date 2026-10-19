"""night pass A: at a given viewport, list the elements wider than the viewport and their computed min-width.
Usage: python scripts/night/probe_width.py <url> [width] [height] [wait-testid]"""
import json
import sys

from playwright.sync_api import sync_playwright

url = sys.argv[1]
w = int(sys.argv[2]) if len(sys.argv) > 2 else 1024
h = int(sys.argv[3]) if len(sys.argv) > 3 else 700
tid = sys.argv[4] if len(sys.argv) > 4 else "inspector"
if ":8765" in url or ":8766" in url:
    sys.exit("refusing 8765/8766")
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": w, "height": h})
    pg.goto(url)
    pg.wait_for_selector(f'[data-testid="{tid}"]', timeout=180000)
    pg.wait_for_timeout(1500)
    out = pg.evaluate("""(vw) => [...document.querySelectorAll('body *')].map(e => {
        const r = e.getBoundingClientRect(); const cs = getComputedStyle(e);
        return { tag: e.tagName, cls: String(e.className).slice(0, 60), tid: e.getAttribute('data-testid'),
                 w: Math.round(r.width), right: Math.round(r.right), minW: cs.minWidth, flexShrink: cs.flexShrink } })
      .filter(x => x.right > vw + 2 && x.w > 300).slice(0, 25)""", w)
    print(json.dumps(out, indent=0))
    b.close()
