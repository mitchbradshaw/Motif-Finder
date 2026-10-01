"""fixup-f evidence: the before/after screenshots of dataset naming.

    python scripts/fixup_f_evidence.py --url http://127.0.0.1:8765 --tag before
    python scripts/fixup_f_evidence.py --url http://127.0.0.1:8765 --tag after --name

Dev tooling (Playwright, conda python); nothing in the app imports it. Run it
against a ``--sandbox`` bridge only: ``--name`` WRITES dataset metadata through
``PUT /api/settings/datasets`` so the "after" shots have a display name to
show. Filling the real database's metadata is the researcher's, not this
script's.

Shots land in ``webui/screenshots/fixup/F/<tag>-<what>.png``.
"""
from __future__ import annotations

import argparse
import json
import os
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(os.path.dirname(HERE), "webui", "screenshots", "fixup", "F")

#: The names the "after" shots show. Illustrative, sandbox only.
NAMES = {
    "Mushroom_260720_0509_4hrs_CH14_fs1": {"display_name": "Lion's mane · 20 Jul · 4 h excerpt", "species": "Hericium erinaceus",
                                           "organism_id": "LM-J", "experiment_date": "2026-07-20", "condition": "baseline"},
    "M2_aug_concat_fs1": {"display_name": "M2 August · 1 Hz", "organism_id": "M2", "condition": "augmented concat"},
    "M2_concat_fs1": {"display_name": "M2 original · 1 Hz", "organism_id": "M2"},
}

#: (what, hash, viewport width, viewport height, selector to wait for)
SHOTS = [
    ("settings-datasets", "settings/datasets?rec=Mushroom_260720_0509_4hrs_CH14_fs1", 1440, 1100, '[data-testid="recordings-table"]'),
    ("settings-channels-wide", "settings/channels-events?rec=M2_aug_concat_fs1", 1440, 900, '[data-testid="channels-table"]'),
    ("settings-channels-narrow", "settings/channels-events?rec=M2_aug_concat_fs1", 900, 900, '[data-testid="channels-table"]'),
    ("settings-channels-L_LM", "settings/channels-events?rec=L_LM_Jul_26_J_raw_fs10", 1440, 900, '[data-testid="channels-table"]'),
    ("review-queue", "review/queue/2/102", 1440, 900, None),
    ("review-home", "review", 1440, 900, None),
    ("explore-corpus", "explore/corpus?rec=Mushroom_260720_0509_4hrs_CH14_fs1.mat", 1440, 900, None),
    ("explore-recording-menu", "explore/corpus?popover=recordings", 1440, 900, None),
    ("discovery-runs", "discovery/runs", 1440, 900, None),
    ("library-recurrence", "library/recurrence", 1440, 900, None),
    ("jobs", "jobs", 1440, 900, None),
    ("interrogation-source", "analyse/interrogation", 1440, 900, None),
    # U5: the picker, open, at a narrow and a wide viewport (the control does not exist before fixup-f)
    ("settings-channels-picker-narrow", "settings/channels-events?rec=M2_aug_concat_fs1", 900, 900, '[data-testid="rec-picker"]'),
    ("settings-channels-picker-wide", "settings/channels-events?rec=M2_aug_concat_fs1", 1440, 900, '[data-testid="rec-picker"]'),
]


def put_names(url: str) -> None:
    values = {f"meta.{stem}.{field}": v for stem, fields in NAMES.items() for field, v in fields.items()}
    req = urllib.request.Request(f"{url}/api/settings/datasets", method="PUT", headers={"content-type": "application/json"},
                                 data=json.dumps({"values": values}).encode())
    with urllib.request.urlopen(req, timeout=60) as r:
        print("named:", json.loads(r.read())["changed"])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:8765")
    ap.add_argument("--tag", required=True)
    ap.add_argument("--name", action="store_true", help="write the illustrative names first (sandbox only)")
    ap.add_argument("--only", default="")
    args = ap.parse_args()
    with urllib.request.urlopen(f"{args.url}/api/runtime", timeout=60) as r:
        rt = json.loads(r.read())
    if rt.get("mode") != "sandbox":
        raise SystemExit(f"refusing: the bridge at {args.url} is in {rt.get('mode')!r} mode, not sandbox")
    print("client:", rt.get("client_dist") or "the shared client/dist")
    if args.name:
        put_names(args.url)
    os.makedirs(OUT, exist_ok=True)
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for what, hash_, w, h, wait in SHOTS:
            if args.only and args.only not in what:
                continue
            page = browser.new_page(viewport={"width": w, "height": h})
            page.goto(f"{args.url}/#/{hash_}", wait_until="networkidle")
            if wait:
                page.wait_for_selector(wait, timeout=30000)
            page.wait_for_timeout(1500)
            if "picker" in what:
                page.click(wait)
                page.wait_for_timeout(500)
            path = os.path.join(OUT, f"{args.tag}-{what}.png")
            page.screenshot(path=path)
            print(path)
            page.close()
        browser.close()


if __name__ == "__main__":
    main()
