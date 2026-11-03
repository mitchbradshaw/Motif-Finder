"""
b10_motif_lengths_site.py - B10: run the `motif_lengths` template on the website (the bridge's own /api/runs, the
route the Analyse page's Run button posts to), one chain at a time, and keep each run's per-length verdict.

The span rule, fixed before any result was read (docs/rq_roundA_2/findings/b10-scales-2026-11-03.md, Protocol):
channel 0 of each recording (first id), an 8 h span starting at 50 % of (length - 8 h); for the two longest
recordings (M2_aug, MJu26a) a second 8 h span at 25 %. A span more than 10 % NaN moves to the next channel.

Writes docs/thesis/data/ch10_b10/site_runs.json (job id, span, time taken, per-length table, summary).

    PYTHONIOENCODING=utf-8 "/c/ProgramData/anaconda3/python.exe" scripts/thesis/b10_motif_lengths_site.py
"""
from __future__ import annotations

import json
import os
import sqlite3
import sys
import time
import urllib.request

import numpy as np

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DB = os.path.join(ROOT, "DATA", "db", "annotations.sqlite").replace("\\", "/")
OUT = os.path.join(ROOT, "docs", "thesis", "data", "ch10_b10")
BASE = "http://127.0.0.1:8765"
STEPS = [
    {"stage": "preprocessing", "algorithm": "detrend", "params": {"mode": "rolling_mean", "window_s": 7200.0}},
    {"stage": "detection", "algorithm": "pan_matrix_profile",
     "params": {"min_window_s": 30.0, "max_window_s": 3600.0, "n_lengths": 12, "null_draws": 3, "null": "aaft",
                "seed": 0, "max_fill_s": 5.0, "stall_s": 60.0}},
]
PLAN = [("M2_aug_concat_fs1.mat", 0.5), ("M2_concat_fs1.mat", 0.5), ("CO_fs2.mat", 0.5), ("LM_fs2.mat", 0.5),
        ("MJu26a_fs2.mat", 0.5), ("M2_aug_concat_fs1.mat", 0.25), ("MJu26a_fs2.mat", 0.25)]


def call(path, body=None):
    req = urllib.request.Request(BASE + path, data=None if body is None else json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"}, method="GET" if body is None else "POST")
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read())


def find_meta(d):
    """The dict that holds the pan block's per_length table, wherever the payload nests it."""
    if isinstance(d, dict):
        if "per_length" in d:
            return d
        for v in d.values():
            m = find_meta(v)
            if m:
                return m
    return {}


def slim(d):
    """The payload without its long arrays (the image), for the record."""
    if isinstance(d, dict):
        return {k: slim(v) for k, v in d.items()}
    if isinstance(d, list):
        return f"<list of {len(d)}>" if len(d) > 64 else [slim(v) for v in d]
    return d


def pick(c, sf, frac):
    rows = c.execute("SELECT id, channel, fs, n_samples, npy_path FROM recordings WHERE source_file = ? AND active = 1 "
                     "ORDER BY channel", (sf,)).fetchall()
    for rid, ch, fs, n, npy in rows:
        L = int(round(8 * 3600 * fs))
        s0 = int(round(frac * (n - L)))
        x = np.load(os.path.join(ROOT, npy), mmap_mode="r")[s0:s0 + L]
        if np.mean(~np.isfinite(x)) <= 0.10:
            return {"recording_id": rid, "channel": ch, "fs": fs, "span": [s0, s0 + L], "frac": frac}
    raise RuntimeError(f"no channel of {sf} has a usable span at {frac}")


def main():
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, "site_runs.json")
    done = json.load(open(path)) if os.path.exists(path) else []
    keys = {(d["source_file"], d["frac"]) for d in done}
    c = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    only = sys.argv[1:]
    for sf, frac in PLAN:
        if (sf, frac) in keys or (only and sf not in only):
            continue
        assert "M4_aug" not in sf and "Schizophyllum" not in sf
        p = pick(c, sf, frac)
        t0 = time.time()
        snap = call("/api/runs", {"recording_id": p["recording_id"], "span": p["span"], "steps": STEPS, "px": 1200})
        jid = snap["job_id"]
        print(f"{sf} @{frac}: rec {p['recording_id']} span {p['span']} -> job {jid}", flush=True)
        while True:
            time.sleep(5)
            snap = call(f"/api/runs/{jid}")
            if snap["status"] in ("completed", "failed", "cancelled"):
                break
        dt = time.time() - t0
        rec = {"source_file": sf, **p, "job_id": jid, "status": snap["status"], "seconds": round(dt, 1)}
        if snap["status"] == "completed":
            pay = call(f"/api/runs/{jid}/steps/1")
            meta = find_meta(pay)
            json.dump(slim(pay), open(os.path.join(OUT, f"job{jid}_step1_payload.json"), "w"), indent=1, default=str)
            rec["summary"] = meta.get("summary")
            rec["cleared_s"] = meta.get("cleared_s")
            rec["suggested_window_s"] = meta.get("suggested_window_s")
            rec["per_length"] = meta.get("per_length")
            rec["run_id"] = snap.get("run_id")
        else:
            rec["error"] = {k: snap.get(k) for k in ("error", "message") if k in snap}
        print(f"  {snap['status']} in {dt:.0f} s: {rec.get('summary')}", flush=True)
        done.append(rec)
        json.dump(done, open(path, "w"), indent=1, default=str)
    c.close()


if __name__ == "__main__":
    main()
