"""Free cluster space by deleting what this PC already holds, checked file by file.

Why (2026-10-18): batch 2 stopped at 18:06 AEST when the cluster could no longer write. Three jobs failed at start
with no log file at all, and the running ones stopped mid-task without a word. By then the RQ4 sweeps had put about
16 GB of returned results in the cluster's home folder: batch 1 4.6 GB, already imported, and batch 2 11 GB, already
copied here.

`list` (on the PC) writes `<batch>/cleanup_copied.txt`. A task's cluster-side files are listed only when its
`result.json` here is complete AND every cache entry that result names is here with the byte count it records. A
listed task keeps its `result.json` on the cluster, so the packs still see it as done and never rerun it; only its
`return/task<i>/step_cache` and its `work/task<i>` go. A whole earlier batch (`--whole`, e.g. batch 1, imported) has
its `return/` and `work/` folders listed instead, once every task of every job checks out here.

`cleanup_copied.sh` (on the cluster) reads that list. By default it is a dry run: it shows what exists and how big it
is. With `--apply` it deletes exactly the listed paths, and only paths under HPC/Detection/generated/rq4_ that lie
inside a `*_out/` folder.

    python scripts/rq4_cleanup.py list --out HPC/Detection/generated/rq4_batch2 --whole HPC/Detection/generated/rq4_overnight

Dev tooling: not imported by the app.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

LIST_NAME = "cleanup_copied.txt"
SCRIPT_NAME = "cleanup_copied.sh"


def _du(path):
    return sum(os.path.getsize(os.path.join(dp, f)) for dp, _, fs in os.walk(path) for f in fs)


def _verified(out, task):
    """(complete and every cache entry here at its recorded size, bytes of the cache here)."""
    from Working.discovery import chain_job
    st = chain_job.task_status(os.path.join(REPO, out), task)
    if st["state"] != "complete":
        return False, 0
    ret = os.path.join(REPO, out, "return", f"task{task}")
    total = 0
    for e in st["result"].get("cache") or []:
        p = os.path.join(ret, e["path"])
        if not os.path.isdir(p) and not os.path.isfile(p):
            return False, 0
        got = _du(p) if os.path.isdir(p) else os.path.getsize(p)
        if int(e.get("bytes") or 0) and got != int(e["bytes"]):
            return False, 0
        total += got
    return True, total


def _jobs(folder):
    """Every (out, n_tasks) of a sweep folder: its own manifest, or each recording's (a batch)."""
    base = os.path.join(REPO, folder)
    if os.path.isfile(os.path.join(base, "batch.json")):
        with open(os.path.join(base, "batch.json"), encoding="utf-8") as f:
            subs = [d["folder"] for d in json.load(f)["datasets"]]
    else:
        subs = [folder]
    for sub in subs:
        with open(os.path.join(REPO, sub, "manifest.json"), encoding="utf-8") as f:
            for j in json.load(f)["jobs"]:
                yield j["out"], len(j["channels"])


def build_list(out_rel, whole=()):
    lines, freed, kept, skipped = [], 0, 0, 0
    for out, n in _jobs(out_rel):
        for i in range(n):
            ok, size = _verified(out, i)
            if ok:
                lines.append((f"{out}/return/task{i}/step_cache", size))
                lines.append((f"{out}/work/task{i}", 0))
                freed += size
            else:
                skipped += 1
    for folder in whole:
        for out, n in _jobs(folder):
            checks = [_verified(out, i) for i in range(n)]
            if all(ok for ok, _ in checks):
                size = sum(s for _, s in checks)
                lines += [(f"{out}/return", size), (f"{out}/work", 0)]
                freed += size
            else:
                kept += 1
    path = os.path.join(REPO, out_rel, LIST_NAME)
    with open(path, "w", newline="\n", encoding="utf-8") as f:
        for p, size in lines:
            f.write(f"{p.replace(os.sep, '/')} {size}\n")
    _write_script(out_rel)
    return {"list": path, "paths": len(lines), "bytes": freed, "tasksNotYetHere": skipped, "wholeJobsKept": kept}


_SH = r"""#!/bin/bash
# Free cluster space by deleting what the PC already holds, checked file by file (scripts/rq4_cleanup.py).
# Each line of {list} is a path and the bytes the PC holds of it (0 = a work/ folder, which stays here). A
# finished task keeps its result.json, so the packs still see it as done; only its cache and work folders go.
#
#   bash {script}            dry run: what exists and how big
#   bash {script} --apply    delete exactly the listed paths
#
# Only paths under HPC/Detection/generated/rq4_ that lie inside a *_out/ folder are ever deleted.
set -euo pipefail
LIST={list}
APPLY=0; [ "${{1:-}}" = "--apply" ] && APPLY=1
N=0; GONE=0; KB=0
while read -r P _BYTES; do
    [ -n "$P" ] || continue
    case "$P" in HPC/Detection/generated/rq4_*/*_out/*) ;; *) echo "refused (outside the sweep folders): $P"; continue;; esac
    case "$P" in *..*) echo "refused (..): $P"; continue;; esac
    [ -e "$P" ] || continue
    N=$((N + 1)); KB=$((KB + $(du -sk -- "$P" | cut -f1)))
    if [ "$APPLY" -eq 1 ]; then rm -rf -- "$P"; GONE=$((GONE + 1)); fi
done < "$LIST"
if [ "$APPLY" -eq 1 ]; then
    echo "deleted $GONE paths, $((KB / 1024)) MB freed"
else
    echo "dry run: $N listed paths exist here, $((KB / 1024)) MB; run with --apply to delete them"
fi
"""


def _write_script(out_rel):
    rel = out_rel.replace(os.sep, "/")
    text = _SH.format(list=f"{rel}/{LIST_NAME}", script=f"{rel}/{SCRIPT_NAME}")
    with open(os.path.join(REPO, out_rel, SCRIPT_NAME), "w", newline="\n", encoding="utf-8") as f:
        f.write(text)


def main(argv=None):
    ap = argparse.ArgumentParser(description="list cluster files the PC already holds, for cleanup_copied.sh")
    sub = ap.add_subparsers(dest="cmd", required=True)
    li = sub.add_parser("list", help="write <out>/cleanup_copied.txt and cleanup_copied.sh")
    li.add_argument("--out", required=True, help="the sweep folder whose finished tasks to free")
    li.add_argument("--whole", action="append", default=[], help="an earlier sweep folder, imported: free it whole")
    args = ap.parse_args(argv)
    r = build_list(args.out, args.whole)
    print(f"{r['paths']} paths, {r['bytes'] / 2**30:.1f} GB the PC holds verified -> {r['list']}")
    print(f"    tasks not complete here (left alone): {r['tasksNotYetHere']}; whole jobs not verified (kept): "
          f"{r['wholeJobsKept']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
