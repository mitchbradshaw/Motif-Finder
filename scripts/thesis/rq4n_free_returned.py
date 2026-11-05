"""
rq4n_free_returned.py - after an import, delete the returned step-cache copies the import has already restored.

`adopt` copies each returned task's step_cache/<hash>/<step>/ into DATA/derived/step_cache/. Once there, the returned
copy is a duplicate. A task's returned step_cache/ is deleted only when the step cache holds every one of its entries with every file
at the same byte size (all or nothing, so a part-failed import can be run again); result.json is always kept (it is the record, and it keeps the task "complete"). Only whole jobs of the
recordings named are touched (the ones imported).

    python scripts/thesis/rq4n_free_returned.py MJu26a_fs2            # dry run
    python scripts/thesis/rq4n_free_returned.py MJu26a_fs2 --apply
"""
import json
import os
import shutil
import sys

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
BATCH = os.path.join(REPO, "docs", "thesis", "hpc", "rq4_newsets_20261027")
CACHE = os.path.join(REPO, "DATA", "derived", "step_cache")


def same(ret_entry, cache_entry):
    if not os.path.isdir(cache_entry):
        return False
    for root, _, files in os.walk(ret_entry):
        for f in files:
            a = os.path.join(root, f)
            b = os.path.join(cache_entry, os.path.relpath(a, ret_entry))
            if not os.path.isfile(b) or os.path.getsize(a) != os.path.getsize(b):
                return False
    return True


def main(recordings, apply):
    with open(os.path.join(BATCH, "rq4n_status.json"), encoding="utf-8") as f:
        rows = [r for r in json.load(f) if r["whole"] and r["recording"] in recordings]
    freed = kept = 0
    for r in rows:
        ret = os.path.join(REPO, r["out"], "return")
        for task in sorted(os.listdir(ret)):
            sc = os.path.join(ret, task, "step_cache")
            if not os.path.isdir(sc):
                continue
            entries = [(h, step) for h in os.listdir(sc) for step in os.listdir(os.path.join(sc, h))]
            sizes = {k: sum(os.path.getsize(os.path.join(a, x)) for a, _, fs in os.walk(os.path.join(sc, *k))
                            for x in fs) for k in entries}
            # all or nothing per task: a job whose import failed part-way restored only some of a task's entries,
            # and a re-import needs every one of them still in return/
            if entries and all(same(os.path.join(sc, *k), os.path.join(CACHE, *k)) for k in entries):
                freed += sum(sizes.values())
                if apply:
                    shutil.rmtree(sc)
            else:
                kept += sum(sizes.values())
    print(f"{len(rows)} whole jobs on {', '.join(recordings)}: {'freed' if apply else 'would free'} "
          f"{freed / 1e9:.1f} GB; {kept / 1e9:.2f} GB kept (no matching step-cache entry)")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        sys.exit(__doc__)
    main(args, "--apply" in sys.argv)
