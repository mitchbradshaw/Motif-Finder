"""
b9_cwt_site.py - B9 on the website: the `cwt_events` template on one 24 h span, on the real channel and on an AAFT
and a phase-randomised copy of it (the template with `preprocessing.surrogate` prepended), posted one at a time to
the bridge's /api/runs (the route the Analyse page's Run button uses). Machine runs only.

The span is the backend's (b9_cwt_durations.py) span for M2_aug channel 0: 24 h starting at 50 % of (length - 24 h),
so the site's real count can be checked against the backend's.

Writes docs/thesis/data/ch10_b9/site_runs.json.
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from b10_motif_lengths_site import call, slim  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
OUT = os.path.join(ROOT, "docs", "thesis", "data", "ch10_b9")
CWT = [{"stage": "detection", "algorithm": "cwt_ridges", "params": {"polarity": "drop"}},
       {"stage": "interrogation", "algorithm": "event_shape", "params": {"polarity": "drop"}},
       {"stage": "interrogation", "algorithm": "intervals", "params": {}}]
RUNS = [("real", 1, CWT),
        ("aaft", 1, [{"stage": "preprocessing", "algorithm": "surrogate", "params": {"method": "aaft", "seed": 0}}] + CWT),
        ("phase", 1, [{"stage": "preprocessing", "algorithm": "surrogate",
                       "params": {"method": "phase_randomize", "seed": 0}}] + CWT)]


def main():
    n, L = 2595600, 86400
    s0 = int(round(0.5 * (n - L)))
    done = []
    for kind, rid, steps in RUNS:
        t0 = time.time()
        snap = call("/api/runs", {"recording_id": rid, "span": [s0, s0 + L], "steps": steps, "px": 1200})
        jid = snap["job_id"]
        while snap["status"] not in ("completed", "failed", "cancelled"):
            time.sleep(3)
            snap = call(f"/api/runs/{jid}")
        det = len(steps) - 3
        rec = {"kind": kind, "recording_id": rid, "span": [s0, s0 + L], "job_id": jid, "status": snap["status"],
               "seconds": round(time.time() - t0, 1), "steps": [(s["algorithm"], s.get("summary")) for s in snap["steps"]],
               "detections_written": snap.get("detections_written"), "db_run_id": snap.get("db_run_id"),
               "detector_step": det}
        if snap["status"] == "completed":
            pay = call(f"/api/runs/{jid}/steps/{det}")
            json.dump(slim(pay), open(os.path.join(OUT, f"site_job{jid}_cwt_payload.json"), "w"), indent=1,
                      default=str)
        print(json.dumps(rec, default=str), flush=True)
        done.append(rec)
        json.dump(done, open(os.path.join(OUT, "site_runs.json"), "w"), indent=1, default=str)


if __name__ == "__main__":
    main()
