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
  cluster's database may not hold. The channels travel by source file and
  channel index — not by a local `.npy` path, which means nothing there. The
  span, the parameters (k, cut, exclusion zone, scale bank) and the null
  (method, draws, seed) are the search's, so the cluster runs exactly the
  search the page would have.
* **The computation** (`run_spec`): per channel, the block's own candidates
  (`seeded_search.candidates`) and the null draws (`seeded_search
  .null_distances`) — the same two functions the bridge's preview calls, so a
  cluster result and a local one are the same quantity.
* **The job** (`write_job`): the spec file and an `sbatch` script that runs
  `python -m Working.discovery.seed_job --spec … --out …` from the repo root
  on the cluster, using `job_export`'s template and partition notes. One job,
  the channels in series: a seed search's cost is the null draws, and 3
  channels × 200 draws is one core's work for minutes, not an array's.

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


def _canonical(spec):
    return json.dumps(spec, sort_keys=True, separators=(",", ":"))


def spec_hash(spec):
    """A short id for a spec: the result names the spec it answers."""
    return hashlib.sha1(_canonical(spec).encode("utf-8")).hexdigest()[:12]


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
        ``{source_file, channel, name, fs}`` per channel in scope.
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
    return {
        "version": SPEC_VERSION,
        "seedId": str(seed_id),
        "label": label,
        "exemplar": [float(v) for v in np.asarray(exemplar, dtype=float).ravel()],
        "channels": [{"source_file": str(c["source_file"]), "channel": int(c["channel"]),
                      "name": str(c["name"]), "fs": float(c["fs"])} for c in channels],
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


def run_spec(spec, *, loader, on_progress=None, should_cancel=None):
    """Compute the search the spec describes.

    ``loader(channel) -> array`` hands over each channel's stored samples.
    Progress is in units of work — the search plus every draw, per channel —
    through ``on_progress(done, total, message)``.

    Returns ``{version, specHash, seedId, sourceFile, span, k, maxDistance,
    exclusion, scales, overlap, null, perChannel: [{name, source_file,
    channel, fs, candidates: [{index, distance, scale?, length?}], null:
    {distances, draws}}], elapsedS, finishedAt}`` with candidate indices
    absolute in the channel.
    """
    from Working.discovery import seeded_search

    if int(spec.get("version") or 0) != SPEC_VERSION:
        raise ValueError(f"seed job spec version {spec.get('version')!r} is not {SPEC_VERSION}")
    exemplar = np.asarray(spec["exemplar"], dtype=float)
    a, b = int(spec["span"][0]), int(spec["span"][1])
    null = spec["null"]
    draws = int(null.get("draws") or 0)
    per = 1 + draws
    total = len(spec["channels"]) * per
    t0 = time.time()
    out = []

    def say(done, msg):
        if on_progress is not None:
            on_progress(done, total, msg)

    for i, ch in enumerate(spec["channels"]):
        if should_cancel is not None and should_cancel():
            break
        say(i * per, f"{ch['name']} · matching")
        x = np.asarray(loader(ch)[a:b], dtype=float)
        found = seeded_search.candidates(x, exemplar, k=spec["k"], max_distance=spec.get("maxDistance"),
                                         scales=spec.get("scales"), overlap=spec.get("overlap") or "lowest",
                                         exclusion=spec.get("exclusion"))
        cands = []
        for c in found:
            row = {"index": a + int(c["index"]), "distance": float(c["distance"])}
            if "scale" in c:
                row["scale"] = float(c["scale"])
                row["length"] = int(c["length"])
            cands.append(row)
        channel_null = {"distances": [], "draws": 0}
        if draws > 0:
            say(i * per + 1, f"{ch['name']} · null, {draws} draws")
            nulls = seeded_search.null_distances(
                x, exemplar, draws=draws, seed=int(null.get("seed") or 0), method=null["method"],
                k=spec["k"], max_distance=spec.get("maxDistance"), fs=float(ch["fs"]),
                block_s=null.get("blockS"),
                on_progress=(lambda d, t, i=i, ch=ch: say(i * per + 1 + d, f"{ch['name']} · null {d}/{t}")),
                should_cancel=should_cancel, scales=spec.get("scales"),
                overlap=spec.get("overlap") or "lowest", exclusion=spec.get("exclusion"))
            channel_null = {"distances": [round(float(d), 4) for d in nulls["distances"]], "draws": int(nulls["draws"])}
            if nulls.get("by_scale"):
                channel_null["byScale"] = {f"{v:g}": {"distances": [round(float(d), 4) for d in part["distances"]],
                                                      "draws": int(part["draws"])}
                                           for v, part in sorted(nulls["by_scale"].items())}
        out.append({"name": ch["name"], "source_file": ch["source_file"], "channel": int(ch["channel"]),
                    "fs": float(ch["fs"]), "candidates": cands, "null": channel_null})
    say(total, "done")
    return {
        "version": SPEC_VERSION, "specHash": spec_hash(spec), "seedId": spec["seedId"],
        "sourceFile": (spec["channels"][0]["source_file"] if spec["channels"] else None),
        "span": [a, b], "k": int(spec["k"]), "maxDistance": spec.get("maxDistance"), "cut": spec.get("cut"),
        "exclusion": spec.get("exclusion"), "scales": spec.get("scales"), "overlap": spec.get("overlap") or "lowest",
        "null": dict(null), "perChannel": out,
        "elapsedS": round(time.time() - t0, 1),
        "finishedAt": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }


def write_job(spec, *, out_dir, base_name, est_seconds=None, slurm_time=None):
    """The spec file and the `sbatch` script that computes it on the cluster.

    Returns ``{script_path, spec_path, result_path, script, sbatch_command,
    job_name, slurm_time, warnings}`` — ``result_path`` repo-relative, where
    the job writes its result (the file to bring back and import)."""
    from Working.config import HPC_REMOTE_REPO_ROOT
    from Working.hpc.job_export import (_SCRIPT_TEMPLATE, _location_warnings, _profile,
                                        _slurm_time_from_estimate, repo_relative)

    os.makedirs(out_dir, exist_ok=True)
    spec_path = os.path.join(out_dir, f"{base_name}{SPEC_SUFFIX}")
    with open(spec_path, "w", encoding="utf-8") as f:
        json.dump(spec, f, indent=2)
    script_path = os.path.join(out_dir, f"{base_name}.sh")
    result_path = repo_relative(os.path.join(out_dir, f"{base_name}{RESULT_SUFFIX}"))
    if slurm_time is None:
        slurm_time = _slurm_time_from_estimate(est_seconds)
    run_command = (f"python -m Working.discovery.seed_job --spec {repo_relative(spec_path)} "
                   f"--out {result_path}")
    script = _SCRIPT_TEMPLATE.format(
        job_name=base_name, remote_root=HPC_REMOTE_REPO_ROOT, base_name=base_name,
        slurm_time=slurm_time, array_line="", run_command=run_command, **_profile(False))
    # LF only: sbatch rejects a script with DOS line breaks (see job_export)
    with open(script_path, "w", newline="\n", encoding="utf-8") as f:
        f.write(script)
    return {"script_path": script_path, "spec_path": spec_path, "result_path": result_path, "script": script,
            "sbatch_command": f"sbatch {repo_relative(script_path)}", "job_name": base_name,
            "slurm_time": slurm_time, "warnings": _location_warnings(out_dir)}


def main(argv=None):
    """The cluster side: ``--spec`` in, ``--out`` written. ``--db`` is the
    database the channels are found in (the repo's own by default)."""
    ap = argparse.ArgumentParser(description="compute a Discovery seed search from its spec")
    ap.add_argument("--spec", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--db", default=os.path.join("DATA", "db", "annotations.sqlite"))
    args = ap.parse_args(argv)
    with open(args.spec, encoding="utf-8") as f:
        spec = json.load(f)

    def progress(done, total, msg):
        print(f"[seed_job] {done}/{total} {msg}", flush=True)

    result = run_spec(spec, loader=db_loader(args.db), on_progress=progress)
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(result, f)
    print(f"[seed_job] wrote {args.out} · {sum(len(c['candidates']) for c in result['perChannel'])} candidates "
          f"· {result['elapsedS']} s", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
