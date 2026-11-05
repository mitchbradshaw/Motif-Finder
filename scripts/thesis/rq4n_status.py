"""
rq4n_status.py - per job of the 2 Hz sweep (docs/thesis/hpc/rq4_newsets_20261027): how many of its tasks came back
complete, so that only whole jobs are adopted (`rq4_overnight.py adopt --only <labels>`) and the rest go to the
cluster again. Read-only.

    python scripts/thesis/rq4n_status.py            # a table, plus rq4n_status.json in the bundle folder
"""
import json
import os
import sys
from collections import defaultdict

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, REPO)
BATCH = os.path.join(REPO, "docs", "thesis", "hpc", "rq4_newsets_20261027")

from Working.discovery import chain_job  # noqa: E402


def main():
    with open(os.path.join(BATCH, "batch.json"), encoding="utf-8") as f:
        batch = json.load(f)
    jobs = defaultdict(lambda: {"tasks": 0, "states": defaultdict(int), "pack": set()})
    for p in batch["packs"]:
        with open(os.path.join(BATCH, f"tasks_{p['name']}.txt"), encoding="utf-8") as f:
            for line in f:
                spec, out, task, label = line.split()[:4]
                rec, setting = label.split("/")[:2]
                st = chain_job.task_status(os.path.join(REPO, out), int(task))["state"]
                j = jobs[(rec, setting)]
                j["tasks"] += 1
                j["states"][st] += 1
                j["pack"].add(p["name"])
                j["out"] = out
    rows = []
    for (rec, setting), j in sorted(jobs.items()):
        done = j["states"].get("complete", 0)
        rows.append(dict(recording=rec, setting=setting, tasks=j["tasks"], complete=done,
                         whole=done == j["tasks"], states=dict(j["states"]), packs=sorted(j["pack"]), out=j["out"]))
    with open(os.path.join(BATCH, "rq4n_status.json"), "w", encoding="utf-8") as f:
        json.dump(rows, f, indent=1)
    for rec in sorted({r["recording"] for r in rows}):
        rr = [r for r in rows if r["recording"] == rec]
        whole = [r for r in rr if r["whole"]]
        print(f"{rec}: {len(whole)} of {len(rr)} jobs whole; tasks {sum(r['complete'] for r in rr)}/"
              f"{sum(r['tasks'] for r in rr)}")
        for r in rr:
            mark = "WHOLE" if r["whole"] else f"{r['complete']}/{r['tasks']}"
            print(f"   {mark:>7}  {r['setting']}  {','.join(r['packs'])}  {r['states'] if not r['whole'] else ''}")


if __name__ == "__main__":
    main()
