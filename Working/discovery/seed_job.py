"""
seed_job.py
===========
A seed search as a job for the HPC (RQ2, the researcher's request of
2026-10-06): a seed search that would take longer than the local ceiling is
not run in the browser's bridge but written as a SLURM job, computed on the
cluster, and its result brought back and imported.

Three halves, all headless (this module is in `Working/` and imports nothing
from the web UI):

* **The spec** (`build_spec`): everything the cluster needs, as plain JSON.
  The exemplar travels as its own samples — not as a library row id, which the
  cluster's database may not hold. The channels travel by source file,
  channel index and the **repo-relative** `.npy` file (`DATA/derived/channels/
  <stem>/CHn.npy`) — the file the job reads, named so the transfer can be read
  off the script. The span, the parameters (k, exclusion zone, scale bank) and
  the null (method, draws, seed) are the search's, so the cluster runs exactly
  the search the page would have. The search runs **uncut**, like the page's
  preview (which re-thresholds what it fetched); the cut rides along for the
  run row.
* **The computation** (`run_spec`): per channel, the block's own candidates
  (`seeded_search.candidates`) and the null draws (`seeded_search
  .null_distances`) — the same two functions the bridge's preview calls, so a
  cluster result and a local one are the same quantity. With ``checkpoint``
  the result file is written after every channel and every ten draws, and a
  run started over an incomplete file **continues it** — the same draws, in
  the same order, because each chunk draws from the seed it would have drawn
  from anyway. A job killed at the wall loses minutes, not the run (2026-10-07:
  a 721 h × 16-channel search is hours; the account's wall is 20 minutes).
* **The job** (`write_job`): the spec file and an `sbatch` script that runs
  `python -m Working.discovery.seed_job --spec … --out …` from the repo root
  on the cluster, lists what it needs there in its comments, and resubmits
  itself while the result reads incomplete (the window-matrix chain's
  pattern, capped).

The result file is small (candidates and null distances, no samples) and is
what `/api/discovery/seed/import` takes.
"""

import argparse
import hashlib
import json
import os
import sys
import time

import numpy as np

SPEC_VERSION = 1

#: `python -m Working.discovery.seed_job` is run from the repo root on the
#: cluster (the script's own `--chdir`), so these are repo-relative.
RESULT_SUFFIX = ".result.json"
SPEC_SUFFIX = ".spec.json"
#: Draws between checkpoints: at 4 s a draw over 721 h, forty seconds of work.
CHECKPOINT_DRAWS = 10
#: Resubmissions a seed job may chain: 16 channels × 721 h at a 20-minute wall
#: is about a dozen; a bug that always reads incomplete stops here.
MAX_CHAIN = 30


def _canonical(spec):
    return json.dumps(spec, sort_keys=True, separators=(",", ":"))


def spec_hash(spec):
    """A short id for a spec: the result names the spec it answers."""
    return hashlib.sha1(_canonical(spec).encode("utf-8")).hexdigest()[:12]


def _repo_rel(path):
    from Working.hpc.job_export import repo_relative
    return repo_relative(path)


def build_spec(*, seed_id, exemplar, channels, span, k, max_distance, null, exclusion=None,
               scales=None, overlap="lowest", label=None, cut=None):
    """The search as the cluster needs it.

    Parameters
    ----------
    seed_id : str
        The page's seed id (`source:recording:start:end`), carried for the
        import to match the result to its session.
    exemplar : array-like
        The seed's own samples, in the unit the stored channel is in.
    channels : list[dict]
        ``{source_file, channel, name, fs, npy_path?}`` per channel in scope;
        ``npy_path`` (the recordings row's) becomes the repo-relative ``npy``.
    span : (int, int)
        The section in absolute samples.
    k, max_distance, exclusion, scales, overlap
        `seeded_search.candidates`' parameters. ``max_distance`` None is "no cut".
    cut : float, optional
        The cut the RUN will keep, carried through to the result untouched. The
        search itself runs uncut (the page fetches every candidate once and
        re-thresholds), so one result serves the histogram and the run.
    null : dict
        ``{method, draws, seed?, block_s?}``.
    """
    chans = []
    for c in channels:
        row = {"source_file": str(c["source_file"]), "channel": int(c["channel"]),
               "name": str(c["name"]), "fs": float(c["fs"])}
        if c.get("npy_path"):
            row["npy"] = _repo_rel(c["npy_path"])
        chans.append(row)
    return {
        "version": SPEC_VERSION,
        "seedId": str(seed_id),
        "label": label,
        "exemplar": [float(v) for v in np.asarray(exemplar, dtype=float).ravel()],
        "channels": chans,
        "span": [int(span[0]), int(span[1])],
        "k": int(k),
        "maxDistance": (None if max_distance is None or float(max_distance) <= 0 else float(max_distance)),
        "cut": (None if cut is None else float(cut)),
        "exclusion": (None if exclusion is None else float(exclusion)),
        "scales": ([float(v) for v in scales] if scales else None),
        "overlap": overlap or "lowest",
        "null": {"method": null["method"], "draws": int(null["draws"]), "seed": int(null.get("seed") or 0),
                 "blockS": (float(null["block_s"]) if null.get("block_s") else None)},
    }


def db_loader(db_path):
    """A loader that finds each channel in a database by source file and
    channel index — the cluster's own copy, or the bridge's sandbox copy — and
    returns its stored samples."""
    from Working.database import queries as q
    from Working.database.schema import init_db

    def load(ch):
        conn = init_db(db_path)
        try:
            rows = [r for r in q.list_recordings(conn, ch["source_file"]) if int(r["channel"]) == int(ch["channel"])]
        finally:
            conn.close()
        if not rows:
            raise FileNotFoundError(f"no recording for {ch['source_file']} channel {ch['channel']} in {db_path}")
        return np.load(rows[0]["npy_path"], mmap_mode="r")
    return load


def file_loader(db_path=None):
    """The cluster's loader: the channel's own file named in the spec (as given,
    then under the repo root), and only failing that a database by
    `db_loader`. A job whose spec names its files needs no database."""
    from Working.hpc.job_export import REPO_ROOT
    fallback = db_loader(db_path) if db_path else None

    def load(ch):
        npy = ch.get("npy")
        if npy:
            for cand in (npy, os.path.join(REPO_ROOT, npy)):
                if os.path.isfile(cand):
                    return np.load(cand, mmap_mode="r")
        if fallback is None:
            raise FileNotFoundError(f"{ch['name']}: no file at {npy!r} and no database to ask")
        return fallback(ch)
    return load


def _read_checkpoint(path, spec):
    if not path or not os.path.isfile(path):
        return None
    with open(path, encoding="utf-8") as f:
        saved = json.load(f)
    if saved.get("specHash") != spec_hash(spec):
        return None                      # another spec's file: start afresh
    return saved


def _write_checkpoint(path, result):
    if not path:
        return
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(result, f)
    os.replace(tmp, path)


def _result_shell(spec, per_channel, complete, t0):
    a, b = int(spec["span"][0]), int(spec["span"][1])
    return {
        "version": SPEC_VERSION, "specHash": spec_hash(spec), "seedId": spec["seedId"],
        "sourceFile": (spec["channels"][0]["source_file"] if spec["channels"] else None),
        "span": [a, b], "k": int(spec["k"]), "maxDistance": spec.get("maxDistance"), "cut": spec.get("cut"),
        "exclusion": spec.get("exclusion"), "scales": spec.get("scales"), "overlap": spec.get("overlap") or "lowest",
        "null": dict(spec["null"]), "perChannel": per_channel, "complete": bool(complete),
        "elapsedS": round(time.time() - t0, 1),
        "finishedAt": (time.strftime("%Y-%m-%dT%H:%M:%S") if complete else None),
    }


def _merge_null(into, nulls):
    into["distances"].extend(round(float(d), 4) for d in nulls["distances"])
    into["draws"] += int(nulls["draws"])
    if nulls.get("by_scale"):
        bs = into.setdefault("byScale", {})
        for v, part in nulls["by_scale"].items():
            slot = bs.setdefault(f"{float(v):g}", {"distances": [], "draws": 0})
            slot["distances"].extend(round(float(d), 4) for d in part["distances"])
            slot["draws"] += int(part["draws"])


def run_spec(spec, *, loader, on_progress=None, should_cancel=None, checkpoint=None):
    """Compute the search the spec describes.

    ``loader(channel) -> array`` hands over each channel's stored samples.
    Progress is in units of work — the search plus every draw, per channel —
    through ``on_progress(done, total, message)``. With ``checkpoint`` (a file
    path) the result so far is written after every channel and every
    `CHECKPOINT_DRAWS` draws, and an existing file for this spec is continued.

    Returns ``{version, specHash, seedId, sourceFile, span, k, maxDistance,
    cut, exclusion, scales, overlap, null, perChannel: [{name, source_file,
    channel, fs, candidates: [{index, distance, scale?, length?}], null:
    {distances, draws}}], complete, elapsedS, finishedAt}`` with candidate
    indices absolute in the channel. ``complete`` is False after a cancel.
    """
    from Working.discovery import seeded_search

    if int(spec.get("version") or 0) != SPEC_VERSION:
        raise ValueError(f"seed job spec version {spec.get('version')!r} is not {SPEC_VERSION}")
    exemplar = np.asarray(spec["exemplar"], dtype=float)
    a, b = int(spec["span"][0]), int(spec["span"][1])
    null = spec["null"]
    draws = int(null.get("draws") or 0)
    base_seed = int(null.get("seed") or 0)
    per = 1 + draws
    total = len(spec["channels"]) * per
    t0 = time.time()
    saved = _read_checkpoint(checkpoint, spec)
    if saved and saved.get("complete"):
        return saved
    done_rows = {r["name"]: r for r in (saved or {}).get("perChannel", [])}
    out = []

    def say(done, msg):
        if on_progress is not None:
            on_progress(done, total, msg)

    def cancelled():
        return should_cancel is not None and should_cancel()

    def save(complete=False):
        _write_checkpoint(checkpoint, _result_shell(spec, out, complete, t0))

    for i, ch in enumerate(spec["channels"]):
        prior = done_rows.get(ch["name"])
        if prior and not prior.get("partial"):
            out.append(prior)                 # finished in an earlier submission
            continue
        if cancelled():
            save(False)
            return _result_shell(spec, out, False, t0)
        x = None
        if prior:
            row = dict(prior)
        else:
            say(i * per, f"{ch['name']} · matching")
            x = np.asarray(loader(ch)[a:b], dtype=float)
            found = seeded_search.candidates(x, exemplar, k=spec["k"], max_distance=spec.get("maxDistance"),
                                             scales=spec.get("scales"), overlap=spec.get("overlap") or "lowest",
                                             exclusion=spec.get("exclusion"))
            cands = []
            for c in found:
                r = {"index": a + int(c["index"]), "distance": float(c["distance"])}
                if "scale" in c:
                    r["scale"] = float(c["scale"])
                    r["length"] = int(c["length"])
                cands.append(r)
            row = {"name": ch["name"], "source_file": ch["source_file"], "channel": int(ch["channel"]),
                   "fs": float(ch["fs"]), "candidates": cands, "null": {"distances": [], "draws": 0}}
        out.append(row)
        # the draws, in chunks: chunk n draws from seed base + drawn, exactly the
        # seeds an uninterrupted run would have used next
        while row["null"]["draws"] < draws:
            if cancelled():
                row["partial"] = True
                save(False)
                return _result_shell(spec, out, False, t0)
            if x is None:
                x = np.asarray(loader(ch)[a:b], dtype=float)
            drawn = row["null"]["draws"]
            want = min(CHECKPOINT_DRAWS, draws - drawn)
            say(i * per + 1 + drawn, f"{ch['name']} · null {drawn}/{draws}")
            nulls = seeded_search.null_distances(
                x, exemplar, draws=want, seed=base_seed + drawn, method=null["method"],
                k=spec["k"], max_distance=spec.get("maxDistance"), fs=float(ch["fs"]),
                block_s=null.get("blockS"),
                on_progress=(lambda d, t, i=i, ch=ch, drawn=drawn: say(i * per + 1 + drawn + d,
                                                                       f"{ch['name']} · null {drawn + d}/{draws}")),
                should_cancel=should_cancel, scales=spec.get("scales"),
                overlap=spec.get("overlap") or "lowest", exclusion=spec.get("exclusion"))
            _merge_null(row["null"], nulls)
            if nulls["draws"] < want:          # cancelled inside the chunk
                row["partial"] = True
                save(False)
                return _result_shell(spec, out, False, t0)
            row["partial"] = row["null"]["draws"] < draws
            save(False)
        row.pop("partial", None)
        save(False)
    say(total, "done")
    result = _result_shell(spec, out, True, t0)
    _write_checkpoint(checkpoint, result)
    return result


def _seed_script(*, base_name, spec_repo_path, result_repo_path, slurm_time, deps_block, script_repo_path):
    from Working.config import HPC_REMOTE_REPO_ROOT
    from Working.hpc.job_export import _profile
    prof = _profile(False)
    return f"""#!/bin/bash
#SBATCH --job-name={base_name}
#SBATCH --chdir={HPC_REMOTE_REPO_ROOT}
#SBATCH --output={HPC_REMOTE_REPO_ROOT}/logs/{base_name}_%j.out
#SBATCH --error={HPC_REMOTE_REPO_ROOT}/logs/{base_name}_%j.err
#SBATCH --time={slurm_time}
{prof['gpu_line']}
#SBATCH --cpus-per-task={prof['cpus']}
{deps_block}
# Chain position, incremented on each resubmit: the job writes its result after
# every channel and every {CHECKPOINT_DRAWS} draws, and continues it from where the
# wall cut it. Capped at {MAX_CHAIN} so a bug that always reads incomplete stops.
CHAIN_INDEX="${{1:-1}}"
MAX_CHAIN={MAX_CHAIN}

echo "========================================"
echo "Job ID       : $SLURM_JOB_ID"
echo "Job name     : $SLURM_JOB_NAME"
echo "Node         : $SLURMD_NODENAME"
echo "Chain        : $CHAIN_INDEX / $MAX_CHAIN"
echo "Started      : $(date)"
echo "Working dir  : $(pwd)"
echo "========================================"

mkdir -p logs

{prof['module_line']}source ~/miniconda3/etc/profile.d/conda.sh
conda activate {prof['conda_env']}

python -m Working.discovery.seed_job --spec {spec_repo_path} --out {result_repo_path}

echo "========================================"
echo "Run finished : $(date)"

python -m Working.discovery.seed_job --status {result_repo_path}
STATUS=$?

if [ "$STATUS" -eq 0 ]; then
    echo ">>> Result complete: {result_repo_path} -- bring it back and import it on the Seed page."
elif [ "$CHAIN_INDEX" -ge "$MAX_CHAIN" ]; then
    echo ">>> Work remains but the chain cap ($MAX_CHAIN) is reached -- stopping."
    echo ">>> Resubmit manually if this is expected: sbatch {script_repo_path} 1"
else
    NEXT=$((CHAIN_INDEX + 1))
    echo ">>> Work remains -- submitting job $NEXT of $MAX_CHAIN ..."
    sbatch {script_repo_path} "$NEXT"
    echo ">>> Submitted. Monitor with: squeue -u $USER"
fi

echo "Finished     : $(date)"
echo "========================================"
"""


def write_job(spec, *, out_dir, base_name, est_seconds=None, slurm_time=None):
    """The spec file and the `sbatch` script that computes it on the cluster.

    Returns ``{script_path, spec_path, result_path, script, sbatch_command,
    job_name, slurm_time, warnings, dependencies}`` — ``result_path``
    repo-relative, where the job writes its result (the file to bring back and
    import); ``dependencies`` the code, inputs and outputs the script's
    comments list."""
    from Working.config import HPC_CONDA_ENV_CPU
    from Working.hpc.job_export import (_location_warnings, _slurm_time_from_estimate, dependency_block,
                                        repo_module_closure, repo_relative)

    os.makedirs(out_dir, exist_ok=True)
    spec_path = os.path.join(out_dir, f"{base_name}{SPEC_SUFFIX}")
    with open(spec_path, "w", encoding="utf-8") as f:
        json.dump(spec, f, indent=2)
    script_path = os.path.join(out_dir, f"{base_name}.sh")
    spec_repo_path = repo_relative(spec_path)
    script_repo_path = repo_relative(script_path)
    result_path = repo_relative(os.path.join(out_dir, f"{base_name}{RESULT_SUFFIX}"))
    if slurm_time is None:
        slurm_time = _slurm_time_from_estimate(est_seconds)
    deps = {
        "code": repo_module_closure("Working.discovery.seed_job"),
        "inputs": [spec_repo_path] + [c["npy"] for c in spec["channels"] if c.get("npy")],
        "outputs": [result_path],
    }
    script = _seed_script(base_name=base_name, spec_repo_path=spec_repo_path, result_repo_path=result_path,
                          slurm_time=slurm_time, script_repo_path=script_repo_path,
                          deps_block=dependency_block(env=HPC_CONDA_ENV_CPU, **deps))
    # LF only: sbatch rejects a script with DOS line breaks (see job_export)
    with open(script_path, "w", newline="\n", encoding="utf-8") as f:
        f.write(script)
    return {"script_path": script_path, "spec_path": spec_path, "result_path": result_path, "script": script,
            "sbatch_command": f"sbatch {script_repo_path}", "job_name": base_name,
            "slurm_time": slurm_time, "warnings": _location_warnings(out_dir), "dependencies": deps}


def main(argv=None):
    """The cluster side: ``--spec`` in, ``--out`` written (and continued, if it
    already holds part of this spec's result). ``--db`` is a database to find
    channels in when the spec names no file. ``--status <result>`` alone exits
    0 when the result is complete, 1 otherwise."""
    ap = argparse.ArgumentParser(description="compute a Discovery seed search from its spec")
    ap.add_argument("--spec")
    ap.add_argument("--out")
    ap.add_argument("--db", default=None,
                    help="database to find channels in when the spec names no file (default: DATA/db/annotations.sqlite if present)")
    ap.add_argument("--status", default=None, help="a result file: exit 0 if complete, 1 if not")
    args = ap.parse_args(argv)
    if args.status:
        if not os.path.isfile(args.status):
            print(f"[seed_job] no result yet at {args.status}")
            return 1
        with open(args.status, encoding="utf-8") as f:
            done = bool(json.load(f).get("complete"))
        print(f"[seed_job] {args.status}: {'complete' if done else 'incomplete'}")
        return 0 if done else 1
    if not args.spec or not args.out:
        ap.error("--spec and --out are required")
    with open(args.spec, encoding="utf-8") as f:
        spec = json.load(f)
    db = args.db if args.db else (os.path.join("DATA", "db", "annotations.sqlite")
                                  if os.path.isfile(os.path.join("DATA", "db", "annotations.sqlite")) else None)

    def progress(done, total, msg):
        print(f"[seed_job] {done}/{total} {msg}", flush=True)

    result = run_spec(spec, loader=file_loader(db), on_progress=progress, checkpoint=args.out)
    print(f"[seed_job] {'wrote' if result['complete'] else 'checkpointed'} {args.out} · "
          f"{sum(len(c['candidates']) for c in result['perChannel'])} candidates · {result['elapsedS']} s", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
