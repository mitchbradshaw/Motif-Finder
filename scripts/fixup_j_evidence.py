"""
fixup_j_evidence.py
===================
The `dehshibi_spikes` template run end to end through a RUNNING SANDBOX BRIDGE
on a span the researcher has labelled (M2_aug CH0, 81.7-85.0 h: eight
10-minute windows, four `interesting`), with a screenshot of the chain page
and of the third block's page — the funnel. The same span and the same
harness as `fixup_a_dehshibi_evidence.py`, which it borrows from.

    python scripts/fixup_j_evidence.py --url http://127.0.0.1:8766 --tag after

Check the bridge's banner says `CLIENT = ...` (a private build) first.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fixup_a_dehshibi_evidence import _get, chain  # noqa: E402

START_S, END_S = 294_000, 306_000          # 81.67 h .. 85.0 h, four 3000 s windows


def main():
    from playwright.sync_api import sync_playwright
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:8766")
    ap.add_argument("--out", default=os.path.join("webui", "screenshots", "fixup", "J"))
    ap.add_argument("--tag", default="after")
    a = ap.parse_args()
    rt = _get(f"{a.url}/api/runtime")
    if rt.get("mode") != "sandbox":
        raise SystemExit(f"refusing to run against mode={rt.get('mode')!r}: use --sandbox")
    ch = None
    for f in _get(f"{a.url}/api/recordings"):
        if f["source_file"] == "M2_aug_concat_fs1.mat" and not f.get("held_out"):
            c = f["channels"][0]
            ch = {"id": c["id"], "name": c["name"], "file": f["source_file"], "fs": f["fs"]}
    if ch is None:
        raise SystemExit("M2_aug is not registered on this database")
    steps = chain(a.url)
    fs = float(ch["fs"])
    source = {"recording_id": ch["id"], "channel_name": ch["name"], "source_file": ch["file"], "fs": fs,
              "start_idx": int(START_S * fs), "end_idx": int(END_S * fs), "label": "fixup-j evidence 81.7-85.0 h"}
    errors: list[str] = []
    os.makedirs(a.out, exist_ok=True)
    out = {"channel": ch, "span_s": [START_S, END_S], "client": rt.get("banner", "").split("CLIENT = ")[-1][:200]}
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 1100})
        page.on("console", lambda m: errors.append(f"console.{m.type}: {m.text}") if m.type == "error" else None)
        page.on("pageerror", lambda e: errors.append(f"pageerror: {e}"))
        page.goto(f"{a.url}/#/analyse/chain", wait_until="networkidle")
        page.evaluate(
            """([src, steps]) => {
                 sessionStorage.setItem('ub-proto-a:source', JSON.stringify(src));
                 sessionStorage.setItem('ub-proto-a:chain', JSON.stringify(
                   { name: 'dehshibi_spikes', saved: false, lastRunJobId: null, steps }));
               }""", [source, steps])
        page.reload(wait_until="networkidle")
        page.wait_for_timeout(1500)
        run = page.locator('[data-testid="run-button"]')
        if not (run.count() and run.first.is_enabled()):
            raise SystemExit(f"run is disabled: {run.first.get_attribute('title') if run.count() else 'no button'}")
        run.first.click()
        for _ in range(600):
            page.wait_for_timeout(500)
            ft = page.locator('[data-testid="footer-terminal"]')
            text = ft.inner_text().lower() if ft.count() else ""
            if "last run" in text or "no result" in text or "failed" in text:
                break
        page.wait_for_timeout(1000)
        page.screenshot(path=os.path.join(a.out, f"template-{a.tag}-chain.png"), full_page=True)
        out["footer"] = page.locator('[data-testid="footer-terminal"]').inner_text()[:400]
        page.goto(f"{a.url}/#/analyse/block/2", wait_until="networkidle")
        page.wait_for_timeout(2500)
        fn = page.locator('[data-testid="detector-funnel"]')
        out["funnel_present"] = bool(fn.count())
        if fn.count():
            out["funnel_summary"] = page.locator('[data-testid="funnel-summary"]').inner_text()
            fn.first.scroll_into_view_if_needed()
        page.screenshot(path=os.path.join(a.out, f"template-{a.tag}-block3.png"), full_page=True)
        browser.close()
    out["console_errors"] = errors
    print(json.dumps(out, indent=1))
    with open(os.path.join(a.out, f"template-{a.tag}.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1)


if __name__ == "__main__":
    main()
