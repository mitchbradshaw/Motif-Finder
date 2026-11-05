"""
rq4n_remaining.py - the second cluster round of the 2 Hz sweep (docs/thesis/hpc/rq4_newsets_20261027): only the
tasks that did not come back complete in the first.

  * reads every task's state from the returned folders here (Working.discovery.chain_job.task_status);
  * writes remaining_20261105/tasks_rq4n_{cpu1,cpu2,gpuA,gpuB}.txt with only the tasks not complete. A task that was
    refused for memory (symbol_search at 10 s per symbol on three MJu26a channels: a 1.7 GiB array, 8 tasks to a
    node) moves from rq4n_cpu1 to rq4n_cpu2, which runs 3 at a time;
  * builds DATA/derived/hpc/rq4_newsets_20261027/rq4n_remaining_upload.tar.gz from the first round's archive (the
    same code, commit 4294c55's, the same 24 channel arrays and the same specs), with these task lists in place of the
    full ones and the remaining_20261105/ folder added.

    python scripts/thesis/rq4n_remaining.py lists      # the task lists only
    python scripts/thesis/rq4n_remaining.py archive    # the lists, then the archive and its sha256
"""
import hashlib
import io
import json
import os
import sys
import tarfile

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, REPO)
BATCH_REL = "docs/thesis/hpc/rq4_newsets_20261027"
BATCH = os.path.join(REPO, BATCH_REL)
REMAIN_REL = f"{BATCH_REL}/remaining_20261105"
REMAIN = os.path.join(REPO, REMAIN_REL)
FIRST_TAR = os.path.join(REPO, "DATA", "derived", "hpc", "rq4_newsets_20261027", "rq4_newsets_upload.tar.gz")
OUT_TAR = os.path.join(REPO, "DATA", "derived", "hpc", "rq4_newsets_20261027", "rq4n_remaining_upload.tar.gz")
MEMORY_REFUSAL = "Unable to allocate"

from Working.discovery import chain_job  # noqa: E402


def lists():
    with open(os.path.join(BATCH, "batch.json"), encoding="utf-8") as f:
        packs = [p["name"] for p in json.load(f)["packs"]]
    out = {p: [] for p in packs}
    counts = {}
    for p in packs:
        with open(os.path.join(BATCH, f"tasks_{p}.txt"), encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                spec, o, task, label = line.split()[:4]
                st = chain_job.task_status(os.path.join(REPO, o), int(task))
                if st["state"] == "complete":
                    continue
                dest = p
                if p == "rq4n_cpu1" and st["state"] == "refused" and MEMORY_REFUSAL in str(st["reason"]):
                    dest = "rq4n_cpu2"
                out[dest].append(line if line.endswith("\n") else line + "\n")
                rec = label.split("/")[0]
                counts[(dest, rec)] = counts.get((dest, rec), 0) + 1
    os.makedirs(REMAIN, exist_ok=True)
    for p, ls in out.items():
        with open(os.path.join(REMAIN, f"tasks_{p}.txt"), "w", encoding="utf-8", newline="\n") as f:
            f.writelines(ls)
        print(f"{p}: {len(ls)} tasks  " + ", ".join(f"{r} {n}" for (q, r), n in sorted(counts.items()) if q == p))
    print(f"total {sum(len(v) for v in out.values())} tasks remaining")
    return out


def archive():
    lists()
    replace = {f"{BATCH_REL}/tasks_{p}.txt": os.path.join(REMAIN, f"tasks_{p}.txt")
               for p in ("rq4n_cpu1", "rq4n_cpu2", "rq4n_gpuA", "rq4n_gpuB")}
    added = sorted(f for f in os.listdir(REMAIN) if os.path.isfile(os.path.join(REMAIN, f)))
    tmp = OUT_TAR + ".part"
    with tarfile.open(FIRST_TAR, "r:gz") as src, tarfile.open(tmp, "w:gz", compresslevel=6) as dst:
        for m in src:
            if m.name in replace:
                data = open(replace[m.name], "rb").read()
                m.size = len(data)
                dst.addfile(m, io.BytesIO(data))
            elif m.isfile():
                dst.addfile(m, src.extractfile(m))
            else:
                dst.addfile(m)
        for f in added:
            dst.add(os.path.join(REMAIN, f), arcname=f"{REMAIN_REL}/{f}")
    os.replace(tmp, OUT_TAR)
    h = hashlib.sha256()
    with open(OUT_TAR, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    print(f"{OUT_TAR}: {os.path.getsize(OUT_TAR) / 1e6:.0f} MB, sha256 {h.hexdigest()}")


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in ("lists", "archive"):
        sys.exit(__doc__)
    lists() if sys.argv[1] == "lists" else archive()
