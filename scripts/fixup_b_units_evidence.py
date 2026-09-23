"""
fixup_b_units_evidence.py
=========================
The evidence for fixup-b: the same Library family, the same Explore channel and
the same Review candidate, screenshotted through a RUNNING BRIDGE, with the
numbers each page prints read back off the DOM into `<out>/<tag>.json`.

Run it once before the change (`--tag before`) and once after (`--tag after`)
against a bridge restarted immediately beforehand, so both runs see the same
fresh sandbox copy of the database:

    "/c/ProgramData/anaconda3/python.exe" scripts/fixup_b_units_evidence.py \\
        --url http://127.0.0.1:8765 --out webui/screenshots/fixup/B --tag before

The bridge must be running in `--sandbox` (the default). Nothing here writes.

The pins are fixed rather than discovered, so the before and after pictures
are of the same things: Library family F-01 (M2_aug + Fig2A members), the
Fig2A-only family F-117, Explore channel 1 (M2_aug_concat_fs1 CH0), and Review
queue 2's first candidate (detection 100 on Mushroom_260720, recording 385).
"""
from __future__ import annotations

import argparse
import json
import os

PAGES = [
    ("library-atlas", "library/atlas", "[data-testid=atlas-scale-note]"),
    ("library-family-F-01", "library/family/F-01", "[data-testid=summary-trace-note]"),
    ("library-family-F-117", "library/family/F-117", "[data-testid=summary-trace-note]"),
    ("explore-signal-1", "explore/signal/1", "[data-testid=mv-labels]"),
    ("review-q2-item-100", "review/queue/2/100", None),
]


def _texts(page, selector: str) -> list[str]:
    try:
        loc = page.locator(selector)
        return [t.strip() for t in (loc.nth(i).text_content() or "" for i in range(loc.count())) if t.strip()]
    except Exception as e:                   # a missing selector is a fact about the page, said in words
        return [f"<{type(e).__name__}: {e}>"]


def shoot(url: str, out_dir: str, tag: str) -> dict:
    from playwright.sync_api import sync_playwright

    os.makedirs(out_dir, exist_ok=True)
    record: dict = {"tag": tag, "url": url, "pages": {}}
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        errors: list[str] = []
        page.on("console", lambda m: errors.append(f"console.{m.type}: {m.text}") if m.type == "error" else None)
        page.on("pageerror", lambda e: errors.append(f"pageerror: {e}"))
        for name, route, sel in PAGES:
            errors.clear()
            page.goto(f"{url}/#/{route}", wait_until="networkidle")
            page.wait_for_timeout(2500)
            path = os.path.join(out_dir, f"{tag}-{name}.png")
            page.screenshot(path=path, full_page=False)
            entry = {"route": route, "screenshot": os.path.relpath(path).replace(os.sep, "/"),
                     # every visible "mV" / "V" / "unit" string on the page: what the page claims
                     "unit_strings": sorted({t for t in _texts(page, "text=/\\bm?V\\b|unit/")})[:60],
                     "errors": list(errors)}
            if sel:
                entry["pinned"] = _texts(page, sel)
            record["pages"][name] = entry
        browser.close()
    with open(os.path.join(out_dir, f"{tag}.json"), "w", encoding="utf-8") as fh:
        json.dump(record, fh, indent=2)
    return record


SEED = os.path.join("DATA", "library_seed", "drop_motifs5", "motifs")


def depth_check(url: str, out_dir: str, families=("F-01", "F-02", "F-37", "F-64")) -> list[dict]:
    """For every member of `families` whose span IS a seed-store event's snippet span, the amplitude the app
    prints beside what the store recorded for the same samples.

    `app_mV` is `amplitudeMv` off the running bridge (peak-to-peak of the stored span, converted at the seam).
    `store_ptp_mV` is peak-to-peak of the store's own `__raw_mv` snippet — the same samples, which the detector
    wrote in mV. `before_mV` is what the pre-fixup-b bridge printed: peak-to-peak of the raw memmap slice with
    no conversion, recomputed here from the .npy. The detector's `drop_depth_mv` / `peak_to_peak_mv` are
    measured on the DETRENDED trace between onset and trough, so they are context, not the same number."""
    import csv
    import urllib.request

    import numpy as np

    def get(path):
        with urllib.request.urlopen(f"{url}{path}", timeout=120) as r:
            return json.load(r)

    recs = {}
    for f in get("/api/recordings"):
        for ch in f["channels"]:
            recs[(f["source_file"], ch["name"])] = ch["id"]
    with open(os.path.join(SEED, "events.csv"), encoding="utf-8") as fh:
        events = list(csv.DictReader(fh))
    by_span = {(int(e["recording_id"]), int(e["snippet_start_idx"]), int(e["snippet_end_idx"])): e for e in events}
    snips = np.load(os.path.join(SEED, "snippets.npz"))
    paths = {}
    rows = []
    for fam in families:
        detail = get(f"/api/library/family/{fam}")["detail"]
        for m in detail["members"]:
            start, end = (int(x) for x in m["revisions"][-1]["spanId"].split(":"))
            sf = next((k[0] for k in recs if k[1] == m["channel"] and m["recordingKey"] and k[0].startswith(m["recordingKey"].rsplit("_fs", 1)[0])), None)
            rid = recs.get((sf, m["channel"])) if sf else None
            ev = by_span.get((rid, start, end)) if rid else None
            if ev is None:
                continue
            if rid not in paths:
                paths[rid] = get(f"/api/channels/{rid}")["npy_path"]
            raw = np.load(paths[rid], mmap_mode="r")[start:end]
            rows.append({"family": fam, "member": m["id"], "event_id": ev["event_id"], "recording_id": rid,
                         "span": f"{start}:{end}", "before_mV": round(float(np.ptp(raw)), 6),
                         "app_mV": m["amplitudeMv"],
                         "store_ptp_mV": round(float(np.ptp(snips[ev["snippet_key"] + "__raw_mv"])), 4),
                         "drop_depth_mv": round(float(ev["drop_depth_mv"]), 4),
                         "peak_to_peak_mv": round(float(ev["peak_to_peak_mv"]), 4)})
    with open(os.path.join(out_dir, "depth-check.json"), "w", encoding="utf-8") as fh:
        json.dump(rows, fh, indent=2)
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--url", default="http://127.0.0.1:8765")
    ap.add_argument("--out", default=os.path.join("webui", "screenshots", "fixup", "B"))
    ap.add_argument("--tag", required=False)
    ap.add_argument("--depth", action="store_true", help="write depth-check.json instead of screenshots")
    a = ap.parse_args()
    if a.depth:
        rows = depth_check(a.url.rstrip("/"), a.out)
        agree = sum(1 for r in rows if r["app_mV"] is not None and abs(r["app_mV"] - r["store_ptp_mV"]) < 1e-3)
        print(f"{len(rows)} members matched a seed event; app == store for {agree}")
        for r in rows[:12]:
            print(r)
        return
    if not a.tag:
        ap.error("--tag is required unless --depth")
    rec = shoot(a.url.rstrip("/"), a.out, a.tag)
    for name, e in rec["pages"].items():
        print(f"{name}: {e.get('pinned')}  errors={len(e['errors'])}")


if __name__ == "__main__":
    main()
