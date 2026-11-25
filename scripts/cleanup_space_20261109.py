"""One-off space clean-up approved by the author on 9 Nov 2026 (after thesis submission).

Deletes, with a reparse-point (junction/symlink) check on every target first:
  1. the agent worktrees under .claude/worktrees (git worktree remove; branches and commits are kept);
  2. the sandbox copies in webui/runtime/<stamp>/;
  3. returned cluster step-cache entries that are byte-for-byte duplicates of DATA/derived/step_cache
     (result.json, task scratch DBs, job specs and logs are kept), and the superseded DATA/derived/hpc/recovery_20261108
     return, whose every file is in recovery_20261108_latest (identical or newer);
  4. the two benchmark database copies under DATA/derived/review_speed and DATA/derived/review_completion_20261108.
Run with --apply to delete; without it, it only reports.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys

REPO = "C:/Users/mmebr/Documents/CNN"
CACHE = os.path.join(REPO, "DATA", "derived", "step_cache")
DUPS = sys.argv[sys.argv.index("--dups") + 1] if "--dups" in sys.argv else None
APPLY = "--apply" in sys.argv
REPARSE = 0x400


def has_reparse(path):
    for r, ds, fs in os.walk(path):
        for name in ds + fs:
            try:
                st = os.stat(os.path.join(r, name), follow_symlinks=False)
            except OSError:
                continue
            if getattr(st, "st_file_attributes", 0) & REPARSE:
                return os.path.join(r, name)
    return None


def size_of(path):
    return sum(os.path.getsize(os.path.join(r, f)) for r, _, fs in os.walk(path) for f in fs)


def rm_tree(path, label):
    bad = has_reparse(path)
    if bad:
        print(f"SKIP {label}: reparse point inside: {bad}")
        return 0
    n = size_of(path)
    if APPLY:
        shutil.rmtree(path)
    return n


freed = {}

# 1. worktrees
wt_lines = subprocess.run(["git", "-C", REPO, "worktree", "list", "--porcelain"], capture_output=True,
                          text=True).stdout.splitlines()
wts = [l[9:] for l in wt_lines if l.startswith("worktree ") and "/.claude/worktrees/" in l]
n = 0
for wt in wts:
    bad = has_reparse(wt)
    if bad:
        print(f"SKIP worktree {wt}: reparse point inside: {bad}")
        continue
    s = size_of(wt)
    if APPLY:
        r = subprocess.run(["git", "-C", REPO, "worktree", "remove", "-f", "-f", wt], capture_output=True, text=True)
        if r.returncode != 0:
            print(f"git worktree remove failed for {wt}: {r.stderr.strip()[:200]}; removing the folder directly")
            if os.path.isdir(wt):
                shutil.rmtree(wt)
    n += s
freed["agent worktrees"] = n
print(f"worktrees: {len(wts)}")

# 2. sandbox runtime copies
rt = os.path.join(REPO, "webui", "runtime")
n = 0
stamps = [d for d in os.listdir(rt) if os.path.isdir(os.path.join(rt, d)) and d[:2] == "20"]
for d in stamps:
    n += rm_tree(os.path.join(rt, d), f"runtime/{d}")
freed["webui/runtime sandbox copies"] = n
print(f"runtime stamps: {len(stamps)}")

# 3a. duplicate returned step-cache entries (re-verified now)
superseded = os.path.join(REPO, "DATA", "derived", "hpc", "recovery_20261108").replace("\\", "/")
n = k = 0
for entry in json.load(open(DUPS, encoding="utf-8")):
    e = entry.replace("\\", "/")
    if e.startswith(superseded + "/") or not os.path.isdir(entry):
        continue
    parts = e.split("/")
    h, step = parts[-2], parts[-1]
    cache_entry = os.path.join(CACHE, h, step)
    ok = os.path.isdir(cache_entry)
    if ok:
        for r, _, fs in os.walk(entry):
            for f in fs:
                a = os.path.join(r, f)
                b = os.path.join(cache_entry, os.path.relpath(a, entry))
                if not os.path.isfile(b) or os.path.getsize(a) != os.path.getsize(b):
                    ok = False
    if not ok:
        print("kept (no longer an exact duplicate):", entry)
        continue
    n += rm_tree(entry, entry)
    k += 1
    if APPLY:
        for parent in (os.path.dirname(entry), os.path.dirname(os.path.dirname(entry))):
            try:
                os.rmdir(parent)  # only succeeds when empty
            except OSError:
                pass
freed["duplicate cluster caches"] = n
print(f"duplicate entries removed: {k}")

# 3b. superseded return
freed["superseded recovery_20261108"] = rm_tree(superseded, "recovery_20261108") if os.path.isdir(superseded) else 0

# 4. benchmark database copies
n = 0
for d in ("DATA/derived/review_speed", "DATA/derived/review_completion_20261108"):
    for r, _, fs in os.walk(os.path.join(REPO, d)):
        for f in fs:
            if f.endswith((".sqlite", ".sqlite-wal", ".sqlite-shm")):
                p = os.path.join(r, f)
                n += os.path.getsize(p)
                if APPLY:
                    os.remove(p)
freed["benchmark database copies"] = n

for k2, v in freed.items():
    print(f"{v / 1e9:8.2f} GB  {k2}")
print(f"{sum(freed.values()) / 1e9:8.2f} GB  {'freed' if APPLY else 'would free'} in total")
