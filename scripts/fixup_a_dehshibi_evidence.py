"""
fixup_a_dehshibi_evidence.py
============================
The evidence for fixup-a items 1-3: run the `dehshibi_spikes` template through
a RUNNING BRIDGE over a short span and over a long one from the same channel,
and screenshot the stage-1 pane each time.

Why a script and not a paragraph: the Dehshibi stage-1 image was uniformly
black with `value_range: [0, 1]` on every real span, and every unit test in the
repo used a synthetic small enough that the serialiser's block factor was 1 --
which is exactly the condition under which the defect cannot appear. Only a
real span through the real bridge shows it, so only a real span can show it
fixed.

    "/c/ProgramData/anaconda3/python.exe" scripts/fixup_a_dehshibi_evidence.py \\
        --url http://127.0.0.1:8765 --out webui/screenshots/fixup/A

The bridge must be running in `--sandbox` (the default). Nothing here writes to
the real DATA/ tree.
"""
from __future__ import annotations

import argparse
import json
import os
import urllib.request

HOURS = 3600.0
#: The two spans, from one channel of one recording. The short one is under the
#: block's `max_span_samples` and must paint; the long one is over it and must
#: be refused in words (fixup-a item 2 derived the cap: 65,000 samples).
SHORT_H = 4.0
LONG_H = 170.0


def _get(url: str):
    with urllib.request.urlopen(url, timeout=60) as r:
        return json.load(r)


def pick_channel(url: str) -> dict:
    """A channel long enough for the 170 h span, on a recording that is not held out."""
    best = None
    for f in _get(f"{url}/api/recordings"):
        if f.get("held_out"):
            continue
        if (f.get("duration_h") or 0) < LONG_H + 1:
            continue
        for ch in f.get("channels", []):
            if best is None:
                best = {"id": ch["id"], "name": ch["name"], "file": f["source_file"],
                        "fs": f["fs"], "duration_h": f["duration_h"]}
    if best is None:
        raise SystemExit(f"no channel on this database is longer than {LONG_H} h")
    return best


def chain(url: str):
    tpl = _get(f"{url}/api/templates")
    for t in (tpl if isinstance(tpl, list) else tpl.get("templates", [])):
        if t.get("name") == "dehshibi_spikes":
            return t["steps"]
    raise SystemExit("the dehshibi_spikes template is not in the registry")


def shoot(url: str, out_dir: str, ch: dict, steps, hours: float, tag: str) -> dict:
    from playwright.sync_api import sync_playwright

    fs = float(ch["fs"])
    start = 0
    end = int(round(hours * HOURS * fs))
    source = {"recording_id": ch["id"], "channel_name": ch["name"], "source_file": ch["file"],
              "fs": fs, "start_idx": start, "end_idx": end, "label": f"fixup-a evidence {hours:g} h"}
    errors: list[str] = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        page.on("console", lambda m: errors.append(f"console.{m.type}: {m.text}") if m.type == "error" else None)
        page.on("pageerror", lambda e: errors.append(f"pageerror: {e}"))
        page.goto(f"{url}/#/analyse/chain", wait_until="networkidle")
        page.evaluate(
            """([src, steps]) => {
                 sessionStorage.setItem('ub-proto-a:source', JSON.stringify(src));
                 sessionStorage.setItem('ub-proto-a:chain', JSON.stringify(
                   { name: 'dehshibi_spikes', saved: false, lastRunJobId: null, steps }));
               }""", [source, steps])
        page.reload(wait_until="networkidle")
        page.wait_for_timeout(1500)
        run = page.locator('[data-testid="run-button"]')
        note = ""
        if run.count() and run.first.is_enabled():
            run.first.click()
            for _ in range(600):                        # up to 5 minutes
                page.wait_for_timeout(500)
                ft = page.locator('[data-testid="footer-terminal"]')
                text = ft.inner_text().lower() if ft.count() else ""
                if "last run" in text or "no result" in text or "failed" in text:
                    break
        else:
            note = run.first.get_attribute("title") if run.count() else "no run button"
        page.wait_for_timeout(800)
        os.makedirs(out_dir, exist_ok=True)
        path = os.path.join(out_dir, f"dehshibi-stage1-{tag}.png")
        page.screenshot(path=path, full_page=False)
        body = page.locator("body").inner_text()
        browser.close()
    return {"hours": hours, "samples": end - start, "screenshot": path,
            "run_disabled_reason": note, "console_errors": errors,
            "says_refused": "max_span_samples" in body or "exceeds" in body,
            "says_no_data": "no data" in body.lower() or "every cell" in body.lower()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:8765")
    ap.add_argument("--out", default=os.path.join("webui", "screenshots", "fixup", "A"))
    a = ap.parse_args()
    rt = _get(f"{a.url}/api/runtime")
    if rt.get("mode") != "sandbox":
        raise SystemExit(f"refusing to run against mode={rt.get('mode')!r}: use --sandbox")
    ch = pick_channel(a.url)
    steps = chain(a.url)
    print("channel:", ch)
    out = [shoot(a.url, a.out, ch, steps, SHORT_H, "short-4h"),
           shoot(a.url, a.out, ch, steps, LONG_H, "long-170h")]
    print(json.dumps({"channel": ch, "runs": out}, indent=2))
    with open(os.path.join(a.out, "evidence.json"), "w", encoding="utf-8") as f:
        json.dump({"channel": ch, "runs": out}, f, indent=2)


if __name__ == "__main__":
    main()
