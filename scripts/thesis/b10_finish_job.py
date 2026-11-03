"""
b10_finish_job.py - record a motif_lengths job that b10_motif_lengths_site.py posted but stopped watching (its
runner was stopped to skip the optional 25 % spans): wait for the job, save its step-1 payload and append it to
site_runs.json exactly as the runner would have.

    python scripts/thesis/b10_finish_job.py <job_id> <source_file> <frac> <recording_id> <channel> <fs> <s0> <s1>
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from b10_motif_lengths_site import OUT, call, find_meta, slim  # noqa: E402


def main():
    jid, sf, frac, rid, ch, fs, s0, s1 = sys.argv[1:9]
    jid = int(jid)
    while True:
        snap = call(f"/api/runs/{jid}")
        if snap["status"] in ("completed", "failed", "cancelled"):
            break
        time.sleep(5)
    rec = {"source_file": sf, "recording_id": int(rid), "channel": int(ch), "fs": float(fs), "span": [int(s0), int(s1)],
           "frac": float(frac), "job_id": jid, "status": snap["status"],
           "seconds": round(snap["finished_at"] - snap["started_at"], 1) if snap.get("finished_at") else None}
    if snap["status"] == "completed":
        pay = call(f"/api/runs/{jid}/steps/1")
        json.dump(slim(pay), open(os.path.join(OUT, f"job{jid}_step1_payload.json"), "w"), indent=1, default=str)
        rec["summary"] = pay.get("summary")
    path = os.path.join(OUT, "site_runs.json")
    done = json.load(open(path))
    done.append(rec)
    json.dump(done, open(path, "w"), indent=1, default=str)
    print(rec)


if __name__ == "__main__":
    main()
