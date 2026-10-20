"""
demo_screenshots.py
===================
Screenshot every step of the live talk (docs/DEMO_DAY.md) at 1920x1080, for the
backup deck in case the live demo fails on the day.

    PYTHONIOENCODING=utf-8 "/c/ProgramData/anaconda3/python.exe" scripts/demo_screenshots.py \
        --url http://127.0.0.1:8765 --out docs/demo/shots

Page visits plus the same clicks the talk makes. On the project bridge those
clicks re-run chains that are already in the step cache, so they write nothing
new except a run row per chain run (as any Analyse run does). Playwright, dev
tooling only.
"""
from __future__ import annotations

import argparse
import os
import time

SPAN = "[1357200, 1371600]"  # M2_aug CH4_A2 (recording 4), hours 377-381: the saved span "demo · W1/W2 span"

# Run a chain from a saved template: open Import, search, pick, Run chain, wait for its footer.
IMPORT_AND_RUN = """async (name) => {
  const B = t => [...document.querySelectorAll('button')].find(b => b.innerText.trim().startsWith(t));
  B('⤓ Import').click(); await new Promise(r => setTimeout(r, 1200));
  const inp = document.querySelector('input[placeholder*="search by name"]');
  Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set.call(inp, name);
  inp.dispatchEvent(new Event('input', { bubbles: true })); await new Promise(r => setTimeout(r, 800));
  const row = [...document.querySelectorAll('button,[role=option],li,div')]
    .filter(e => e.children.length < 6 && new RegExp('^' + name + '\\\\b').test(e.innerText?.trim() || '')).pop();
  row.click(); await new Promise(r => setTimeout(r, 1500));
  [...document.querySelectorAll('button')].find(b => /Run chain/.test(b.innerText)).click();
  for (let i = 0; i < 120; i++) { await new Promise(r => setTimeout(r, 1000));
    const t = document.body.innerText; if (/last run/.test(t) && t.includes('imported ' + name) && !/running ·|queued/.test(t)) return true }
  return false }"""

OPEN_SPAN_IN_ANALYSE = """async () => {
  [...document.querySelectorAll('button')].find(b => b.innerText.trim() === 'Open in Analyse').click();
  await new Promise(r => setTimeout(r, 3000)); return location.hash }"""

# (file name, hash or None to stay, JS to run before the shot, full page?)
STEPS = [
    ("w1-1-corpus", "explore/corpus", None, False),
    ("w1-2-signal-span", "explore/signal/4", None, False),
    ("w1-3-analyse-source", None, OPEN_SPAN_IN_ANALYSE, False),
    ("w1-4-spike-event-features", None, ("spike_event_features", IMPORT_AND_RUN), True),
    ("w1-5-cwt-events", None, ("cwt_events", IMPORT_AND_RUN), True),
    ("w2-1-drop-detector-chain", None, ("drop_detection_v1", IMPORT_AND_RUN), True),
    ("w2-2-template-saved", "library/templates", None, False),
    ("w2-3-discovery-runs", "discovery/runs", None, False),
    ("w2-4-report", "reports/detection-run/demo%20%C2%B7%20drop%20detector", None, True),
    ("w2-5-review", "review/queue/30", None, False),
    ("w3-1-atlas", "library/atlas?grouping=g-05", None, False),
    ("w3-2-family-F-30", "library/family/F-30?grouping=g-05", None, False),
    ("w3-3-seed-search", "discovery/seed?entry=191&step=3", None, False),
    ("w3-4-seed-kept", "discovery/seed?entry=191&step=4", None, False),
    ("w3-5-review", "review/queue/31", None, False),
    ("w3-6-report", "reports/detection-run/seed_056a5d", None, True),
    ("r1-1-map-overview", "discovery/map", None, False),
    *[(f"r1-2-map-{d}", f"discovery/map?dataset={d}", None, False)
      for d in ("M2_aug_concat_fs1", "M2_concat_fs1", "CO_fs2", "LM_fs2", "L_LM_Jul_26_J_raw",
                "L_LM_Jul_26_J_raw_fs2", "M4_aug_concat_fs1")],
    ("r2-1-dip-search-allch-report", "reports/detection-run/dip_search_allch", None, True),
    ("r2-2-seed-bdd3d0-report", "reports/detection-run/seed_bdd3d0", None, True),
    ("r2-3-reports-list", "reports", None, False),
]


def settle(page, quiet_s=2.0, cap_s=180.0):
    """Wait until no /api request has been open for `quiet_s`."""
    open_ = set()
    page.on("request", lambda r: "/api/" in r.url and open_.add(r))
    for ev in ("requestfinished", "requestfailed"):
        page.on(ev, lambda r: open_.discard(r))
    t0 = last = time.perf_counter()
    while time.perf_counter() - t0 < cap_s:
        page.wait_for_timeout(250)
        if open_:
            last = time.perf_counter()
        elif time.perf_counter() - last >= quiet_s:
            break
    page.wait_for_timeout(800)  # let the charts paint


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--url", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--only", default=None, help="only steps whose name starts with this")
    a = ap.parse_args()
    url = a.url.rstrip("/")
    os.makedirs(a.out, exist_ok=True)
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(viewport={"width": 1920, "height": 1080})
        page.goto(f"{url}/#/explore/corpus")
        for name, route, js, full in STEPS:
            if a.only and not name.startswith(a.only) and not name.startswith("w1-2") and not name.startswith("w1-3"):
                continue
            t0 = time.perf_counter()
            if route:
                page.goto(f"{url}/#/{route}")
                if route == "explore/signal/4":
                    # Signal opens on the view this tab remembers; Corpus resets it, so set it last and reload
                    page.evaluate(f"""() => sessionStorage.setItem('ub-proto-a:explore',
                        JSON.stringify({{file: null, channelId: 4, view: {SPAN}, colourBy: 'both'}}))""")
                    page.reload()
                settle(page)
            if js:
                ok = page.evaluate(js[1], js[0]) if isinstance(js, tuple) else page.evaluate(js)
                settle(page)
                if ok is False:
                    print(f"  {name}: the chain did not finish in time")
            page.screenshot(path=os.path.join(a.out, f"{name}.png"), full_page=full)
            print(f"{time.perf_counter() - t0:6.1f} s  {name}", flush=True)
        browser.close()


if __name__ == "__main__":
    main()
