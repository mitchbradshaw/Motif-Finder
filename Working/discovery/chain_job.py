"""
chain_job.py
============
A Discovery template run as a job for the cluster, and its way back (round A_2,
P2; the researcher, 2026-10-17: "HPC template runs must come back to the Map,
to be viewed and verified in the website. Later reviews of the same algorithm
reuse cached results instead of recalculating").

**The cluster computes; the import restores the step cache; the existing local
path writes the rows.** Three halves, all headless:

* **The spec** (`build_spec`). Content, not the cluster's database: per target
  (one channel of the fan-out) the exact recipe the local sweep would execute
  (`fanout.target_recipe`: `materialize_target` plus the `surrogate` flag, which
  every cache key carries), the recording as content (its local id, source file,
  channel, rate, length, unit, repo-relative `.npy` and the file's sha1), the
  expected config hash and step-prefix hashes, the null (paired, method, seed,
  draws — Settings › Nulls, down to 1), and the matrix-profile steps to compute
  in blocks. A step that reads the live database (a `conn`-reading block, a
  Library exemplar, a source block) is refused for export by name: the cluster's
  database is a scratch copy.
* **The task** (`run_task`, ``python -m Working.discovery.chain_job --spec …
  --out … --task i``). A per-task scratch SQLite (`init_db()`), the recording row
  inserted under its LOCAL id with its local unit, so every hash equals the
  local one — asserted against the spec before anything runs. The step cache is
  redirected into the task's own folder; persist hooks are off (their files are
  not what comes back); the matrix-profile time caps are lifted (they are this
  machine's budget, not a limit on the question). The real run, then its null
  draws in the same task (a block shuffle sizes its block from the real run's
  detections). The result file is written atomically. A resubmitted task
  continues from its own cache and its finished draws; a budget stops it between
  steps, draws or profile blocks; two jobs in a row that make no progress stop
  its chain with the reason (a step longer than the wall).
* **The import** (`import_results`). Refuses on any mismatch — the spec hash,
  every expected hash, the recording content against each local id, an
  incomplete or missing task (named) — and records nothing then. Otherwise it
  copies each task's cache entries into STEP_CACHE_ROOT with their
  `step_artifacts` rows. The bridge then runs the ordinary local sweep
  (`_start_sweep` over `local_plan`): heavy steps are cache hits, cheap steps
  recompute, and every row is written by the existing code.

Why not `seed_job` or `job_export.export_job`: a seed job ships one search's
inputs and its own result format, read back by the Seed page; the chain export
ran `run_recipe.py` against a copy of the whole database, all tasks writing it
at once, its runs never coming back. This module keeps `seed_job`'s pattern
(content in the spec, atomic checkpoints, a budget, self-resubmission on a
status exit code) and reuses `job_export`'s script pieces (`_profile`,
`dependency_block`, `repo_module_closure`, `repo_relative`).

On disk, beside the spec (``<base>.chain.json``) and the script (``<base>.sh``):

    <base>_out/job.json                       what the job is (spec hash, tasks)
    <base>_out/return/task<i>/result.json     the task's result      } bring
    <base>_out/return/task<i>/step_cache/…     its cache entries      }  back
    <base>_out/work/task<i>/scratch.sqlite    the scratch database   } stays on
    <base>_out/work/task<i>/mp_chunks/…        profile-block checkpoints } the cluster

No UI imports.
"""

import argparse
import contextlib
import datetime as _dt
import hashlib
import inspect
import json
import math
import multiprocessing
import os
import shutil
import sys
import time

import numpy as np

SPEC_VERSION = 1
KIND = "detection_chain"
RESULT_KIND = "detection_chain_result"
SPEC_SUFFIX = ".chain.json"
OUT_SUFFIX = "_out"
RETURN_DIR = "return"
WORK_DIR = "work"
RESULT_NAME = "result.json"
STATE_NAME = "state.json"
JOB_NAME = "job.json"
CACHE_DIR = "step_cache"
#: two jobs in a row that cache nothing, finish no run and no profile block: the step does not fit the wall
STALL_LIMIT = 2
#: the job stops itself at this fraction of the wall, between steps / draws / profile blocks
BUDGET_FRACTION = 0.85
#: `timeout` ends the python process this long before the wall, so the status check and the resubmit still run
TIMEOUT_MARGIN_S = 90
#: resubmissions per task; the stall check, not this cap, is what stops a task that cannot progress
MIN_CHAIN = 60
#: CPUs a task asks for. `stump` scales with threads; the `cpu` partition's per-node count is not recorded here
CPU_CPUS = 8
GPU_CPUS = 4
#: an uncalibrated machine cannot size the blocks: a profile longer than two of these is computed in these
DEFAULT_BLOCK = 131_072
#: matrix-profile backends that use the GPU when asked for one (`auto` falls back to the CPU without a GPU)
GPU_BACKENDS = ("gpu_stump", "auto")
EXACT_BACKENDS = ("stump", "gpu_stump", "auto")


class ExportRefused(ValueError):
    """The chain cannot be sent to the cluster; ``steps`` names the steps and why."""

    def __init__(self, message, steps=()):
        super().__init__(message)
        self.steps = list(steps)


class ChainJobRefused(RuntimeError):
    """The cluster side refuses to compute (content or hashes are not the exported
    ones, or the task makes no progress). Written into the task's result."""


class ImportRefused(ValueError):
    """The import found a mismatch or a missing task; nothing was recorded."""


class _Stopped(Exception):
    """The budget (or a cancel) stopped the task between units of work."""


def _now():
    return _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")


def _canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def spec_hash(spec):
    """A short id for a spec: each task's result names the spec it answers."""
    return hashlib.sha1(_canonical(spec).encode("utf-8")).hexdigest()[:12]


def _read_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _write_json(path, obj, indent=None):
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=indent)
    os.replace(tmp, path)


def _name(step):
    return f"{step['stage']}.{step['algorithm']}"


_SHA1 = {}


def _file_sha1(path):
    """`matrix_profile_store.compute_data_sha1` (the profile artifacts' own staleness
    signal), remembered per (path, size, mtime): the modal's dry run, the export and
    the import each read a 721-h channel otherwise."""
    from Working.database.matrix_profile_store import compute_data_sha1

    st = os.stat(path)
    key = (os.path.abspath(path), st.st_size, st.st_mtime_ns)
    if key not in _SHA1:
        _SHA1[key] = compute_data_sha1(path)
    return _SHA1[key]


def _adapter(name):
    from Adapters.registry import discover_adapters, get_adapter
    discover_adapters()
    return get_adapter(name)


# ── the spec ────────────────────────────────────────────────────────────────

def store_reading_steps(steps):
    """The steps that read the live database while they run, with why: the
    cluster's database is a scratch copy holding the recording rows only."""
    out = []
    for i, st in enumerate(steps):
        name = _name(st)
        spec = _adapter(name)
        why = None
        if "conn" in inspect.signature(spec.run).parameters:
            why = "its block reads the database while it runs (human verdicts, saved sets)"
        elif any((b or {}).get("source_kind") == "library_exemplar" for b in (st.get("side_inputs") or {}).values()):
            why = ("its exemplar is a Library entry read from the database (a seed search goes to the cluster from "
                   "the Seed page, as its own job)")
        elif getattr(spec, "source", False):
            why = "it is a chain source: it reads saved sets from the store"
        if why:
            out.append({"index": i, "name": name, "why": why})
    return out


def _held_out_unlocked(conn, source_file):
    """True when ``source_file`` is the held-out recording and it is unlocked at
    export (fix round, F1). The cluster's scratch database is built by `init_db()`
    and has no settings row — which the lock reads as ON — so such a target
    carries ``heldOutUnlocked`` and its scratch database is written unlocked
    (`_unlock_held_out`). Unlocked is P1's one predicate, `held_out_locked`
    (Settings › Datasets' switch, or the HELD_OUT_UNLOCK override a script may
    set), against the file the runner's own guard names (a2 integration)."""
    from Working.config import HELD_OUT_RECORDING_FILE
    from Working.registration.settings import held_out_locked

    return str(source_file) == HELD_OUT_RECORDING_FILE and not held_out_locked(conn)


def _unlock_held_out(conn):
    """The scratch database's Settings › Datasets lock, OFF — as it was where the
    spec was exported (`heldOutUnlocked`)."""
    from Working.registration.settings import HELD_OUT_ON_KEY, HELD_OUT_PAGE, held_out_state, put_settings

    st = held_out_state(conn)
    if st["on"]:
        put_settings(conn, HELD_OUT_PAGE, {HELD_OUT_ON_KEY: False}, actor="chain_job (exported with the lock off)",
                     confirm_name=st["name"])


def _profile(steps):
    """Where the job runs: the a100 for a matrix profile on the GPU (or a CNN), the
    CPU partition otherwise; the wall recorded for that partition."""
    from Working.config import HPC_CONDA_ENV_CPU, HPC_CONDA_ENV_GPU, HPC_CPU_PARTITION, HPC_GPU_PARTITION
    from Working.hpc.job_export import partition_wall_minutes, recipe_uses_gpu

    gpu = recipe_uses_gpu({"steps": steps}) or any(
        _name(st) == "detection.matrix_profile" and (st.get("params") or {}).get("backend", "auto") in GPU_BACKENDS
        for st in steps)
    partition = HPC_GPU_PARTITION if gpu else HPC_CPU_PARTITION
    wall, verified = partition_wall_minutes(partition)
    return {"gpu": bool(gpu), "partition": partition, "cpus": GPU_CPUS if gpu else CPU_CPUS,
            "condaEnv": HPC_CONDA_ENV_GPU if gpu else HPC_CONDA_ENV_CPU, "wallMinutes": int(wall),
            "wallVerified": bool(verified)}


def _auto_block(n, m, profile):
    """Profile blocks for an n-sample profile that cannot finish inside one job of
    ``profile``'s wall, or None when the one-shot fits (or the GPU computes it).

    From this machine's calibration (``t = k n^2`` on all its CPUs), scaled by the
    task's CPU share; a unit (a self-join over two blocks) is held to half the
    job's budget. Uncalibrated, a profile longer than two `DEFAULT_BLOCK`s is
    computed in those."""
    if profile["gpu"]:
        return None
    from Working.Detection.matrix_profiling import cost

    budget = profile["wallMinutes"] * 60.0 * BUDGET_FRACTION
    factor = max(1.0, multiprocessing.cpu_count() / float(profile["cpus"]))
    est = cost.estimate_seconds(int(n), "stump")
    if est is None:
        return DEFAULT_BLOCK if n > 2 * DEFAULT_BLOCK else None
    if est * factor <= 0.5 * budget:
        return None
    k = est / float(n) ** 2
    return max(int(math.sqrt(0.5 * budget / (4.0 * k * factor))), int(m) + 1)


def _chunks_for(recipe, samples, fs, chunk, profile):
    """The matrix-profile steps of a target's recipe to compute in blocks."""
    out = []
    for k, st in enumerate(recipe["steps"]):
        if _name(st) != "detection.matrix_profile":
            continue
        params = _adapter("detection.matrix_profile").validate_params(st.get("params"))
        if params["backend"] not in EXACT_BACKENDS:
            continue                                     # SCRIMP++ is not an exact join
        m = int(round(float(params["window_min"]) * 60 * float(fs)))
        if chunk is None:
            block = None
        elif isinstance(chunk, dict):
            block = int(chunk["blockSamples"])
        else:
            block = _auto_block(samples, m, profile)
        if block:
            out.append({"step": k, "blockSamples": int(block)})
    return out


def build_spec(conn, plan, *, label, null, run_key=None, session_id=None, template=None, band=None, chunk="auto"):
    """The run as the cluster needs it, from a runnable `fanout.plan`.

    ``null`` is the run's null as the bridge plans it: ``{paired, params, draws}``.
    ``chunk``: ``"auto"`` sizes profile blocks from the wall and this machine's
    calibration, ``None`` never chunks, ``{"blockSamples": L}`` forces blocks."""
    from Working import run_groups as RG
    from Working.database import queries as q
    from Working.discovery import fanout
    from Working.execution import _recipe_prefix_hash, recording_units
    from Working.hpc.job_export import repo_relative
    from Working.recipes import short_hash

    if not plan.get("runnable"):
        raise ExportRefused(f"this scope cannot run: {plan.get('reason')}")
    recipe = plan["recipe"]
    steps = recipe["steps"]
    refused = store_reading_steps(steps)
    if refused:
        raise ExportRefused(
            "not sent to the cluster: " + "; ".join(f"step {s['index'] + 1:02d} ({s['name']}): {s['why']}"
                                                    for s in refused)
            + " — the cluster computes on a scratch database that holds the recording rows only", steps=refused)
    paired = bool((null or {}).get("paired"))
    draws = max(1, int((null or {}).get("draws") or 0)) if paired else 0
    params = dict((null or {}).get("params") or RG.DEFAULT_SURROGATE_PARAMS) if paired else None
    if params is not None:
        params.setdefault("method", RG.DEFAULT_SURROGATE_PARAMS["method"])
        params["seed"] = int(params.get("seed") or 0)
    profile = _profile(steps)
    targets = []
    # round A_2, P3: a windowed plan's targets are its windows; its tasks are its channels (`_window_targets`)
    for i, t in enumerate([] if plan.get("windows") else plan["targets"]):
        rec = q.get_recording_by_id(conn, int(t["recording_id"]))
        per = fanout.target_recipe(recipe, i, paired)
        units = recording_units(rec)
        npy = rec["npy_path"]
        target = {
            "index": i, "recordingId": int(rec["id"]), "sourceFile": rec["source_file"], "channel": int(rec["channel"]),
            "channelName": t["channel_name"], "fs": float(rec["fs"]), "nSamples": int(rec["n_samples"]),
            "globalOffset": int(rec["global_offset"]), "units": units,
            "unitsNote": (rec["units_note"] if "units_note" in rec.keys() else None),
            "npy": repo_relative(npy), "npySha1": _file_sha1(npy), "npyBytes": int(os.path.getsize(npy)),
            "span": list(t["span"]), "recipe": per, "configHash": short_hash(per),
            "prefixHashes": [_recipe_prefix_hash(per, k, units) for k in range(len(per["steps"]))],
            "chunks": _chunks_for(per, t["samples"], rec["fs"], chunk, profile),
        }
        if _held_out_unlocked(conn, rec["source_file"]):
            # only on such a target: every other spec (the overnight sweep's) keeps the hash it was exported with
            target["heldOutUnlocked"] = True
        targets.append(target)
    if plan.get("windows"):
        targets = _window_targets(conn, plan, paired)
    spec = {
        "version": SPEC_VERSION, "kind": KIND, "label": label, "runKey": run_key, "sessionId": session_id,
        "template": template, "band": band, "steps": steps, "span": recipe["span"],
        "sourceFile": targets[0]["sourceFile"] if targets else None,
        "null": {"paired": paired, "params": params, "draws": draws},
        "profile": profile, "tasks": len(targets), "targets": targets,
    }
    if plan.get("windows"):
        # only on a windowed spec, so every other spec keeps the hash it was exported with
        from Working.discovery import windowed as WD
        spec["windows"] = {"scope": plan["windows"]["scope"], "rule": plan["windows"]["rule"],
                           "stitch": WD.STITCH_VERSION}
    return spec


def _window_targets(conn, plan, paired):
    """A windowed plan's tasks (round A_2, P3): one per channel, as a whole-span run's, each naming its windows and
    every window's config hash.

    One target per window would be 1,441 to 8,651 array tasks per channel at the RQ4 sweep's scales (1-hour and
    10-minute windows over 721 h), a spec of tens to hundreds of megabytes, and a scratch database per window. So a
    task runs every window of its channel, and its ``recipe`` / ``configHash`` / ``prefixHashes`` are its first
    window's, which the cluster asserts before anything runs, as for any target; each later window's recipe is the
    first one over its own span (`windowed.with_span`), asserted against ``windows.configHashes`` before it runs."""
    from Working.database import queries as q
    from Working.discovery import fanout
    from Working.discovery import windowed as WD
    from Working.execution import _recipe_prefix_hash, recording_units
    from Working.hpc.job_export import repo_relative
    from Working.recipes import short_hash

    recipe = plan["recipe"]
    out = []
    for c, (rid, idxs) in enumerate(WD._channels(plan["targets"]).items()):
        t = plan["targets"][idxs[0]]
        rec = q.get_recording_by_id(conn, int(rid))
        first = fanout.target_recipe(recipe, idxs[0], paired)
        units = recording_units(rec)
        npy = rec["npy_path"]
        spans = [list(plan["targets"][i]["span"]) for i in idxs]
        target = {
            "index": c, "recordingId": int(rec["id"]), "sourceFile": rec["source_file"], "channel": int(rec["channel"]),
            "channelName": t["channel_name"], "fs": float(rec["fs"]), "nSamples": int(rec["n_samples"]),
            "globalOffset": int(rec["global_offset"]), "units": units,
            "unitsNote": (rec["units_note"] if "units_note" in rec.keys() else None),
            "npy": repo_relative(npy), "npySha1": _file_sha1(npy), "npyBytes": int(os.path.getsize(npy)),
            "span": list(t["section"]), "recipe": first, "configHash": short_hash(first),
            "prefixHashes": [_recipe_prefix_hash(first, k, units) for k in range(len(first["steps"]))],
            "chunks": [],
            "windows": {"spans": spans, "configHashes": [short_hash(WD.with_span(first, sp)) for sp in spans]},
        }
        if _held_out_unlocked(conn, rec["source_file"]):
            target["heldOutUnlocked"] = True
        out.append(target)
    return out


# ── the job script ──────────────────────────────────────────────────────────

_SCRIPT = """#!/bin/bash
#SBATCH --job-name={job_name}
#SBATCH --chdir={remote_root}
#SBATCH --output={remote_root}/logs/{base}_%A_%a.out
#SBATCH --error={remote_root}/logs/{base}_%A_%a.err
#SBATCH --time={slurm_time}
{partition_lines}
#SBATCH --cpus-per-task={cpus}
#SBATCH --array=0-{last}
{deps_block}
# Round A_2 (P2): a Discovery template run, one array task per channel ({tasks} in all). Each task
# runs the real chain and its {draws} null draw(s) on a scratch database and writes
#     {out}/return/task<i>/   (result.json and step_cache/) -- bring that folder back.
# Wall {wall} min on {partition} ({wall_note}). The task stops itself after {budget} s
# between steps, draws or profile blocks; `timeout` ends it at {timeout_s} s inside a step. While its
# result reads incomplete it resubmits ITSELF (sbatch --array=<task>), at most {max_chain} jobs; two
# jobs in a row that make no progress stop it with the reason.
CHAIN_INDEX="${{1:-1}}"
MAX_CHAIN={max_chain}
TASK="${{SLURM_ARRAY_TASK_ID:-0}}"

echo "========================================"
echo "Job ID       : $SLURM_JOB_ID (array task $TASK)"
echo "Job name     : $SLURM_JOB_NAME"
echo "Node         : $SLURMD_NODENAME"
echo "Chain        : $CHAIN_INDEX / $MAX_CHAIN"
echo "Started      : $(date)"
echo "Working dir  : $(pwd)"
echo "========================================"

mkdir -p logs

{module_line}source ~/miniconda3/etc/profile.d/conda.sh
conda activate {conda_env}

# numba (stumpy's engine) and BLAS would otherwise size their thread pools from the NODE's cores, not this
# job's allocation, and oversubscribe the {cpus} CPUs it was given
export NUMBA_NUM_THREADS="${{SLURM_CPUS_PER_TASK:-{cpus}}}"
export OMP_NUM_THREADS="${{SLURM_CPUS_PER_TASK:-{cpus}}}"

timeout --signal=TERM {timeout_s} python -m Working.discovery.chain_job --spec {spec} --out {out} --task "$TASK" --budget-s {budget}
RC=$?

echo "========================================"
echo "Run finished : $(date) (exit $RC)"

if [ "$RC" -eq 124 ]; then
    echo ">>> The budget ran out inside a step: stopped before the wall. The next job continues from this task's cache."
elif [ "$RC" -ne 0 ]; then
    echo ">>> Task $TASK stopped (exit $RC) -- NOT resubmitting."
    if [ "$RC" -eq 2 ]; then
        echo ">>> Exit 2 is 'unrecognized arguments': the cluster's Working/discovery/chain_job.py is older than this script."
        echo ">>> Pull the repo on the cluster (git pull) or copy Working/ across, then: sbatch --array=$TASK {script} $CHAIN_INDEX"
    else
        echo ">>> Read {out}/return/task$TASK/result.json ('error') and the .err log; when fixed: sbatch --array=$TASK {script} $CHAIN_INDEX"
    fi
    exit $RC
fi

python -m Working.discovery.chain_job --status --out {out} --task "$TASK"
STATUS=$?

if [ "$STATUS" -eq 0 ]; then
    echo ">>> Task $TASK complete: {out}/return/task$TASK/ -- bring {out}/return/ back when every task is."
elif [ "$STATUS" -ne 1 ]; then
    echo ">>> Task $TASK cannot continue (status $STATUS): see 'error' in {out}/return/task$TASK/result.json -- NOT resubmitting."
    exit $STATUS
elif [ "$CHAIN_INDEX" -ge "$MAX_CHAIN" ]; then
    echo ">>> Work remains but the chain cap ($MAX_CHAIN) is reached -- stopping."
    echo ">>> Resubmit by hand to continue from the cache: sbatch --array=$TASK {script} 1"
else
    NEXT=$((CHAIN_INDEX + 1))
    echo ">>> Work remains -- submitting job $NEXT of $MAX_CHAIN for task $TASK ..."
    sbatch --array="$TASK" {script} "$NEXT"
    echo ">>> Submitted. Monitor with: squeue -u $USER"
fi

echo "Finished     : $(date)"
echo "========================================"
"""


def _max_chain(spec):
    """Jobs a task may chain: twice what the local estimate says it needs, never
    under `MIN_CHAIN` (the estimate is this machine's; the stall check stops a
    task that cannot progress)."""
    from Working.Detection.matrix_profiling import cost

    prof = spec["profile"]
    budget = prof["wallMinutes"] * 60.0 * BUDGET_FRACTION
    factor = max(1.0, multiprocessing.cpu_count() / float(prof["cpus"]))
    need = 0
    for t in spec["targets"]:
        n = int(t["span"][1]) - int(t["span"][0])
        est = cost.estimate_seconds(n, "stump") if any(_name(s) == "detection.matrix_profile"
                                                       for s in t["recipe"]["steps"]) else None
        if est is None:
            continue
        work = est * factor * (1 + int(spec["null"]["draws"])) * (2.0 if t["chunks"] else 1.0)
        need = max(need, int(math.ceil(work / max(budget, 1.0))))
    return max(MIN_CHAIN, 2 * need + 4)


def write_job(spec, *, out_dir, base_name, dry_run=False):
    """The spec file, the array script and the results folder's ``job.json``.

    Returns the paths (absolute, and repo-relative as the script names them), the
    script, the ``sbatch`` line, the wall and budget, what to copy each way. With
    ``dry_run`` nothing is written (the modal's preview)."""
    from Working.config import HPC_REMOTE_REPO_ROOT
    from Working.hpc.job_export import (_location_warnings, _profile as _sched, dependency_block,
                                        repo_module_closure, repo_relative)

    prof = spec["profile"]
    spec_path = os.path.join(out_dir, base_name + SPEC_SUFFIX)
    script_path = os.path.join(out_dir, base_name + ".sh")
    result_dir = os.path.join(out_dir, base_name + OUT_SUFFIX)
    spec_repo, script_repo, out_repo = repo_relative(spec_path), repo_relative(script_path), repo_relative(result_dir)
    wall_s = int(prof["wallMinutes"]) * 60
    budget = int(wall_s * BUDGET_FRACTION)
    timeout_s = max(budget + 30, wall_s - TIMEOUT_MARGIN_S)
    h, rem = divmod(int(prof["wallMinutes"]), 60)
    slurm_time = f"{h:02d}:{rem:02d}:00"
    max_chain = _max_chain(spec)
    sched = _sched(prof["gpu"], cpus=prof["cpus"])
    code = repo_module_closure("Working.discovery.chain_job", "Working.Detection.matrix_profiling.mp_chunks")
    deps = {"code": code, "inputs": [spec_repo] + [t["npy"] for t in spec["targets"]],
            "outputs": [f"{out_repo}/{RETURN_DIR}/"]}
    script = _SCRIPT.format(
        job_name=base_name[:60], remote_root=HPC_REMOTE_REPO_ROOT, base=base_name, slurm_time=slurm_time,
        partition_lines=sched["gpu_line"], cpus=prof["cpus"], last=max(0, int(spec["tasks"]) - 1),
        deps_block=dependency_block(env=prof["condaEnv"], **deps), tasks=spec["tasks"],
        draws=spec["null"]["draws"], out=out_repo, wall=prof["wallMinutes"], partition=prof["partition"],
        wall_note=("recorded" if prof["wallVerified"] else
                   "UNVERIFIED: the conservative floor until Working/config.py records this partition's limit"),
        budget=budget, timeout_s=timeout_s, max_chain=max_chain, module_line=sched["module_line"],
        conda_env=prof["condaEnv"], spec=spec_repo, script=script_repo)
    copy_out = ([{"what": "spec", "path": spec_repo, "bytes": None},
                 {"what": "script", "path": script_repo, "bytes": None}]
                + [{"what": "channel array", "path": t["npy"], "bytes": t.get("npyBytes"),
                    "note": f"{t['sourceFile']} channel {t['channel']} ({t['channelName']})"} for t in spec["targets"]])
    made = {"spec_path": spec_path, "script_path": script_path, "result_dir": result_dir,
            "spec_repo_path": spec_repo, "script_repo_path": script_repo, "result_repo_path": out_repo,
            "return_repo_path": f"{out_repo}/{RETURN_DIR}/", "script": script,
            "sbatch_command": f"sbatch {script_repo}", "job_name": base_name, "slurm_time": slurm_time,
            "wall_minutes": prof["wallMinutes"], "wall_verified": prof["wallVerified"], "budget_s": budget,
            "timeout_s": timeout_s, "max_chain": max_chain, "profile": prof, "dependencies": deps,
            "warnings": _location_warnings(out_dir), "copy_out": copy_out, "spec_hash": spec_hash(spec),
            "tasks": spec["tasks"], "dry_run": bool(dry_run)}
    if dry_run:
        return made
    os.makedirs(out_dir, exist_ok=True)
    _write_json(spec_path, spec, indent=2)
    # LF only: sbatch refuses a script with DOS line breaks (job_export)
    with open(script_path, "w", newline="\n", encoding="utf-8") as f:
        f.write(script)
    _job_json(result_dir, spec, spec_repo)
    for t in copy_out:
        if t["bytes"] is None:
            p = spec_path if t["what"] == "spec" else script_path
            t["bytes"] = int(os.path.getsize(p))
    return made


def _job_json(result_dir, spec, spec_repo=None):
    os.makedirs(result_dir, exist_ok=True)
    p = os.path.join(result_dir, JOB_NAME)
    if not os.path.isfile(p):
        _write_json(p, {"kind": KIND, "specHash": spec_hash(spec), "tasks": int(spec["tasks"]),
                        "label": spec.get("label"), "spec": spec_repo,
                        "channels": [t["channelName"] for t in spec["targets"]]}, indent=2)


# ── the task (the cluster side) ─────────────────────────────────────────────

def _task_dirs(out_dir, task):
    return (os.path.join(out_dir, RETURN_DIR, f"task{int(task)}"), os.path.join(out_dir, WORK_DIR, f"task{int(task)}"))


@contextlib.contextmanager
def _cluster_environment(cache_root):
    """The process as a task needs it, put back afterwards: the step cache in the
    task's own folder, persist hooks off (their files are not what comes back,
    and twenty draws of a whole-channel profile are gigabytes), and no time cap
    on the matrix-profile family (it is this machine's budget, not a limit on the
    question)."""
    import Working.config as cfg
    from Adapters.registry import discover_adapters, list_adapters
    from Working.discovery.routing import TIME_CAPPED_BLOCKS

    discover_adapters()
    specs = list_adapters()
    saved_root = cfg.STEP_CACHE_ROOT
    saved_persist = {s.name: s.persist for s in specs}
    saved_caps = {s.name: s.max_span_samples for s in specs if s.name in TIME_CAPPED_BLOCKS}
    try:
        cfg.STEP_CACHE_ROOT = cache_root
        for s in specs:
            s.persist = None
            if s.name in TIME_CAPPED_BLOCKS:
                s.max_span_samples = None
        yield
    finally:
        cfg.STEP_CACHE_ROOT = saved_root
        for s in specs:
            s.persist = saved_persist.get(s.name)
            if s.name in saved_caps:
                s.max_span_samples = saved_caps[s.name]


def _resolve_npy(npy, repo_root=None):
    from Working.hpc.job_export import REPO_ROOT
    for cand in (npy, os.path.join(repo_root or REPO_ROOT, npy)):
        if cand and os.path.isfile(cand):
            return cand
    raise ChainJobRefused(f"no channel file at {npy!r} (as given, or under {repo_root or REPO_ROOT}): copy the "
                          f"exported .npy to that path first")


def _scratch(db, target, repo_root=None):
    """The per-task scratch database: `init_db()` and the recording row under its
    LOCAL id, its file verified against the spec's sha1, its unit as exported, and
    — for a held-out target exported with the lock off (``heldOutUnlocked``) — the
    held-out lock off, as it was there."""
    from Working.database import queries as q
    from Working.database.matrix_profile_store import compute_data_sha1
    from Working.database.schema import init_db
    from Working.execution import recording_units

    npy = _resolve_npy(target["npy"], repo_root)
    sha = compute_data_sha1(npy)
    if sha != target["npySha1"]:
        raise ChainJobRefused(f"{target['channelName']}: the channel file {npy} is not the exported one "
                              f"(sha1 {sha}, the spec says {target['npySha1']}) — copy the exported .npy again")
    conn = init_db(db)
    try:
        row = q.get_recording_by_id(conn, int(target["recordingId"]))
        if row is None:
            conn.execute("INSERT INTO recordings (id, source_file, channel, fs, n_samples, global_offset, npy_path, "
                         "units, units_note) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                         (int(target["recordingId"]), target["sourceFile"], int(target["channel"]),
                          float(target["fs"]), int(target["nSamples"]), int(target["globalOffset"]), npy,
                          target["units"], target.get("unitsNote")))
            conn.commit()
        elif (row["source_file"], int(row["channel"])) != (target["sourceFile"], int(target["channel"])):
            raise ChainJobRefused(f"the scratch database holds recording {row['id']} as {row['source_file']} "
                                  f"channel {row['channel']}, not {target['sourceFile']} channel {target['channel']}")
        elif row["npy_path"] != npy:
            conn.execute("UPDATE recordings SET npy_path = ? WHERE id = ?", (npy, int(row["id"])))
            conn.commit()
        if target.get("heldOutUnlocked"):
            _unlock_held_out(conn)
    finally:
        conn.close()
    conn = init_db(db)             # the schema's backfills run again here: the unit must survive them
    try:
        row = q.get_recording_by_id(conn, int(target["recordingId"]))
        if recording_units(row) != target["units"]:
            raise ChainJobRefused(f"{target['channelName']}: the scratch database reads the unit as "
                                  f"{recording_units(row)!r}, the export said {target['units']!r}")
    finally:
        conn.close()
    return npy


def _assert_hashes(db, target):
    """Every hash the scratch database produces equals the spec's (the local ones)."""
    from Working.database import queries as q
    from Working.database.schema import init_db
    from Working.execution import _recipe_prefix_hash, recording_units
    from Working.recipes import short_hash

    conn = init_db(db)
    try:
        units = recording_units(q.get_recording_by_id(conn, int(target["recordingId"])))
    finally:
        conn.close()
    recipe = target["recipe"]
    got = short_hash(recipe)
    if got != target["configHash"]:
        raise ChainJobRefused(f"{target['channelName']}: the recipe hashes {got} here, {target['configHash']} at the "
                              f"export — the code computing it differs")
    prefixes = [_recipe_prefix_hash(recipe, k, units) for k in range(len(recipe["steps"]))]
    bad = [k for k, (a, b) in enumerate(zip(prefixes, target["prefixHashes"])) if a != b]
    if bad:
        raise ChainJobRefused(f"{target['channelName']}: step {bad[0] + 1:02d}'s cache key is {prefixes[bad[0]]} here, "
                              f"{target['prefixHashes'][bad[0]]} at the export — the scratch database does not "
                              f"reproduce the local recording (unit {units!r})")
    return prefixes


def _progress_mark(db, work_dir):
    """What a job has to show for itself: cache entries, finished runs, profile blocks."""
    from Working.Detection.matrix_profiling import mp_chunks
    from Working.database.schema import init_db

    conn = init_db(db)
    try:
        n_cache = sum(1 for r in conn.execute("SELECT path FROM step_artifacts") if os.path.isdir(r[0]))
        # distinct recipes, not rows: a profile computed in blocks re-runs its cheap prefix in every job (a new row
        # each time), which is not progress
        n_runs = conn.execute("SELECT COUNT(DISTINCT config_id) FROM runs WHERE status = 'completed'").fetchone()[0]
    finally:
        conn.close()
    chunks_root = os.path.join(work_dir, "mp_chunks")
    n_blocks = sum(mp_chunks.progress(os.path.join(chunks_root, d))
                   for d in (os.listdir(chunks_root) if os.path.isdir(chunks_root) else []))
    return [int(n_cache), int(n_runs), int(n_blocks)]


def _check_stall(work_dir, mark):
    """Two jobs in a row that made no progress stop the task's chain: a step that
    does not fit the wall would otherwise resubmit until the cap."""
    path = os.path.join(work_dir, STATE_NAME)
    prev = _read_json(path) if os.path.isfile(path) else None
    stalls = (int(prev.get("stalls") or 0) + 1) if prev and prev.get("mark") == mark else 0
    _write_json(path, {"mark": mark, "stalls": stalls, "jobs": int((prev or {}).get("jobs") or 0) + 1,
                       "at": _now()})
    if stalls >= STALL_LIMIT:
        raise ChainJobRefused(
            f"no progress in {stalls} jobs in a row (the same cache entries, runs and profile blocks each time): a "
            f"step does not finish inside the wall. Run it on the GPU (backend gpu_stump), compute the profile in "
            f"blocks (export again: it sizes them from the wall), or record a longer wall for this partition")


def _stopper(t0, budget_s, should_cancel):
    def stop():
        if should_cancel is not None and should_cancel():
            return True
        return budget_s is not None and (time.time() - t0) >= float(budget_s)
    return stop


def _input_of(recipe, k, db, stop):
    """The signal step ``k`` of ``recipe`` receives: the span itself for the first
    step, else what the steps before it hand on (run through `execute_recipe`, so
    their own cache entries are the run's)."""
    from Working.database import queries as q
    from Working.database.schema import init_db
    from Working.execution import RecipeCancelled, _load_signal, execute_recipe

    if k == 0:
        conn = init_db(db)
        try:
            rec = q.get_recording_by_id(conn, recipe["recording_id"])
        finally:
            conn.close()
        return _load_signal(rec, recipe["span"])[0]
    prefix = dict(recipe)
    prefix["steps"] = recipe["steps"][:k]
    try:
        out = execute_recipe(prefix, db_path=db, force=True, should_cancel=stop)
    except RecipeCancelled:
        raise _Stopped()
    return np.asarray(out["result"].value.x)


def _precompute_chunked(recipe, k, block, db, work_dir, stop):
    """Compute step ``k``'s matrix profile in blocks (`mp_chunks`) and leave it in
    the task's step cache under the step's own key, so the run that follows reads
    it as a cache hit — the recipe, and so every hash, is the one-shot's."""
    import Working.config as cfg
    from Working.Detection.matrix_profiling import mp_chunks
    from Working.config import MP_MIN_WINDOW_SAMPLES
    from Working.database import queries as q
    from Working.database.runs import get_step_artifact, insert_step_artifact
    from Working.database.schema import init_db
    from Working.execution import _recipe_prefix_hash, recording_units
    from Working.types import Scores

    conn = init_db(db)
    try:
        rec = q.get_recording_by_id(conn, recipe["recording_id"])
        h = _recipe_prefix_hash(recipe, k, recording_units(rec))
        row = get_step_artifact(conn, h, k)
        if row is not None and os.path.isdir(row["path"]):
            return {"step": k, "prefixHash": h, "blockSamples": int(block), "units": None, "already": True}
    finally:
        conn.close()
    t0 = time.time()
    x = _input_of(recipe, k, db, stop)
    params = _adapter("detection.matrix_profile").validate_params(recipe["steps"][k].get("params"))
    fs = float(rec["fs"])
    m = int(round(float(params["window_min"]) * 60 * fs))
    if m < MP_MIN_WINDOW_SAMPLES or m >= len(x):
        raise ValueError(f"step {k + 1:02d}: a {m}-sample window does not fit a {len(x)}-sample span")
    out = mp_chunks.chunked_profile(x, m, block=block, backend=params["backend"],
                                    state_dir=os.path.join(work_dir, "mp_chunks", h), should_stop=stop)
    if not out["complete"]:
        raise _Stopped()
    padded = np.full(len(x), np.nan, dtype=np.float32)       # the adapter's own Scores: float32, NaN-padded
    padded[:len(out["P"])] = out["P"].astype(np.float32)
    cache_dir = os.path.join(cfg.STEP_CACHE_ROOT, h, str(k))
    Scores(values=padded, fs=fs).to_path(cache_dir)
    conn = init_db(db)
    try:
        insert_step_artifact(conn, h, k, cache_dir)
    finally:
        conn.close()
    return {"step": k, "prefixHash": h, "blockSamples": int(out["block"]), "units": int(out["units"]),
            "seconds": round(time.time() - t0, 1), "already": False}


def _cache_entries(db, cache_root):
    from Working.database.schema import init_db

    conn = init_db(db)
    try:
        rows = conn.execute("SELECT recipe_prefix_hash, step_index, path FROM step_artifacts "
                            "ORDER BY step_index, recipe_prefix_hash").fetchall()
    finally:
        conn.close()
    out = []
    root = os.path.abspath(cache_root)
    for h, k, p in rows:
        if not os.path.isdir(p):
            continue
        rel = os.path.relpath(os.path.abspath(p), os.path.dirname(root)).replace(os.sep, "/")
        size = sum(os.path.getsize(os.path.join(d, f)) for d, _, fs in os.walk(p) for f in fs)
        out.append({"prefixHash": h, "step": int(k), "path": rel, "bytes": int(size)})
    return out


def _versions():
    out = {"python": sys.version.split()[0], "numpy": np.__version__}
    for mod in ("stumpy", "numba", "scipy"):
        try:
            out[mod] = getattr(__import__(mod), "__version__", "?")
        except Exception:
            out[mod] = None
    return out


def _compute(spec, target, db, work_dir, stop):
    """The real run, then its null draws, in this task. Returns the pieces of the
    result; raises `_Stopped` at the budget."""
    from Working import run_groups as RG
    from Working.database import runs as R
    from Working.database.schema import init_db
    from Working.execution import RecipeCancelled, execute_recipe
    from Working.recipes import short_hash

    recipe = target["recipe"]
    chunked = []
    for ch in target.get("chunks") or []:
        chunked.append(dict(_precompute_chunked(recipe, ch["step"], ch["blockSamples"], db, work_dir, stop),
                            where="real"))
    try:
        real = execute_recipe(recipe, db_path=db, should_cancel=stop)
    except RecipeCancelled:
        raise _Stopped()
    null = spec["null"]
    draws = {"asked": int(null["draws"]) if null["paired"] else 0, "drawn": 0, "skipped": None, "params": None,
             "configHashes": [], "detections": []}
    if null["paired"]:
        conn = init_db(db)
        try:
            base, skipped = RG.surrogate_draw_params(conn, real["run_id"], null["params"])
        finally:
            conn.close()
        draws["params"], draws["skipped"] = base, skipped
        if base is not None:
            for j in range(int(null["draws"])):
                if stop():
                    raise _Stopped()
                dr = RG.surrogate_recipe(recipe, dict(base, seed=base["seed"] + j))
                for ch in target.get("chunks") or []:
                    chunked.append(dict(_precompute_chunked(dr, ch["step"] + 1, ch["blockSamples"], db, work_dir,
                                                            stop), where=f"draw {j}"))
                try:
                    d = execute_recipe(dr, db_path=db, should_cancel=stop)
                except RecipeCancelled:
                    raise _Stopped()
                conn = init_db(db)
                try:
                    R.update_run(conn, d["run_id"], surrogate_of_run_id=real["run_id"])
                finally:
                    conn.close()
                draws["configHashes"].append(short_hash(dr))
                draws["detections"].append(int(d["detections_written"]))
            draws["drawn"] = len(draws["configHashes"])
    return real, draws, chunked


def _detections_of(db_conn, run_id):
    return [[int(r[0]), int(r[1]), (float(r[2]) if r[2] is not None else None)] for r in db_conn.execute(
        "SELECT start_idx, end_idx, score FROM detections WHERE run_id = ? ORDER BY start_idx, id", (int(run_id),))]


def _compute_windows(spec, target, db, stop, *, into):
    """Every window of a windowed task (round A_2, P3), then each one's null draws, on the scratch database.

    Each window's recipe is asserted against the spec's hash before it runs; a resubmitted task reuses the windows
    its earlier jobs finished (they are completed runs in the scratch database). Each finished window is appended to
    ``into`` (the result's ``windows``) as ``{index, span, configHash, detections, stepTimings, fitted, draws:
    [{configHash, detections, stepTimings}], drawParams, drawsSkipped}``; raises `_Stopped` between windows and
    draws. Returns the result's ``run`` and ``draws`` summaries (totals over the windows)."""
    from Working import run_groups as RG
    from Working.database import runs as R
    from Working.database.schema import init_db
    from Working.discovery import windowed as WD
    from Working.execution import RecipeCancelled, execute_recipe
    from Working.recipes import short_hash

    base, w = target["recipe"], target["windows"]
    if len(w["spans"]) != len(w["configHashes"]):
        raise ChainJobRefused(f"{target['channelName']}: the spec names {len(w['spans'])} windows and "
                              f"{len(w['configHashes'])} window hashes")
    null = spec["null"]
    asked = int(null["draws"]) if null["paired"] else 0

    def timings(run_id, conn):
        row = conn.execute("SELECT step_timings_json FROM runs WHERE id = ?", (int(run_id),)).fetchone()
        return {str(a): float(b) for a, b in json.loads((row[0] if row else None) or "{}").items()}

    conn = init_db(db)
    try:
        # what earlier jobs of this task finished: read, not run again (a resubmitted job would otherwise spend its
        # wall re-reading thousands of windows through the executor)
        done = WD.lookup_windows(conn, base, w["spans"], int(target["recordingId"]), draws=asked,
                                 surrogate_params=null["params"])
        for k, (span, h) in enumerate(zip(w["spans"], w["configHashes"])):
            if stop():
                raise _Stopped()
            recipe = WD.with_span(base, span)
            got = short_hash(recipe)
            if got != h:
                raise ChainJobRefused(f"{target['channelName']}: window {k + 1}'s recipe hashes {got} here, {h} at "
                                      f"the export — the code computing it differs")
            st = done[k]
            if st["complete"]:
                real_id, draw_ids = st["real"], list(st["draws"])
                step_timings = timings(real_id, conn)
            else:
                fits = {}
                try:
                    real = execute_recipe(recipe, db_path=db, should_cancel=stop,
                                          on_step_result=WD.capture_fits(fits, recipe["steps"]))
                except RecipeCancelled:
                    raise _Stopped()
                real_id, draw_ids = int(real["run_id"]), None
                step_timings = {str(a): float(b) for a, b in (real["step_timings"] or {}).items()}
                if fits:
                    WD.save_fits(conn, real_id, fits)
            entry = {"index": k, "span": [int(span[0]), int(span[1])], "configHash": got,
                     "detections": _detections_of(conn, real_id), "stepTimings": step_timings,
                     "fitted": WD.load_fits(conn, real_id), "draws": [], "drawParams": None, "drawsSkipped": None}
            base_p = None
            if null["paired"]:
                base_p, entry["drawsSkipped"] = RG.surrogate_draw_params(conn, real_id, null["params"])
                entry["drawParams"] = base_p
            for j in range(asked if base_p is not None else 0):
                dr = RG.surrogate_recipe(recipe, dict(base_p, seed=base_p["seed"] + j))
                if draw_ids is not None:
                    d_id = draw_ids[j]
                else:
                    if stop():
                        raise _Stopped()
                    try:
                        d = execute_recipe(dr, db_path=db, should_cancel=stop)
                    except RecipeCancelled:
                        raise _Stopped()
                    d_id = int(d["run_id"])
                    R.update_run(conn, d_id, surrogate_of_run_id=real_id)
                entry["draws"].append({"configHash": short_hash(dr), "detections": _detections_of(conn, d_id),
                                       "stepTimings": timings(d_id, conn)})
            into.append(entry)
    finally:
        conn.close()
    drew = [e for e in into if e["drawParams"] is not None]
    run = {"configHash": target["configHash"], "detections": sum(len(e["detections"]) for e in into),
           "stepTimings": {}, "reused": False}
    draws = {"asked": asked, "drawn": (min(len(e["draws"]) for e in drew) if drew else 0),
             "skipped": next((e["drawsSkipped"] for e in into if e["drawsSkipped"]), None),
             # per window (`windows[].drawParams`): a block shuffle sizes its block from each window's own run
             "params": None, "configHashes": [],
             "detections": [sum(len(e["draws"][j]["detections"]) for e in drew if j < len(e["draws"]))
                            for j in range(asked)]}
    return run, draws


def run_task(spec, task, out_dir, *, budget_s=None, should_cancel=None, repo_root=None):
    """Compute task ``task`` of ``spec`` (one channel) into ``out_dir`` and return
    its result (also written to ``return/task<i>/result.json``, atomically).

    A finished task returns its result at once. ``budget_s`` stops the task
    between steps, draws and profile blocks once that long has passed (``complete``
    False, no error: the next job continues it). A refusal — the channel file or
    the hashes are not the exported ones, or the task made no progress twice — is
    the result's ``error``.

    So is anything else that goes wrong (fix round, F1): a step that raises, a lock
    the scratch database reads, a spec this code cannot read — the result carries
    the exception's words in ``error`` and its ``traceback``, so a task never ends
    without a result that says why (Jobs read such a task as *missing*, no reason
    given). Only an interruption (SystemExit, KeyboardInterrupt: SLURM ending the
    job) leaves no result, and the next job continues the task from its cache."""
    import traceback as _traceback

    t0 = time.time()
    ret_dir, work_dir = _task_dirs(out_dir, task)
    os.makedirs(ret_dir, exist_ok=True)
    os.makedirs(work_dir, exist_ok=True)
    result_path = os.path.join(ret_dir, RESULT_NAME)
    result = {"version": SPEC_VERSION, "kind": RESULT_KIND, "specHash": None, "task": int(task),
              "recordingId": None, "channelName": None, "complete": False, "error": None, "configHash": None,
              "prefixHashes": None, "run": None, "draws": None, "cache": [], "chunked": [], "elapsedS": None,
              "finishedAt": None, "host": None, "versions": None}
    try:
        if int(spec.get("version") or 0) != SPEC_VERSION or spec.get("kind") != KIND:
            raise ValueError(f"not a chain job spec this code reads (version {spec.get('version')!r}, kind "
                             f"{spec.get('kind')!r}; it reads version {SPEC_VERSION}, kind {KIND!r})")
        h = spec_hash(spec)
        target = spec["targets"][int(task)]
        result.update(specHash=h, recordingId=target["recordingId"], channelName=target["channelName"],
                      configHash=target["configHash"])
        _job_json(out_dir, spec)
        if os.path.isfile(result_path):
            try:
                prior = _read_json(result_path)
            except (OSError, ValueError):
                prior = None
            if prior and prior.get("specHash") == h and prior.get("complete"):
                return prior
        result["versions"] = _versions()
        try:
            import platform
            result["host"] = platform.node()
        except Exception:
            pass
        # round A_2, P3: a windowed task's windows come back as runs (`windows` in its result), not as cache
        # entries — each window's steps are too quick for the step cache to keep — so its cache stays in work/
        windowed = bool(target.get("windows"))
        cache_root = os.path.join(work_dir if windowed else ret_dir, CACHE_DIR)
        db = os.path.join(work_dir, "scratch.sqlite")
        with _cluster_environment(cache_root):
            _scratch(db, target, repo_root)
            result["prefixHashes"] = _assert_hashes(db, target)
            _check_stall(work_dir, _progress_mark(db, work_dir))
            stop = _stopper(t0, budget_s, should_cancel)
            try:
                if windowed:
                    result["windows"] = []
                    real, draws = _compute_windows(spec, target, db, stop, into=result["windows"])
                    result.update({"complete": True, "configHash": target["configHash"], "run": real,
                                   "draws": draws, "chunked": [], "finishedAt": _now()})
                else:
                    real, draws, chunked = _compute(spec, target, db, work_dir, stop)
                    result.update({
                        "complete": True, "configHash": real["config_hash"],
                        "run": {"configHash": real["config_hash"], "detections": int(real["detections_written"]),
                                "stepTimings": {str(k): float(v) for k, v in (real["step_timings"] or {}).items()},
                                "reused": bool(real["reused"])},
                        "draws": draws, "chunked": chunked, "finishedAt": _now()})
            except _Stopped:
                pass
            result["cache"] = [] if windowed else _cache_entries(db, cache_root)
    except ChainJobRefused as e:
        result["error"] = str(e)
    except Exception as e:                 # anything else: written down, and the task's chain stops (status 3)
        result["error"] = f"{type(e).__name__}: {e}"
        result["traceback"] = _traceback.format_exc()
    result["elapsedS"] = round(time.time() - t0, 1)
    _write_json(result_path, result)
    return result


def task_status(out_dir, task, spec=None, *, expected_hash=None):
    """``{state, reason, result}`` of one task from its result file: missing,
    partial, complete, refused (an error in it), other (another spec's) or
    unreadable. ``expected_hash`` is ``spec_hash(spec)`` when the caller has it
    already (`collect` hashes the spec once per job, not once per task)."""
    path = os.path.join(_task_dirs(out_dir, task)[0], RESULT_NAME)
    if not os.path.isfile(path):
        return {"state": "missing", "reason": "no result.json yet", "result": None}
    try:
        res = _read_json(path)
    except (OSError, ValueError) as e:
        return {"state": "unreadable", "reason": f"{type(e).__name__}: {e}", "result": None}
    want = expected_hash if expected_hash is not None else (spec_hash(spec) if spec is not None else None)
    if want is not None and res.get("specHash") != want:
        return {"state": "other", "result": res,
                "reason": f"its result was computed from spec {res.get('specHash')}, not this spec {want}"}
    if res.get("error"):
        return {"state": "refused", "reason": res["error"], "result": res}
    if res.get("complete"):
        return {"state": "complete", "reason": None, "result": res}
    return {"state": "partial", "result": res,
            "reason": "stopped part-way at its budget (the job resubmits itself until it is complete)"}


def collect(spec, out_dir):
    """Every task's state: ``{specHash, tasks: [{index, channelName, recordingId,
    state, reason, result}], done, total, complete}``."""
    h = spec_hash(spec)
    tasks = []
    for i, t in enumerate(spec["targets"]):
        st = task_status(out_dir, i, spec, expected_hash=h)
        tasks.append({"index": i, "channelName": t["channelName"], "recordingId": t["recordingId"], **st})
    done = sum(1 for t in tasks if t["state"] == "complete")
    return {"specHash": h, "tasks": tasks, "done": done, "total": len(tasks),
            "complete": done == len(tasks) and bool(tasks)}


# ── the import (this machine) ───────────────────────────────────────────────

def _local_checks(conn, spec):
    """The local recordings are the content the cluster computed on, and the local
    hashes are the spec's. Returns the problems, in words."""
    from Working.database import queries as q
    from Working.execution import _recipe_prefix_hash, recording_units
    from Working.recipes import short_hash

    problems = []
    for t in spec["targets"]:
        who = f"task {t['index']} ({t['channelName']}, recording {t['recordingId']})"
        rec = q.get_recording_by_id(conn, int(t["recordingId"]))
        if rec is None:
            problems.append(f"{who}: no such recording on this machine")
            continue
        if (rec["source_file"], int(rec["channel"])) != (t["sourceFile"], int(t["channel"])):
            problems.append(f"{who}: this machine's recording {rec['id']} is {rec['source_file']} channel "
                            f"{rec['channel']}, not {t['sourceFile']} channel {t['channel']}")
            continue
        if float(rec["fs"]) != float(t["fs"]) or int(rec["n_samples"]) != int(t["nSamples"]):
            problems.append(f"{who}: its rate or length changed since the export ({rec['fs']} Hz, "
                            f"{rec['n_samples']} samples here; {t['fs']} Hz, {t['nSamples']} at the export)")
            continue
        units = recording_units(rec)
        if units != t["units"]:
            problems.append(f"{who}: its unit is {units!r} now and was {t['units']!r} at the export — a block that "
                            f"reads the unit keys its result on it")
            continue
        if not os.path.isfile(rec["npy_path"]):
            problems.append(f"{who}: its channel file {rec['npy_path']} is not on this machine")
            continue
        sha = _file_sha1(rec["npy_path"])
        if sha != t["npySha1"]:
            problems.append(f"{who}: this machine's channel file is not the one the cluster computed on (sha1 {sha} "
                            f"here, {t['npySha1']} at the export) — the recording changed since")
            continue
        if short_hash(t["recipe"]) != t["configHash"]:
            problems.append(f"{who}: the recipe hashes {short_hash(t['recipe'])} here, {t['configHash']} in the spec")
            continue
        here = [_recipe_prefix_hash(t["recipe"], k, units) for k in range(len(t["recipe"]["steps"]))]
        if here != list(t["prefixHashes"]):
            problems.append(f"{who}: its step-cache keys differ here from the export's")
    return problems


def _expected_keys(spec, target, res):
    """The (prefix hash, step) pairs the local sweep will look up for this task —
    the real run's, and each draw's at the params the cluster resolved."""
    from Working import run_groups as RG
    from Working.execution import _recipe_prefix_hash
    from Working.recipes import short_hash

    keys = {(h, k) for k, h in enumerate(target["prefixHashes"])}
    problems = []
    draws = res.get("draws") or {}
    base = draws.get("params")
    if spec["null"]["paired"] and base is not None:
        want = dict(spec["null"]["params"] or {})
        if want.get("method") != base.get("method") or int(want.get("seed") or 0) != int(base.get("seed") or 0) or \
                (want.get("block_s") and float(want["block_s"]) != float(base.get("block_s") or 0)):
            problems.append(f"task {target['index']}: its draws ran with {base}, not the spec's {want}")
        for j, ch in enumerate(draws.get("configHashes") or []):
            dr = RG.surrogate_recipe(target["recipe"], dict(base, seed=int(base["seed"]) + j))
            if short_hash(dr) != ch:
                problems.append(f"task {target['index']}: draw {j} hashes {short_hash(dr)} here, {ch} on the cluster")
                continue
            keys |= {(_recipe_prefix_hash(dr, k, target["units"]), k) for k in range(len(dr["steps"]))}
        if len(draws.get("configHashes") or []) != int(spec["null"]["draws"]):
            problems.append(f"task {target['index']}: {len(draws.get('configHashes') or [])} of "
                            f"{spec['null']['draws']} null draws were made")
    # a null the cluster could not draw (a block shuffle over a run that found nothing) is skipped here the
    # same way, from the same detections: not a mismatch
    return keys, problems


def import_results(conn, spec, out_dir, *, cache_root):
    """Verify every task's result against the spec and this machine
    (`verify_results`), then copy the tasks' cache entries into ``cache_root``
    with their `step_artifacts` rows (`restore_cache`).

    All or nothing: any missing or incomplete task, any mismatch, and an
    `ImportRefused` says what — before anything is copied. Returns ``{tasks,
    entries, copied, already, bytes, counts}``; ``counts`` is what the cluster
    found per channel (the real run and each draw), for the run row to compare."""
    checked = verify_results(conn, spec, out_dir)
    return dict(checked, **restore_cache(conn, checked, cache_root=cache_root))


class RestoreCancelled(RuntimeError):
    """`restore_cache` stopped at a cancel, between entries: the entries already
    restored are whole and registered, none is half-copied."""

    def __init__(self, message, copied=0, already=0, size=0):
        super().__init__(message)
        self.copied, self.already, self.bytes = copied, already, size


def restore_cache(conn, checked, *, cache_root, should_cancel=None):
    """Copy the verified cache entries (`verify_results`) into ``cache_root`` and
    register them in `step_artifacts` — the executor's own layout
    (``<root>/<prefix hash>/<step>``). An entry this machine already holds is
    left as it is. The copy is the import's long part (gigabytes for twenty draws
    of whole channels), so the bridge runs it inside the sweep job.

    Each entry is copied beside its place (``<entry>.part``) and renamed in, then
    registered (fix round, F3/F4): a copy that fails part-way leaves no half entry
    where the cache reads and no row; the next restore clears the debris and
    copies it whole. ``should_cancel()`` is asked between entries; a cancel raises
    `RestoreCancelled` with the counts so far, the restored entries kept."""
    from Working.database.runs import get_step_artifact, insert_step_artifact

    copied = already = size = 0
    for h, k, src, nbytes in checked["copy"]:
        if should_cancel is not None and should_cancel():
            raise RestoreCancelled(f"the restore was cancelled after {copied + already} of {len(checked['copy'])} "
                                   f"cache entries; the ones restored are kept, whole", copied, already, size)
        row = get_step_artifact(conn, h, k)
        if row is not None and os.path.isdir(row["path"]):
            already += 1
            continue
        dst = os.path.join(cache_root, h, str(k))
        part = dst + ".part"
        for debris in (part, dst):                    # a half copy (or an unregistered entry) from before
            if os.path.isdir(debris):
                shutil.rmtree(debris)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copytree(src, part)
        os.replace(part, dst)
        insert_step_artifact(conn, h, k, dst)
        copied += 1
        size += nbytes
    out = {"copied": copied, "already": already, "bytes": size}
    if checked.get("windows") is not None:
        # round A_2, P3: a windowed job's windows are written as the runs the local sweep then reuses, one
        # transaction per channel; a cancel stops between channels, the channels written kept whole
        written = present = 0
        for i, task in enumerate(checked["windows"]):
            if should_cancel is not None and should_cancel():
                raise RestoreCancelled(f"the restore was cancelled after {i} of {len(checked['windows'])} channels' "
                                       f"windows; the ones written are kept, whole", copied, already, size)
            w, p = _write_window_rows(conn, task)
            written += w
            present += p
        out.update(windowRuns=written, windowRunsAlready=present)
    return out


def _write_window_rows(conn, task):
    """One channel's windows from a verified windowed result: each window's run and each draw's (linked to its
    window by `surrogate_of_run_id`), with their detections and what each window fitted — the rows `execute_recipe`
    would have written here, so the local sweep reuses every one. A window this machine already holds is left as it
    is. One transaction. Returns ``(written, already)``."""
    from Working.discovery import windowed as WD
    from Working.recipes import canonical_json, short_hash

    from Working import run_groups as RG

    rid = int(task["recordingId"])
    rows = task["rows"]
    now = _now()
    configs = {}                                          # config hash -> canonical json, every window and draw
    for r in rows:
        recipe = WD.with_span(task["recipe"], r["span"])
        configs[r["configHash"]] = canonical_json(recipe)
        for j, d in enumerate(r["draws"]):
            p = dict(r["drawParams"], seed=int(r["drawParams"]["seed"]) + j)
            configs[d["configHash"]] = canonical_json(RG.surrogate_recipe(recipe, p))
    with conn:
        conn.executemany("INSERT OR IGNORE INTO configs (config_hash, config_json, created_at) VALUES (?, ?, ?)",
                         [(h, js, now) for h, js in configs.items()])
    cfg = {}
    for chunk in WD._chunks(sorted(configs)):
        for row in conn.execute("SELECT id, config_hash FROM configs WHERE config_hash IN (%s)"
                                % ",".join("?" * len(chunk)), chunk):
            cfg[row[1]] = int(row[0])
    have = WD._completed(conn, rid, [r["configHash"] for r in rows], [r["span"] for r in rows])
    flat = [(k, j) for k, r in enumerate(rows) for j in range(len(r["draws"]))]
    have_draws = dict(zip(flat, WD._completed(conn, rid, [rows[k]["draws"][j]["configHash"] for k, j in flat],
                                              [rows[k]["span"] for k, _ in flat])))
    written = present = 0

    def insert(config_hash, span, dets, timings, surrogate_of=None):
        duration = float(sum(float(v) for v in (timings or {}).values()))
        cur = conn.execute(
            "INSERT INTO runs (config_id, recording_id, span_start, span_end, started_at, status, finished_at, "
            "duration_s, step_timings_json, surrogate_of_run_id) VALUES (?, ?, ?, ?, ?, 'completed', ?, ?, ?, ?)",
            (cfg[config_hash], rid, int(span[0]), int(span[1]), now, now, duration, json.dumps(timings or {}),
             surrogate_of))
        run_id = int(cur.lastrowid)
        conn.executemany("INSERT INTO detections (run_id, start_idx, end_idx, score) VALUES (?, ?, ?, ?)",
                         [(run_id, int(d[0]), int(d[1]), d[2] if len(d) > 2 else None) for d in dets])
        return run_id

    with conn:
        for k, (r, hit) in enumerate(zip(rows, have)):
            if hit is not None:
                real_id = hit[0]
                present += 1
            else:
                real_id = insert(r["configHash"], r["span"], r["detections"], r["stepTimings"])
                written += 1
                if r.get("fitted"):
                    WD.save_fits(conn, real_id, r["fitted"], commit=False)
            for j, d in enumerate(r["draws"]):
                dh = have_draws.get((k, j))
                if dh is not None and dh[1] is not None and int(dh[1]) == int(real_id):
                    present += 1
                    continue
                insert(d["configHash"], r["span"], d["detections"], d["stepTimings"], surrogate_of=real_id)
                written += 1
    return written, present


def verify_results(conn, spec, out_dir):
    """Everything an import checks, and nothing written: the spec, every task
    complete and computed from this spec, the recordings' content against each
    local id, every hash, every cache entry one this run will look up and on disk.
    Raises `ImportRefused` naming what is wrong. Returns ``{tasks, entries,
    bytesToCopy, counts, copy, importedAt}``; ``copy`` is the entries to restore,
    ``(prefix hash, step, source dir, bytes)``, and ``bytesToCopy`` their sum
    (the disk the restore needs)."""
    if int(spec.get("version") or 0) != SPEC_VERSION or spec.get("kind") != KIND:
        raise ImportRefused(f"not a chain job spec (version {spec.get('version')!r}, kind {spec.get('kind')!r})")
    st = collect(spec, out_dir)
    if not st["complete"]:
        missing = [t for t in st["tasks"] if t["state"] != "complete"]
        raise ImportRefused(
            f"{st['done']} of {st['total']} tasks are complete; nothing was imported. Not back yet or not "
            f"complete: " + "; ".join(f"task {t['index']} ({t['channelName']}): {t['reason']}" for t in missing)
            + f". Bring {os.path.join(out_dir, RETURN_DIR)} back once every task reads complete.")
    problems = _local_checks(conn, spec)
    plan_copy, counts = [], []
    windows = [] if spec.get("windows") else None
    for t, task in zip(spec["targets"], st["tasks"]):
        res = task["result"]
        if res.get("configHash") != t["configHash"] or list(res.get("prefixHashes") or []) != list(t["prefixHashes"]):
            problems.append(f"task {t['index']} ({t['channelName']}): the cluster computed config "
                            f"{res.get('configHash')}, the spec asked for {t['configHash']}")
            continue
        if t.get("windows"):
            # round A_2, P3: every window and every draw checked; the rows they make come back, not cache entries
            rows, more = _window_results(spec, t, res)
            keys = set()
            if windows is not None:
                windows.append({"recordingId": int(t["recordingId"]), "channelName": t["channelName"],
                                "recipe": t["recipe"], "rows": rows})
        else:
            keys, more = _expected_keys(spec, t, res)
        problems += more
        ret_dir = _task_dirs(out_dir, t["index"])[0]
        for e in res.get("cache") or []:
            if (e["prefixHash"], int(e["step"])) not in keys:
                problems.append(f"task {t['index']}: a cache entry ({e['prefixHash']}, step {e['step']}) belongs to "
                                f"no run of this spec")
                continue
            src = os.path.abspath(os.path.join(ret_dir, *str(e["path"]).replace("\\", "/").split("/")))
            if not src.startswith(os.path.abspath(ret_dir) + os.sep):
                problems.append(f"task {t['index']}: a cache entry's path ({e['path']}) leads out of its task folder")
                continue
            if not os.path.isdir(src):
                problems.append(f"task {t['index']} ({t['channelName']}): its cache entry {e['path']} is not in "
                                f"{ret_dir} — bring the whole return/ folder back")
                continue
            plan_copy.append((e["prefixHash"], int(e["step"]), src, int(e.get("bytes") or 0)))
        draws = res.get("draws") or {}
        counts.append({"recordingId": t["recordingId"], "channelName": t["channelName"],
                       "detections": int((res.get("run") or {}).get("detections") or 0),
                       "draws": [int(n) for n in (draws.get("detections") or [])]})
    if problems:
        raise ImportRefused("nothing was imported: " + "; ".join(problems))
    out = {"tasks": len(spec["targets"]), "entries": len(plan_copy), "counts": counts, "copy": plan_copy,
           "bytesToCopy": int(sum(c[3] for c in plan_copy)), "importedAt": _now()}
    if windows is not None:
        out["windows"] = windows
        out["windowRunsToWrite"] = sum(len(w["rows"]) + sum(len(r["draws"]) for r in w["rows"]) for w in windows)
    return out


def _window_results(spec, target, res):
    """A windowed task's result checked window by window (round A_2, P3): every window came back, over the exported
    span, computed from the exported recipe (its hash, and the same recipe rebuilt here), its detections inside its
    window; its draws at the spec's null (method and seed; a block shuffle's block twice the window's own longest
    detection) and each draw's recipe rebuilt here. Returns ``(rows, problems)``: the rows the import writes."""
    from Working import run_groups as RG
    from Working.discovery import windowed as WD
    from Working.recipes import short_hash

    who = f"task {target['index']} ({target['channelName']})"
    spans, hashes = target["windows"]["spans"], target["windows"]["configHashes"]
    got = res.get("windows") or []
    problems, rows = [], []
    if "windows" not in res:
        return [], [f"{who}: its result names no windows — the cluster's Working/discovery/chain_job.py predates "
                    f"windowed jobs (round A_2, P3), so it ran the first window only: update the code on the cluster "
                    f"and run the job again"]
    if len(got) != len(spans):
        return [], [f"{who}: {len(got)} of its {len(spans)} windows came back"]
    null = spec["null"]
    want = dict(null["params"] or {}) if null["paired"] else {}
    fs = float(target["fs"])
    for k, (w, span, h) in enumerate(zip(got, spans, hashes)):
        where = f"{who} window {k + 1}"
        if [int(x) for x in w.get("span") or ()] != [int(span[0]), int(span[1])]:
            problems.append(f"{where}: the cluster ran {w.get('span')}, the spec's window is {span}")
            continue
        if w.get("configHash") != h:
            problems.append(f"{where}: the cluster computed config {w.get('configHash')}, the spec asked for {h}")
            continue
        recipe = WD.with_span(target["recipe"], span)
        if short_hash(recipe) != h:
            problems.append(f"{where}: its recipe hashes {short_hash(recipe)} here, {h} in the spec")
            continue
        dets = w.get("detections") or []
        if any(not (int(span[0]) <= int(d[0]) <= int(d[1]) <= int(span[1])) for d in dets):
            problems.append(f"{where}: a detection lies outside its window {span}")
            continue
        row = {"index": k, "span": [int(span[0]), int(span[1])], "configHash": h, "detections": dets,
               "stepTimings": w.get("stepTimings") or {}, "fitted": w.get("fitted"), "draws": [], "drawParams": None}
        if null["paired"]:
            base = w.get("drawParams")
            if base is None:
                longest_ok = not dets
                if not (w.get("drawsSkipped") and want.get("method") == "block_shuffle" and not want.get("block_s")
                        and longest_ok):
                    problems.append(f"{where}: it drew no null ({w.get('drawsSkipped')!r}) and the spec's null is "
                                    f"{want}")
                    continue
            else:
                if base.get("method") != want.get("method") or int(base.get("seed") or 0) != int(want.get("seed") or 0):
                    problems.append(f"{where}: its draws ran with {base}, not the spec's {want}")
                    continue
                if want.get("block_s"):
                    if float(base.get("block_s") or 0) != float(want["block_s"]):
                        problems.append(f"{where}: its draws' block is {base.get('block_s')}, the spec's {want['block_s']}")
                        continue
                elif base.get("method") == "block_shuffle":
                    longest = max((int(d[1]) - int(d[0]) for d in dets), default=0) / fs
                    if not dets or abs(float(base.get("block_s") or 0) - max(2.0 * longest, 2.0 / fs)) > 1e-9:
                        problems.append(f"{where}: its draws' block ({base.get('block_s')}) is not twice its longest "
                                        f"detection")
                        continue
                draws = w.get("draws") or []
                if len(draws) != int(null["draws"]):
                    problems.append(f"{where}: {len(draws)} of {null['draws']} null draws were made")
                    continue
                bad = False
                row["drawParams"] = dict(base)
                for j, d in enumerate(draws):
                    dr = RG.surrogate_recipe(recipe, dict(base, seed=int(base["seed"]) + j))
                    if short_hash(dr) != d.get("configHash"):
                        problems.append(f"{where}: draw {j} hashes {short_hash(dr)} here, {d.get('configHash')} on "
                                        f"the cluster")
                        bad = True
                        break
                    if any(not (int(span[0]) <= int(x[0]) <= int(x[1]) <= int(span[1])) for x in d.get("detections") or []):
                        problems.append(f"{where}: a detection of draw {j} lies outside its window")
                        bad = True
                        break
                    row["draws"].append({"configHash": d["configHash"], "detections": d.get("detections") or [],
                                         "stepTimings": d.get("stepTimings") or {}})
                if bad:
                    continue
        rows.append(row)
    return rows, problems


def local_plan(conn, spec, *, ceiling_s=None):
    """The plan the local sweep runs after an import: `fanout.plan` over the
    spec's own chain, channels, span and null — never the session's current
    scope or Settings, which may have moved since the export. Refused if a target
    is refused here or its recipe is no longer the exported one."""
    from Working.discovery import fanout

    if spec.get("windows"):
        return _local_windows_plan(conn, spec, ceiling_s=ceiling_s)
    null = spec["null"]
    ids = [int(t["recordingId"]) for t in spec["targets"]]
    plan = fanout.plan(conn, steps=spec["steps"], recording_ids=ids, span=spec["span"], ceiling_s=ceiling_s,
                       null_draws=(int(null["draws"]) if null["paired"] else 0), surrogate=bool(null["paired"]),
                       surrogate_params=null["params"])
    if plan["refused"]:
        raise ImportRefused("refused here: " + "; ".join(f"recording {r['recording_id']}: {r['reason']}"
                                                         for r in plan["refused"]))
    if [t["recording_id"] for t in plan["targets"]] != ids:
        raise ImportRefused("the plan's channels are not the exported ones")
    for i, t in enumerate(spec["targets"]):
        if fanout.target_recipe(plan["recipe"], i, bool(null["paired"])) != t["recipe"]:
            raise ImportRefused(f"task {i} ({t['channelName']}): the chain is not the exported one")
    plan["channels"] = [t["channel_name"] for t in plan["targets"]]
    plan["null"] = {"paired": bool(null["paired"]), "params": null["params"],
                    "draws": int(null["draws"]) if null["paired"] else 0, "reason": None, "source": "cluster"}
    return plan


def _local_windows_plan(conn, spec, *, ceiling_s=None):
    """`local_plan` for a windowed spec (round A_2, P3): the spec's chain, channels, section, null, window scope and
    stitch rule — never the session's or Settings' — refused when a channel's windows or any window's recipe here are
    not the exported ones."""
    from Working.discovery import fanout
    from Working.discovery import windowed as WD
    from Working.recipes import short_hash

    null, w = spec["null"], spec["windows"]
    paired = bool(null["paired"])
    ids = [int(t["recordingId"]) for t in spec["targets"]]
    plan = fanout.plan(conn, steps=spec["steps"], recording_ids=ids, span=spec["span"], ceiling_s=ceiling_s,
                       null_draws=(int(null["draws"]) if paired else 0), surrogate=paired,
                       surrogate_params=null["params"], windows=w["scope"], stitch_rule=w["rule"])
    if plan["refused"]:
        raise ImportRefused("refused here: " + "; ".join(f"recording {r['recording_id']}: {r['reason']}"
                                                         for r in plan["refused"]))
    if not plan["runnable"]:
        raise ImportRefused(f"refused here: {plan['reason']}")
    chans = WD._channels(plan["targets"])
    if list(chans) != ids:
        raise ImportRefused("the plan's channels are not the exported ones")
    for t, idxs in zip(spec["targets"], chans.values()):
        who = f"task {t['index']} ({t['channelName']})"
        spans = [list(plan["targets"][i]["span"]) for i in idxs]
        if spans != [list(s) for s in t["windows"]["spans"]]:
            raise ImportRefused(f"{who}: its windows here are not the exported ones ({len(spans)} windows here, "
                                f"{len(t['windows']['spans'])} at the export) — the window scope or the way a "
                                f"section is cut changed")
        first = fanout.target_recipe(plan["recipe"], idxs[0], paired)
        if first != t["recipe"]:
            raise ImportRefused(f"{who}: the chain is not the exported one")
        if [short_hash(WD.with_span(first, sp)) for sp in spans] != list(t["windows"]["configHashes"]):
            raise ImportRefused(f"{who}: a window's recipe hashes differently here than at the export")
    plan["channels"] = [plan["targets"][idxs[0]]["channel_name"] for idxs in chans.values()]
    plan["null"] = {"paired": paired, "params": null["params"], "draws": int(null["draws"]) if paired else 0,
                    "reason": None, "source": "cluster"}
    return plan


# ── the command line (the cluster) ──────────────────────────────────────────

def _status_code(out_dir, task):
    st = task_status(out_dir, task)
    print(f"[chain_job] task {task}: {st['state']}" + (f" — {st['reason']}" if st["reason"] else ""), flush=True)
    return {"complete": 0, "missing": 1, "partial": 1}.get(st["state"], 3)


def main(argv=None):
    """``--spec S --out O --task I [--budget-s B]`` computes one task (exit 0, or 3
    when it refuses: the reason is in its result). ``--status --out O --task I``
    exits 0 when the task is complete, 1 while work remains, 3 when it cannot
    continue; ``--status --out O`` alone reports every task and exits 0 only when
    all are complete."""
    ap = argparse.ArgumentParser(description="compute one task of a Discovery chain job, or report its status")
    ap.add_argument("--spec")
    ap.add_argument("--out")
    ap.add_argument("--task", type=int, default=None)
    ap.add_argument("--status", action="store_true", help="report the task's state through the exit code")
    ap.add_argument("--budget-s", type=float, default=None, help="stop between units of work after this many seconds")
    args = ap.parse_args(argv)
    if args.status:
        if not args.out:
            ap.error("--status needs --out")
        if args.task is not None:
            return _status_code(args.out, args.task)
        job = os.path.join(args.out, JOB_NAME)
        if not os.path.isfile(job):
            print(f"[chain_job] no {JOB_NAME} in {args.out}", flush=True)
            return 1
        codes = [_status_code(args.out, i) for i in range(int(_read_json(job)["tasks"]))]
        return 3 if 3 in codes else (1 if 1 in codes else 0)
    if not args.spec or not args.out or args.task is None:
        ap.error("--spec, --out and --task are required")
    spec = _read_json(args.spec)
    res = run_task(spec, args.task, args.out, budget_s=args.budget_s)
    print(f"[chain_job] task {args.task} ({res['channelName']}): "
          + ("complete" if res["complete"] else f"refused — {res['error']}" if res["error"] else "stopped at its budget")
          + f" · {len(res['cache'])} cache entries · {res['elapsedS']} s", flush=True)
    return 3 if res["error"] else 0


if __name__ == "__main__":
    sys.exit(main())
