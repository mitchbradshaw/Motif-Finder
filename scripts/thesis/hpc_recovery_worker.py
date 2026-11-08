"""Run the frozen November recovery plan; no live annotation database is opened."""
from __future__ import annotations
import argparse
import concurrent.futures
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time

BASE = Path(__file__).resolve().parent
ROOT = Path.cwd().resolve()
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(BASE / "runtime"))


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(4 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def atomic_json(path, obj, indent=None):
    """Each writer owns its temporary file, including writers of shared job.json."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(obj, f, indent=indent)
        for attempt in range(50):
            try:
                os.replace(tmp, path)
                break
            except PermissionError:
                if attempt == 49:
                    raise
                time.sleep(0.01)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def safe(relative):
    p = (ROOT / relative).resolve()
    if not p.is_relative_to(ROOT):
        raise ValueError("Path leaves the CNN repository: " + relative)
    return p


def done(t):
    p = safe(t["out"])
    if t["kind"] == "rq4":
        p = p / "return" / ("task" + str(t["task"])) / "result.json"
    if not p.exists():
        return False
    r = read(p)
    if r.get("specHash") != t["specHash"]:
        raise ValueError("Result/spec mismatch: " + str(p))
    return bool(r.get("complete")) and not r.get("error")


def prepare(m):
    # Runtime-local links support modules that resolve MODELS/DATA from their package root.
    for name in ("DATA", "MODELS"):
        link = BASE / "runtime" / name
        if not link.exists() and not link.is_symlink():
            link.symlink_to(ROOT / name, target_is_directory=True)
    for row in m["seed_checkpoints"]:
        src, dst = BASE / row["copy"], safe(row["destination"])
        old = read(dst) if dst.exists() else {}
        saved = read(src)
        if old and old.get("specHash") != saved["specHash"]:
            raise ValueError("A different seed search occupies " + str(dst))
        def progress(r):
            return sum((c.get("null") or {}).get("draws", 0) for c in r.get("perChannel", []))
        if not old or progress(old) < progress(saved):
            dst.parent.mkdir(parents=True, exist_ok=True)
            atomic_json(dst, saved)
    for t in m["tasks"]:
        spec = read(BASE / t["spec_copy"])
        if t["kind"] == "seed":
            from Working.discovery.seed_job import spec_hash
        else:
            from Working.discovery.chain_job import spec_hash
        if spec_hash(spec) != t["specHash"]:
            raise ValueError("Specification changed: " + t["id"])
        if t["kind"] == "rq4" and not done(t):
            # The cluster may have finished more tasks since the PC copy was made.
            old = safe(t["original_out"]) / "return" / ("task" + str(t["task"]))
            result = old / "result.json"
            if result.exists():
                r = read(result)
                intact = all((old / e["path"]).is_dir() and
                             sum(p.stat().st_size for p in (old / e["path"]).rglob("*") if p.is_file()) == e["bytes"]
                             for e in r.get("cache", []))
                if r.get("complete") and not r.get("error") and r.get("specHash") == t["specHash"] and intact:
                    target = safe(t["out"]) / "return" / ("task" + str(t["task"]))
                    def link_or_copy(src, dst):
                        try:
                            os.link(src, dst)
                        except OSError:
                            shutil.copy2(src, dst)
                    shutil.copytree(old, target, copy_function=link_or_copy, dirs_exist_ok=True)
                    print("Reused a later complete original task:", t["id"])
    print("Frozen specs and seed checkpoints verified; no jobs submitted.")


def check_inputs(m):
    import numpy as np
    for rel, n in m["inputs"].items():
        p = safe(rel)
        if not p.exists() or np.load(p, mmap_mode="r").shape != (n,):
            raise ValueError("Missing or wrong input: " + str(p))
    for p, digest in m["model_hashes"].items():
        if sha(safe(p)) != digest:
            raise ValueError("CNN checkpoint differs: " + p)
    for p, digest in m["runtime_hashes"].items():
        if sha(BASE / p) != digest:
            raise ValueError("Recovery runtime differs: " + p)
    print("Input shapes, CNN hashes and isolated runtime verified.")


def run_one(t, budget):
    spec = read(BASE / t["spec_copy"])
    if done(t):
        return
    if t["kind"] == "seed":
        import numpy as np
        from Working.discovery import seed_job
        seed_job.CHECKPOINT_DRAWS = 1
        seed_job.run_spec(spec, loader=lambda ch: np.load(safe(ch["npy"]), mmap_mode="r"),
                           checkpoint=str(safe(t["out"])), budget_s=budget, max_channels=1)
    else:
        from Working.discovery import chain_job
        chain_job._write_json = atomic_json
        r = chain_job.run_task(spec, t["task"], str(safe(t["out"])),
                               budget_s=budget, repo_root=str(ROOT))
        if r.get("error"):
            raise RuntimeError(r["error"])


def run_pack(m, pack):
    tasks = [t for t in m["tasks"] if t["pack"] == pack and not done(t)]
    if not tasks:
        return 0
    outroot = BASE / "rq4"
    size = sum(p.stat().st_size for p in outroot.rglob("*") if p.is_file()) if outroot.exists() else 0
    if size > 8 * 1024**3:
        print("Recovery output exceeds 8 GiB. Collect and copy it before continuing.")
        return 75
    cfg = m["packs"][pack]
    end = time.monotonic() + cfg.get("wall_budget_s", 900)
    parallel = cfg["parallel"]
    failed = []
    def launch(t):
        remaining = int(end - time.monotonic()) - 90
        if remaining < cfg.get("min_launch_s", 240):
            return
        log = BASE / "logs" / (t["id"].replace("/", "_") + "_" + os.getenv("SLURM_JOB_ID", "local") + ".log")
        log.parent.mkdir(exist_ok=True)
        with log.open("w") as f:
            try:
                r = subprocess.run([sys.executable, str(BASE / "worker.py"), "one",
                                    "--id", t["id"], "--budget", str(min(cfg.get("task_budget_s",720), remaining))],
                                   stdout=f, stderr=subprocess.STDOUT, timeout=remaining + 75)
                if r.returncode:
                    failed.append(t["id"])
            except subprocess.TimeoutExpired:
                # The task's previous checkpoint remains available for the next submission.
                print("Wall-time guard interrupted", t["id"], flush=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=parallel) as pool:
        list(pool.map(launch, tasks))
    left = [t["id"] for t in m["tasks"] if t["pack"] == pack and not done(t)]
    print(json.dumps({"pack": pack, "left": len(left), "failed": failed}), flush=True)
    return 3 if failed else (10 if left else 0)


def release(m, apply=False):
    total = 0
    for row in m["backed_up_returns"]:
        result = safe(row["result"])
        if not result.exists() or sha(result) != row["result_sha256"]:
            continue
        cache = result.parent / "step_cache"
        if not cache.exists():
            continue
        files = [p for p in cache.rglob("*") if p.is_file()]
        expected = row["files"]
        if {str(p.relative_to(cache)).replace(os.sep, "/") for p in files} != set(expected):
            continue
        if any(sha(p) != expected[str(p.relative_to(cache)).replace(os.sep, "/")] for p in files):
            continue
        total += sum(p.stat().st_size for p in files)
        if apply:
            # Only this exact, complete, hash-verified cache is removed. Keep result.json/work/inputs.
            if not cache.resolve().is_relative_to(ROOT / "docs/thesis/hpc/rq4_newsets_20261027"):
                raise ValueError("Cleanup escaped the original RQ4 result directory")
            shutil.rmtree(cache)
    print(("Released" if apply else "Would release") + f" {total / 1e9:.2f} GB already verified on the PC.")


def collect(m):
    pending = [t["id"] for t in m["tasks"] if not done(t)]
    archive = BASE.parent / (BASE.name + "_return.tar.gz")
    files = set()
    for t in m["tasks"]:
        if t["kind"] == "rq4" and done(t):
            folder = safe(t["out"]) / "return" / ("task" + str(t["task"]))
            files.update(p for p in folder.rglob("*") if p.is_file())
    for row in m["seed_checkpoints"]:
        p = safe(row["destination"])
        if p.exists():
            files.add(p)
    files.add(BASE / "manifest.json")
    # Include the full original seed specs/manifest and worker so the original collector can run on return.
    seedroot = ROOT / m["seed_root"]
    files.update(p for p in seedroot.rglob("*.spec.json"))
    files.update(p for p in seedroot.glob("*.json"))
    if (seedroot / "worker.py").exists():
        files.add(seedroot / "worker.py")
    with tarfile.open(archive, "w:gz") as tar:
        for p in sorted(files):
            tar.add(p, arcname=str(p.relative_to(ROOT)).replace(os.sep, "/"), recursive=False)
    print(json.dumps({"archive": str(archive), "sha256": sha(archive), "pending": pending,
                      "complete": not pending}, indent=2))


def restore_rq4(m):
    restored = 0
    for t in m["tasks"]:
        if t["kind"] != "rq4" or not done(t):
            continue
        source = safe(t["out"]) / "return" / ("task" + str(t["task"]))
        target = safe(t["original_out"]) / "return" / ("task" + str(t["task"]))
        if (target / "result.json").exists():
            old = read(target / "result.json")
            if old.get("specHash") != t["specHash"]:
                raise ValueError("Original task has a different spec: " + str(target))
            if old.get("complete") and not old.get("error"):
                continue
        shutil.copytree(source, target, dirs_exist_ok=True)
        restored += 1
    print("Restored complete recovered tasks into the original import locations:", restored)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("command", choices=["prepare", "check", "status", "pack", "one", "release", "collect", "restore-rq4"])
    ap.add_argument("--pack")
    ap.add_argument("--id")
    ap.add_argument("--budget", type=int, default=720)
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    m = read(BASE / "manifest.json")
    if a.command == "prepare":
        prepare(m)
    elif a.command == "check":
        check_inputs(m)
    elif a.command == "status":
        from collections import Counter
        print(json.dumps({p: dict(Counter("complete" if done(t) else "unfinished"
                          for t in m["tasks"] if t["pack"] == p)) for p in m["packs"]}, indent=2))
    elif a.command == "one":
        run_one(next(t for t in m["tasks"] if t["id"] == a.id), a.budget)
    elif a.command == "pack":
        return run_pack(m, a.pack)
    elif a.command == "release":
        release(m, a.apply)
    elif a.command == "collect":
        collect(m)
    elif a.command == "restore-rq4":
        restore_rq4(m)
    return 0


if __name__ == "__main__":
    sys.exit(main())
