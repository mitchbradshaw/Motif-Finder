"""
rq4n_returns.py - on the cluster, while the remaining packs run: bring back what is finished, then free its space
without making it run again.

A task counts as done when its return/task<i>/result.json says complete (Working.discovery.chain_job.task_status).
The big part of a return is its step_cache/ folder; result.json is a few kB. So:

    python docs/thesis/hpc/rq4_newsets_20261027/remaining_20261105/rq4n_returns.py list   # new complete tasks -> a list file
    python docs/thesis/hpc/rq4_newsets_20261027/remaining_20261105/rq4n_returns.py free   # dry run
    python docs/thesis/hpc/rq4_newsets_20261027/remaining_20261105/rq4n_returns.py free --apply

`list` writes state/returned_<stamp>.txt with every complete task's return folder not listed before, for `tar -T`.
`free` deletes step_cache/ only inside folders already listed in a state/returned_*.txt AND still complete, so a task
whose cache has been freed stays complete (its result.json stays) and no pack runs it again. Only run `free` after the
tar of that list is safely on the PC.
"""
import glob
import os
import shutil
import sys
import time

REPO = os.getcwd()
sys.path.insert(0, REPO)
BATCH = os.path.join("docs", "thesis", "hpc", "rq4_newsets_20261027")
STATE = os.path.join(BATCH, "state")

from Working.discovery import chain_job  # noqa: E402


def task_dirs():
    for tf in sorted(glob.glob(os.path.join(BATCH, "tasks_rq4n_*.txt"))):
        with open(tf, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    spec, out, task, label = line.split()[:4]
                    yield out, int(task), label


def listed():
    seen = set()
    for p in glob.glob(os.path.join(STATE, "returned_*.txt")):
        with open(p, encoding="utf-8") as f:
            seen.update(l.strip() for l in f if l.strip())
    return seen


def ret_dir(out, task):
    return os.path.relpath(chain_job._task_dirs(out, task)[0])


def cmd_list():
    seen = listed()
    new = [ret_dir(o, t) for o, t, _ in task_dirs()
           if chain_job.task_status(o, t)["state"] == "complete" and ret_dir(o, t) not in seen]
    if not new:
        print("no new complete tasks")
        return 0
    os.makedirs(STATE, exist_ok=True)
    path = os.path.join(STATE, f"returned_{time.strftime('%Y%m%d-%H%M%S')}.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(new) + "\n")
    print(path)
    print(f"{len(new)} new complete tasks listed", file=sys.stderr)
    return 0


def cmd_free(apply):
    seen, freed, nbytes = listed(), 0, 0
    for o, t, label in task_dirs():
        d = ret_dir(o, t)
        sc = os.path.join(d, "step_cache")
        if d not in seen or not os.path.isdir(sc) or chain_job.task_status(o, t)["state"] != "complete":
            continue
        size = sum(os.path.getsize(os.path.join(r, x)) for r, _, fs in os.walk(sc) for x in fs)
        nbytes += size
        freed += 1
        if apply:
            shutil.rmtree(sc)
    print(f"{'freed' if apply else 'would free'} {nbytes / 1e9:.1f} GB in {freed} returned tasks"
          + ("" if apply else " (dry run: add --apply once the tar is on the PC)"))
    return 0


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in ("list", "free"):
        sys.exit(__doc__)
    sys.exit(cmd_list() if sys.argv[1] == "list" else cmd_free("--apply" in sys.argv))
