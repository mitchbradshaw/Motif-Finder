"""
pool_provenance.py
==================
What produced `DATA/derived/autodetect/pool_20261124`, kept beside it - so the pool can be traced, trusted and redone
after the working copy, the database and the models have moved on.

In plain words
--------------
A result is only as good as the record of how it was made. This writes that record next to the results:

* ``provenance/provenance.json`` - the git commit the run stood on; every repo file the pool's three scripts import
  (found by reading their imports, not by running them), each with its fingerprint and whether it differs from that
  commit; the Python and package versions; the inputs - the seed bank, the R4 model, every channel's .npy, the
  database file, the snapshot of what was already judged or queued (``reference_spans.parquet``) - with fingerprints;
  and which channels ran with which settings.
* ``provenance/local_changes/`` - a copy of each imported file that is NOT in that commit as it is (untracked, or
  modified), and for a modified one its diff against the commit (``<file>.patch``). With these the run can be redone
  even if those files are later changed or lost.
* ``provenance/runs.csv`` - one row per channel from its ``run.json``: the worker, the stretches, the time, the memory
  peak and the counts.

Read-only everywhere but ``<pool>/provenance/``. Run it after each stage that changes the pool:

    PYTHONIOENCODING=utf-8 "/c/ProgramData/anaconda3/python.exe" scripts/autodetect/pool_provenance.py [--no-channel-hashes]
"""
from __future__ import annotations

import argparse
import ast
import datetime as dt
import glob
import hashlib
import importlib.metadata as md
import json
import os
import platform
import shutil
import sqlite3
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
POOL = os.path.join(ROOT, "DATA", "derived", "autodetect", "pool_20261124")
OUT = os.path.join(POOL, "provenance")
DB = os.path.join(ROOT, "DATA", "db", "annotations.sqlite")

#: the pool's own scripts: where the import walk starts
ENTRY = ("scripts/autodetect/run_pool.py", "scripts/autodetect/build_pool.py", "scripts/autodetect/pool_rhythm.py",
         "scripts/autodetect/pool_summary.py", "scripts/autodetect/pool_plots.py",
         "scripts/autodetect/pool_provenance.py", "scripts/autodetect/pool_checks/core_verdicts.py",
         "scripts/autodetect/pool_checks/acceptance_models.py", "scripts/autodetect/pool_checks/steepness_rate.py")
#: where a bare ``import name`` may be found (the scripts put these on sys.path)
BARE_DIRS = ("scripts/autodetect", "scripts/library_analysis", "scripts/thesis")
#: the inputs that are files, beside the channels
INPUT_FILES = ("Working/autodetect/seed_bank/seed_bank.npz",
               "DATA/derived/models/rq1b_minirocket/20261020-2343/model.joblib",
               "DATA/derived/autodetect/pool_20261124/reference_spans.parquet")
PACKAGES = ("numpy", "pandas", "scipy", "numba", "scikit-learn", "joblib", "aeon", "sktime", "stumpy", "pyarrow",
            "matplotlib", "PyWavelets")


def git(*args):
    r = subprocess.run(("git", *args), cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
    return r.stdout.strip() if r.returncode == 0 else ""


def sha256(path, n=None):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 22), b""):
            h.update(block)
    return h.hexdigest()[:n] if n else h.hexdigest()


# ── which repo files the pool's scripts import ───────────────────────────────

def _exists_exact(path):
    """A file at exactly this name, case included - Windows would also say yes to `SpanSet.py` for `spanset.py`,
    where Python's importer (and git) would not."""
    if not os.path.isfile(path):
        return False
    rel = os.path.relpath(path, ROOT).split(os.sep)
    here = ROOT
    for part in rel:
        if part not in os.listdir(here):
            return False
        here = os.path.join(here, part)
    return True


def _module_file(name):
    """The repo file a dotted module name stands for, or None (a third-party or standard module)."""
    base = os.path.join(ROOT, *name.split("."))
    for cand in (base + ".py", os.path.join(base, "__init__.py")):
        if _exists_exact(cand):
            return cand
    return None


def _imports_of(path):
    """The repo files ``path`` imports directly: absolute imports, a sibling's bare import, a package's modules
    named in a from-import, and a ``*.py`` named in a string (a module loaded by path)."""
    with open(path, encoding="utf-8") as fh:
        tree = ast.parse(fh.read(), filename=path)
    here = os.path.dirname(path)
    found = set()

    def bare(name):
        top = name.split(".")[0]
        for d in (here, *(os.path.join(ROOT, b) for b in BARE_DIRS)):
            cand = os.path.join(d, top + ".py")
            if _exists_exact(cand):
                return cand
        return None

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                f = _module_file(a.name) or bare(a.name)
                if f:
                    found.add(f)
                parts = a.name.split(".")                     # the packages on the way: their __init__ runs
                for k in range(1, len(parts)):
                    f = _module_file(".".join(parts[:k]))
                    if f:
                        found.add(f)
        elif isinstance(node, ast.ImportFrom):
            if node.level:                                    # relative: from the file's own package
                pkg = os.path.relpath(here, ROOT).replace(os.sep, ".")
                for _ in range(node.level - 1):
                    pkg = pkg.rsplit(".", 1)[0]
                mod = f"{pkg}.{node.module}" if node.module else pkg
            else:
                mod = node.module or ""
            f = _module_file(mod) or (bare(mod) if mod and "." not in mod else None)
            if f:
                found.add(f)
            for a in node.names:                              # `from pkg import module`
                g = _module_file(f"{mod}.{a.name}") if mod else None
                if g:
                    found.add(g)
            parts = mod.split(".")
            for k in range(1, len(parts)):
                g = _module_file(".".join(parts[:k]))
                if g:
                    found.add(g)
        elif isinstance(node, ast.Constant) and isinstance(node.value, str) and node.value.endswith(".py") \
                and os.sep not in node.value and "/" not in node.value and " " not in node.value:
            hits = [p for d in ("Working", "Adapters", "Pipelines", "scripts")
                    for p in glob.glob(os.path.join(ROOT, d, "**", node.value), recursive=True)
                    if "__pycache__" not in p]
            if len(hits) == 1:
                found.add(hits[0])
    return found


def import_closure():
    todo = [os.path.join(ROOT, e) for e in ENTRY]
    seen = set()
    while todo:
        f = os.path.normpath(todo.pop())
        if f in seen or not os.path.isfile(f):
            continue
        seen.add(f)
        nxt = _imports_of(f)
        # the adapter registry imports every module in Adapters/ (pkgutil.iter_modules): all of them run
        if os.path.normpath(os.path.join(ROOT, "Adapters", "registry.py")) in {os.path.normpath(n) for n in nxt}:
            nxt |= {p for p in glob.glob(os.path.join(ROOT, "Adapters", "*.py"))}
        todo += [n for n in nxt if os.path.normpath(n) not in seen]
    return sorted(seen)


# ── the record ───────────────────────────────────────────────────────────────

def code_record(files):
    rows, changed = [], []
    for f in files:
        rel = os.path.relpath(f, ROOT).replace(os.sep, "/")
        head_blob = git("rev-parse", f"HEAD:{rel}")
        work_blob = git("hash-object", rel)
        state = "untracked" if not head_blob else ("modified" if head_blob != work_blob else "as committed")
        rows.append({"file": rel, "sha256_12": sha256(f, 12), "git_blob": work_blob[:12], "state": state,
                     "mtime": dt.datetime.fromtimestamp(os.path.getmtime(f)).isoformat(timespec="seconds")})
        if state != "as committed":
            changed.append((rel, state))
    return rows, changed


def save_local_changes(changed):
    dest = os.path.join(OUT, "local_changes")
    if os.path.isdir(dest):
        shutil.rmtree(dest)
    for rel, state in changed:
        target = os.path.join(dest, *rel.split("/"))
        os.makedirs(os.path.dirname(target), exist_ok=True)
        shutil.copy2(os.path.join(ROOT, rel), target)
        if state == "modified":
            with open(target + ".patch", "w", encoding="utf-8", newline="\n") as fh:
                fh.write(git("diff", "HEAD", "--", rel) + "\n")


def targets_from_source():
    """TARGETS and SKIPPED read from run_pool.py's text (importing it would load the detectors)."""
    with open(os.path.join(HERE, "run_pool.py"), encoding="utf-8") as fh:
        tree = ast.parse(fh.read())
    out = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name) \
                and node.targets[0].id in ("TARGETS", "SKIPPED", "RUN_FS"):
            out[node.targets[0].id] = ast.literal_eval(node.value)
    return out


def channel_inputs(target_files, hash_channels):
    conn = sqlite3.connect(f"file:{DB.replace(os.sep, '/')}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    q = "SELECT id, source_file, channel, fs, n_samples, units, npy_path FROM recordings WHERE source_file = ? " \
        "ORDER BY channel"
    rows = []
    for f in target_files:
        for r in conn.execute(q, (f,)):
            p = os.path.join(ROOT, r["npy_path"])
            row = dict(r)
            row["bytes"] = os.path.getsize(p) if os.path.isfile(p) else None
            row["mtime"] = dt.datetime.fromtimestamp(os.path.getmtime(p)).isoformat(timespec="seconds") \
                if os.path.isfile(p) else None
            if hash_channels and os.path.isfile(p):
                row["sha256"] = sha256(p)
            rows.append(row)
    conn.close()
    return rows


def runs_table():
    import csv
    rows = []
    for f in sorted(glob.glob(os.path.join(POOL, "raw", "*", "run.json")), key=lambda p: int(p.split(os.sep)[-2])):
        j = json.load(open(f, encoding="utf-8"))
        rec, tgt, counts = j.get("recording", {}), j.get("target", {}), j.get("counts", {})
        st = j.get("stretches") or []
        rows.append({"recording_id": rec.get("id"), "dataset": tgt.get("dataset"), "source_file": rec.get("source_file"),
                     "channel": rec.get("channel"), "native_fs": rec.get("fs"), "decimation": j.get("decimation"),
                     "run_fs": j.get("run_fs"), "samples_run": j.get("n_samples_run"), "hours": j.get("hours"),
                     "stretches": len(st), "longest_stretch": max((s["end_idx"] - s["start_idx"] for s in st), default=None),
                     "worker_pid": j.get("pid"), "wall_s": j.get("wall_s"), "peak_rss_gb": j.get("peak_rss_gb"),
                     "finished_at": j.get("finished_at"), "floor_mv": j.get("floor_mv"),
                     **{f"n_{k}": v for k, v in counts.items() if not isinstance(v, (dict, list))}})
    if rows:
        keys = list(dict.fromkeys(k for r in rows for k in r))
        with open(os.path.join(OUT, "runs.csv"), "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=keys)
            w.writeheader()
            w.writerows(rows)
    return rows


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--no-channel-hashes", action="store_true", help="record each channel's size and time only")
    a = ap.parse_args(argv)
    os.makedirs(OUT, exist_ok=True)
    files = import_closure()
    code, changed = code_record(files)
    save_local_changes(changed)
    t = targets_from_source()
    versions = {}
    for p in PACKAGES:
        try:
            versions[p] = md.version(p)
        except md.PackageNotFoundError:
            pass
    inputs = []
    for rel in INPUT_FILES:
        p = os.path.join(ROOT, rel)
        inputs.append({"file": rel, "bytes": os.path.getsize(p) if os.path.isfile(p) else None,
                       "sha256": sha256(p) if os.path.isfile(p) else None})
    runs = runs_table()
    record = {
        "written_at": dt.datetime.now().isoformat(timespec="seconds"),
        "git": {"head": git("rev-parse", "HEAD"), "branch": git("rev-parse", "--abbrev-ref", "HEAD"),
                "head_date": git("show", "-s", "--format=%ci", "HEAD"),
                "head_subject": git("show", "-s", "--format=%s", "HEAD")},
        "python": {"version": sys.version, "executable": sys.executable, "platform": platform.platform()},
        "packages": versions,
        "code": {"entry": list(ENTRY), "files": code,
                 "not_as_committed": [{"file": r, "state": s} for r, s in changed],
                 "note": "files found by reading imports (ast), plus every Adapters/*.py once the adapter registry is "
                         "imported (it imports them all); local_changes/ holds a copy of each file not as committed"},
        "inputs": {"files": inputs, "database": {"file": os.path.relpath(DB, ROOT).replace(os.sep, "/"),
                                                  "bytes": os.path.getsize(DB),
                                                  "mtime": dt.datetime.fromtimestamp(os.path.getmtime(DB)).isoformat(
                                                      timespec="seconds"),
                                                  "note": "read-only (mode=ro); live, so not hashed - what was judged "
                                                          "or queued when the pool was filtered is "
                                                          "reference_spans.parquet"},
                   "channels": channel_inputs([x["file"] for x in t.get("TARGETS", [])], not a.no_channel_hashes)},
        "targets": t.get("TARGETS"), "skipped": t.get("SKIPPED"), "run_fs": t.get("RUN_FS"),
        "runs": {"channels_done": len(runs),
                 "stretch_settings": sorted({r["longest_stretch"] for r in runs if r["longest_stretch"]})[-3:]},
    }
    with open(os.path.join(OUT, "provenance.json"), "w", encoding="utf-8") as fh:
        json.dump(record, fh, indent=1, default=str)
    print(f"provenance: {len(code)} code files ({len(changed)} not as committed: "
          f"{', '.join(r for r, _ in changed) or 'none'}); {len(record['inputs']['channels'])} channels; "
          f"{len(runs)} runs -> {os.path.relpath(OUT, ROOT)}")


if __name__ == "__main__":
    main()
