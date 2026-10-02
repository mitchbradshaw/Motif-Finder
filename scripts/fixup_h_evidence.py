"""
fixup_h_evidence.py
====================
Evidence for fixup H: what each block draws, before and after, at both tiers.

One block per output type - all seven - is run on the example span through the
bridge's own pages (import a canonical template, use the example span, run), and
two pictures are taken of each: its row on the chain page (the thumbnail tier) and
its block page (the settings tier).

    python scripts/fixup_h_evidence.py shots URL LABEL      # LABEL is `before` or `after`
    python scripts/fixup_h_evidence.py store URL LABEL      # the Interrogation member grid on the seed store,
                                                            #   and rule 9 measured on every tile of it
    python scripts/fixup_h_evidence.py split URL            # a WindowSet with no features (after only)
    python scripts/fixup_h_evidence.py capped               # capped-edge counts on the seed store (md + json)

Run it against a `--sandbox` bridge. Writes under webui/screenshots/fixup/H/ (or $H_OUT). Dev tooling.
"""
import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

OUT = os.environ.get("H_OUT") or os.path.join(REPO, "webui", "screenshots", "fixup", "H")

#: (template, seconds to wait for the run, [(step index, output type, block)]) - the blocks
#: photographed. Between them the seven output types, and the conversions that invert the
#: rule (spanset -> spanset) or need two thumbnails (signal -> windowset).
CHAINS = [
    ("mp_threshold", 60, [(0, "signal", "detrend"), (1, "scores", "matrix_profile"), (2, "spanset", "threshold")]),
    ("dsax_encoding", 30, [(1, "encoding", "sax_dsax")]),
    ("dehshibi_spikes", 90, [(0, "encoding", "wavelet_transform"), (1, "scores", "wavelet_summation"),
                             (2, "spanset", "summation_threshold")]),
    ("windows_model", 120, [(0, "windowset", "window_matrix"), (1, "grouping", "cluster"), (2, "model", "classifier")]),
    ("drop_event_features", 120, [(2, "spanset", "drop_detection"), (3, "spanset", "event_shape"),
                                  (4, "spanset", "intervals")]),
]

#: Seed families photographed on the Interrogation source block, and why each. id024 has 12
#: windows the store counted more than one fall in (the impurity flag) and 35 of 40 capped
#: edges. id025 is the widest family of the store in amplitude: its members' depths span
#: 7.5 to 75 mV - one order of magnitude, the most a seed family can span, because the
#: detector's own `min_depth_frac = 0.10` drops anything shallower than a tenth of the deepest.
STORE_FAMILIES = {"id024": "impurity", "id025": "per-panel-scale"}

#: A trace's drawn height as a fraction of its panel, for every tile of the member grid. Works on
#: both builds: the old grid is `MiniTrace` on a viewBox (the path's own box is measured, not its
#: `d`), the new one is the slideshow's `EventTrace`.
_FILL_JS = """() => {
  const grid = document.querySelector('[data-testid="member-grid"]');
  if (!grid) return null;
  const out = [];
  for (const svg of grid.querySelectorAll('svg')) {
    if (!svg.hasAttribute('data-plot-box')) continue;
    const b = svg.getBoundingClientRect();
    const paths = svg.querySelectorAll('[data-trace] path');
    const p = paths[paths.length - 1];
    if (!p || !b.height) continue;
    out.push(p.getBoundingClientRect().height / b.height);
  }
  return out;
}"""


def _browser():
    from playwright.sync_api import sync_playwright
    return sync_playwright()


def _page(p, errors):
    b = p.chromium.launch()
    page = b.new_page(viewport={"width": 1500, "height": 1100})
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    page.on("pageerror", lambda e: errors.append(str(e)))
    return b, page


def _run_template(page, url, template, wait_s):
    page.goto(f"{url}/#/analyse/chain", wait_until="networkidle")
    page.wait_for_selector('[data-testid="chain-page"]', timeout=20000)
    page.wait_for_timeout(600)
    page.keyboard.press("Escape")
    page.locator('[data-testid="import-button"]').first.click()
    page.wait_for_timeout(500)
    page.locator(f'[data-testid="template-{template}"]').first.click()
    page.wait_for_timeout(700)
    if page.locator('[data-testid="use-example"]').count():
        page.locator('[data-testid="use-example"]').first.click()
        page.wait_for_timeout(900)
    _run(page, wait_s)


def _run(page, wait_s):
    page.locator('[data-testid="run-button"]').first.click()
    for _ in range(wait_s * 4):
        page.wait_for_timeout(250)
        ft = page.locator('[data-testid="footer-terminal"]')
        txt = ft.inner_text().lower() if ft.count() else ""
        if not page.locator('[data-testid="cancel-button"]').count() and ("last run" in txt or "failed" in txt or "no result" in txt):
            break
    page.wait_for_timeout(1200)


def shots(url, label):
    os.makedirs(OUT, exist_ok=True)
    errors = []
    with _browser() as p:
        b, page = _page(p, errors)
        for template, wait_s, blocks in CHAINS:
            _run_template(page, url, template, wait_s)
            page.screenshot(path=os.path.join(OUT, f"{label}-chain-{template}.png"), full_page=True)
            print("wrote", f"{label}-chain-{template}.png")
            for i, kind, block in blocks:
                row = page.locator(f'[data-testid="chain-row-{i + 1}"]')
                if row.count():
                    row.first.scroll_into_view_if_needed()
                    row.first.screenshot(path=os.path.join(OUT, f"{label}-thumbnail-{kind}-{block}.png"))
            for i, kind, block in blocks:
                page.goto(f"{url}/#/analyse/block/{i}", wait_until="networkidle")
                page.wait_for_selector('[data-testid="block-page"]', timeout=20000)
                page.wait_for_timeout(3500)
                name = f"{label}-settings-{kind}-{block}.png"
                page.screenshot(path=os.path.join(OUT, name), full_page=True)
                print("wrote", name)
        b.close()
    _done(errors)


def store(url, label):
    """The member grid of two seed families, and how much of its panel each tile's trace fills."""
    os.makedirs(OUT, exist_ok=True)
    errors, fills = [], {}
    with _browser() as p:
        b, page = _page(p, errors)
        for fam, why in STORE_FAMILIES.items():
            page.goto(f"{url}/#/analyse/interrogation?family={fam}", wait_until="networkidle")
            page.wait_for_selector('[data-testid="member-grid"]', timeout=30000)
            page.wait_for_timeout(2500)
            name = f"{label}-slideshow-{why}-{fam}.png"
            page.locator('[data-testid="source-block"]').screenshot(path=os.path.join(OUT, name))
            print("wrote", name)
            f = page.evaluate(_FILL_JS) or []
            fills[fam] = {"tiles": len(f), "fill": [round(x, 3) for x in f],
                          "below_20_percent": sum(1 for x in f if x < 0.2),
                          "median": round(sorted(f)[len(f) // 2], 3) if f else None}
            print(fam, fills[fam])
        b.close()
    path = os.path.join(OUT, "rule9-member-grid.json")
    have = json.load(open(path, encoding="utf-8")) if os.path.isfile(path) else {}
    have[label] = fills
    with open(path, "w", encoding="utf-8") as f:
        json.dump(have, f, indent=2)
    _done(errors)


def split(url):
    """`preprocessing.sliding_windows` carries no features: its windows by train / validation / test."""
    os.makedirs(OUT, exist_ok=True)
    errors = []
    chain = {"name": "sliding_windows", "saved": False, "lastRunJobId": None,
             "steps": [{"stage": "preprocessing", "algorithm": "sliding_windows",
                        "params": {"window_s": 300.0, "n_blocks": 6, "holdout_frac": 0.2, "validation_frac": 0.2}}]}
    with _browser() as p:
        b, page = _page(p, errors)
        page.goto(f"{url}/#/analyse/chain", wait_until="networkidle")
        page.evaluate("c => sessionStorage.setItem('ub-proto-a:chain', JSON.stringify(c))", chain)
        page.reload(wait_until="networkidle")
        page.wait_for_timeout(800)
        if page.locator('[data-testid="use-example"]').count():
            page.locator('[data-testid="use-example"]').first.click()
            page.wait_for_timeout(900)
        _run(page, 30)
        page.locator('[data-testid="chain-row-1"]').first.screenshot(path=os.path.join(OUT, "after-thumbnail-windowset-sliding_windows.png"))
        page.goto(f"{url}/#/analyse/block/0", wait_until="networkidle")
        page.wait_for_timeout(2500)
        page.screenshot(path=os.path.join(OUT, "after-settings-windowset-sliding_windows.png"), full_page=True)
        print("wrote after-*-windowset-sliding_windows.png")
        b.close()
    _done(errors)


def _done(errors):
    if errors:
        print("CONSOLE ERRORS:", errors[:20])
        sys.exit(1)


if __name__ == "__main__":
    if len(sys.argv) == 4 and sys.argv[1] == "shots":
        shots(sys.argv[2].rstrip("/"), sys.argv[3])
    elif len(sys.argv) == 4 and sys.argv[1] == "store":
        store(sys.argv[2].rstrip("/"), sys.argv[3])
    elif len(sys.argv) == 3 and sys.argv[1] == "split":
        split(sys.argv[2].rstrip("/"))
    elif len(sys.argv) == 2 and sys.argv[1] == "capped":
        from Working.Detection.drop_motifs import extent as X
        X.main(OUT)
    else:
        print(__doc__)
        sys.exit(2)
