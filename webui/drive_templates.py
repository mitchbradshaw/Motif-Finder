"""Drive one chain run of every canonical template on a real recording and screenshot the chain page.

    "/c/ProgramData/anaconda3/python.exe" webui/drive_templates.py --url http://127.0.0.1:8767 \
        --recording 1 --span 1209600 1216800 --out webui/screenshots/wiring/01

Runs against a bridge started in ``--project`` mode (the real database): each template is applied
through ``POST /api/templates/{id}/apply``, started through ``POST /api/runs`` (a persisted job), the
chain page is attached to the job through its session-storage draft, and the rendered rows are
screenshotted once the run ends. Writes ``<out>/summary.json`` with per-template status, elapsed time,
detections written and the step summaries. Stage-3 wiring prompt 01 evidence.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
SS_KEY = "ub-proto-a"

# templates whose blocks refuse long spans get a shorter one (samples)
SPAN_CAP = {"gramian_gasf": 3600}
# the drop template's defaults are the reference span's autoderived parameters; nothing to override
OVERRIDES = {"windows_model": {0: {"window_min": 5.0, "step_frac": 1.0, "slow_entropy": False}, 1: {"k": 2}, 2: {"n_estimators": 20}}}


def api(url, path, body=None, method=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url + path, data=data, method=method or ("POST" if data else "GET"), headers={"content-type": "application/json"})
    with urllib.request.urlopen(req, timeout=600) as r:
        return json.loads(r.read().decode())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:8767")
    ap.add_argument("--recording", type=int, default=1)
    ap.add_argument("--span", type=int, nargs=2, default=[1209600, 1216800])
    ap.add_argument("--out", default=os.path.join(HERE, "screenshots", "wiring", "01"))
    ap.add_argument("--only", default=None)
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)

    rt = api(args.url, "/api/runtime")
    print("mode", rt["mode"], "db", rt["db_path"])
    recs = api(args.url, "/api/recordings")
    rec = next((c | {"source_file": f["source_file"], "fs": f["fs"]} for f in recs for c in f["channels"] if c["id"] == args.recording), None)
    assert rec, f"no recording {args.recording}"
    templates = [t for t in api(args.url, "/api/templates") if t["builtin"]]
    if args.only:
        templates = [t for t in templates if t["name"] in args.only.split(",")]
    summary = []

    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1500, "height": 1000})
        errors = []
        page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
        page.on("pageerror", lambda e: errors.append(str(e)))
        for t in templates:
            s0, s1 = args.span
            if t["name"] in SPAN_CAP:
                s1 = min(s1, s0 + SPAN_CAP[t["name"]])
            print(f"[{t['name']}] span {s0}-{s1} ...", flush=True)
            applied = api(args.url, f"/api/templates/{t['id']}/apply", {"recording_id": args.recording, "span": [s0, s1]})
            steps = applied["recipe"]["steps"]
            for i, ov in OVERRIDES.get(t["name"], {}).items():
                steps[i]["params"].update(ov)
            t0 = time.time()
            try:
                job = api(args.url, "/api/runs", {"recording_id": args.recording, "span": [s0, s1], "steps": steps, "px": 1200})
            except urllib.error.HTTPError as e:
                body = e.read().decode()
                summary.append({"template": t["name"], "status": "refused", "http": e.code, "detail": body[:400]})
                print("  refused:", e.code, body[:200])
                continue
            jid = job["job_id"]
            while True:
                snap = api(args.url, f"/api/jobs/{jid}")
                if snap["status"] in ("completed", "failed", "cancelled"):
                    break
                time.sleep(1.0)
            elapsed = time.time() - t0
            row = {"template": t["name"], "job_id": jid, "status": snap["status"], "elapsed_s": round(elapsed, 1),
                   "db_run_id": snap.get("db_run_id"), "detections_written": snap.get("detections_written"),
                   "steps": [{"name": f"{s['stage']}.{s['algorithm']}", "status": s["status"], "summary": s.get("summary"), "elapsed_s": s.get("elapsed_s")} for s in snap.get("steps", [])],
                   "error": (snap.get("error") or {}).get("message")}
            print(f"  {snap['status']} in {elapsed:.1f}s · detections {snap.get('detections_written')} · " + " | ".join(f"{s.get('summary')}" for s in snap.get("steps", [])))
            # attach the chain page to the job and screenshot the rendered rows
            source = {"recording_id": args.recording, "channel_name": rec["name"], "source_file": rec["source_file"], "fs": rec["fs"],
                      "start_idx": s0, "end_idx": s1, "label": t["name"]}
            draft = {"name": t["name"], "saved": True, "steps": steps, "lastRunJobId": jid}
            page.goto(f"{args.url}/#/analyse/chain", wait_until="networkidle")
            page.evaluate(f"([s, c]) => {{ sessionStorage.setItem('{SS_KEY}:source', JSON.stringify(s)); sessionStorage.setItem('{SS_KEY}:chain', JSON.stringify(c)) }}", [source, draft])
            page.goto(f"{args.url}/#/analyse/chain?attached={jid}", wait_until="networkidle")
            page.reload(wait_until="networkidle")
            try:
                page.wait_for_selector(f'[data-testid="chain-row-{len(steps)}"]', timeout=30000)
                page.wait_for_timeout(2500)
            except Exception as e:
                row["page"] = f"rows did not paint: {e}"
            painted = page.evaluate("() => Array.from(document.querySelectorAll('[data-testid^=\"row-plot-\"]')).map(el => !!el.querySelector('path, rect, canvas, img, .bp-model'))")
            row["rows_painted"] = painted
            shot = os.path.join(args.out, f"{t['name']}.png")
            page.screenshot(path=shot, full_page=True)
            row["screenshot"] = shot
            summary.append(row)
        row_errors = [e for e in errors if "favicon" not in e]
        browser.close()
    with open(os.path.join(args.out, "summary.json"), "w", encoding="utf-8") as f:
        json.dump({"url": args.url, "mode": rt["mode"], "recording": rec, "span": args.span, "templates": summary, "console_errors": row_errors}, f, indent=2)
    print(json.dumps([{k: r.get(k) for k in ("template", "status", "elapsed_s", "detections_written", "rows_painted", "error")} for r in summary], indent=1))
    print("console errors:", row_errors[:5])


if __name__ == "__main__":
    sys.exit(main())
