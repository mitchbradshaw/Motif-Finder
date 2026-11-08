"""Operational follow-up: longer CNN jobs and audited retry.

Scientific specs, runtime, arrays and model checkpoints are never changed.
This file is copied beside the existing recovery worker on the cluster.
"""
from __future__ import annotations
import argparse
import datetime as dt
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil

BASE = Path(__file__).resolve().parent
ROOT = Path.cwd().resolve()
STALL = "no progress in 2 jobs in a row"
CNN_PACK_BUDGET_S = 3 * 3600
CNN_TASK_BUDGET_S = 9900


def cnn_pack_config(original):
    return {**original, "parallel": 1, "wall_budget_s": CNN_PACK_BUDGET_S,
            "task_budget_s": CNN_TASK_BUDGET_S, "min_launch_s": 2400}


def safe(root, relative):
    p=(root/relative).resolve()
    if not p.is_relative_to(root.resolve()): raise ValueError("Path escapes project")
    return p


def retry_stalled(root, manifest, apply=False):
    """Archive only confirmed short-wall CNN stall states; retain all caches."""
    retried=[]
    for t in manifest["tasks"]:
        if t["pack"]!="cnn": continue
        base=safe(root,t["out"])
        result=base/"return"/f"task{t['task']}"/"result.json"
        state=base/"work"/f"task{t['task']}"/"state.json"
        if not result.exists() or not state.exists(): continue
        r=json.loads(result.read_text())
        if r.get("complete") or STALL not in (r.get("error") or ""): continue
        if r.get("specHash")!=t["specHash"]: raise ValueError("Result/spec mismatch")
        prior=json.loads(state.read_text())
        if prior.get("stalls",0)<2: continue
        backup=state.with_name("state.before_longwall_"+dt.datetime.now().strftime("%Y%m%d_%H%M%S_%f")+".json")
        if apply: state.rename(backup)
        retried.append({"id":t["id"],"state_backup":str(backup),"applied":apply})
    return retried


def sha(p):
    h=hashlib.sha256()
    with p.open("rb") as f:
        for block in iter(lambda:f.read(4*1024**2),b""): h.update(block)
    return h.hexdigest()


def release_verified(root, acknowledgement, apply=False):
    """Remove only exact caches whose full file hashes were verified on the PC."""
    allowed=(root/"DATA/derived/hpc/recovery_20261108/rq4").resolve()
    released=[]
    for row in acknowledgement["returns"]:
        result=safe(root,row["result"])
        cache=(result.parent/"step_cache").resolve()
        if not cache.is_relative_to(allowed): raise ValueError("Cache outside recovery outputs")
        if not result.exists() or sha(result)!=row["result_sha256"] or not cache.is_dir(): continue
        files={p.relative_to(cache).as_posix():p for p in cache.rglob("*") if p.is_file()}
        if set(files)!=set(row["files"]): continue
        if any(sha(files[k])!=v for k,v in row["files"].items()): continue
        size=sum(p.stat().st_size for p in files.values())
        if apply: shutil.rmtree(cache)
        released.append({"result":row["result"],"bytes":size,"applied":apply})
    return {"tasks":len(released),"bytes":sum(r["bytes"] for r in released),"applied":apply}


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("command",choices=["retry-stalled","release-verified","pack"])
    ap.add_argument("--apply",action="store_true")
    args=ap.parse_args()
    m=json.loads((BASE/"manifest.json").read_text())
    if args.command=="retry-stalled": print(json.dumps(retry_stalled(ROOT,m,args.apply),indent=2));return 0
    if args.command=="release-verified":
        ack=json.loads((BASE/"pc_verified_returns.json").read_text())
        print(json.dumps(release_verified(ROOT,ack,args.apply)));return 0
    spec=importlib.util.spec_from_file_location("frozen_recovery_worker",BASE/"worker.py")
    worker=importlib.util.module_from_spec(spec);spec.loader.exec_module(worker)
    m["packs"]["cnn"]=cnn_pack_config(m["packs"]["cnn"])
    return worker.run_pack(m,"cnn")


if __name__=="__main__": raise SystemExit(main())
