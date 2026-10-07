"""
job_export.py
===============
Headless HPC job generation for matrix-profile runs
(MATRIX_PROFILE_UI_PROMPT.md §5). Generates a recipe JSON in exactly the
shape `Pipelines/run_recipe/run_recipe.py` reads, plus an `sbatch` script
that invokes it — no SSH, no submission from here. `Working/` must not
import Panel; this module doesn't either.

`export_mp_job` deliberately goes through `run_recipe.py`, not
`Pipelines/matrix_profile/run_matrix_profile.py` directly — the latter has
`CH`/`FILE`/`WINDOW_MIN` as module-level constants that would need editing
per job (exactly what `HPC/README.md` says not to do). Going through
`run_recipe.py` also means the cluster run registers its own
`runs`/`artifacts` rows via `detection.matrix_profile`'s `persist` hook,
so a returned `.npz` slots into the browser with no separate import step.

Two things this module does NOT resolve on its own:

1. **`--chdir`.** `HPC/README.md` records that hand-written job scripts
   disagree (`/home/s4699158/CNN` in `score_job.sh` vs
   `/home/Student/s4699158/CNN` in `wm_job.sh`/`mp_job.sh`). Generated
   scripts use `Working.config.HPC_REMOTE_REPO_ROOT` — confirm that value
   is actually correct for your account before submitting anything it
   produces.
2. **Getting the files to the cluster.** This only writes into the local
   working tree (`HPC/Detection/generated/` by default). The generated
   `.sh`/`.json` pair still needs to reach rangpur the same way the
   hand-written scripts do (git sync, scp, ...) before `sbatch` can run it.
3. **Partition names.** `HPC_CPU_PARTITION`/`HPC_GPU_PARTITION`
   (`Working/config.py`) are this account's real partition names as of
   2026-08-31 (`sinfo`/`scontrol show partition`) — a reconfiguration
   (rangpur's login banner warns these do happen) could rename or remove
   them again. If `sbatch` ever says `invalid partition specified`, re-run
   `sinfo -o "%P %a %l %D %G %f"` before guessing a replacement string —
   two rounds of guessing (`gpu`, then `--partition=gpu` without `--gres`)
   both failed against the live account before the real names were pulled
   from `sinfo` directly.
"""

import json
import math
import os

from Working.config import (
    CLUSTER_ROUTING_CEILING_S, HPC_CONDA_ENV_CPU, HPC_CONDA_ENV_GPU,
    HPC_CPU_PARTITION, HPC_GPU_PARTITION, HPC_MAX_WALLTIME_MINUTES,
    HPC_REMOTE_REPO_ROOT,
)
from Working.database import queries as q
from Working.database.runs import get_or_create_config
from Working.recipes import make_recipe

DEFAULT_OUT_DIR = os.path.join("HPC", "Detection", "generated")
DEFAULT_WM_OUT_DIR = os.path.join("HPC", "Preprocessing", "generated")

# The repository root on THIS machine: an absolute `out_dir` is baked into the
# script relative to it (fixup-ab). Working/hpc/job_export.py -> three levels up.
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Steps that run a CNN and so need the GPU partition. Everything else — the
# window matrix's statistics, the Gramian/recurrence IMAGE encodings (numpy),
# clustering, the classifier's forest; matrix profiles go through
# `export_mp_job`, which asks explicitly — is a CPU job.
_GPU_ALGORITHMS = {"cnn_score"}


def outside_repo(path):
    """True when an absolute `path` does not lie under `REPO_ROOT`."""
    p = str(path)
    if not os.path.isabs(p):
        return False
    try:
        rel = os.path.relpath(os.path.abspath(p), REPO_ROOT)
    except ValueError:   # another drive on Windows
        return True
    return rel == ".." or rel.startswith(".." + os.sep) or os.path.isabs(rel)


def repo_relative(path):
    """`path` as the job will see it after `--chdir` to the remote repo root:
    repo-relative with forward slashes. A relative path is taken as already
    repo-relative (the exporter's contract since T-HPC); an absolute one under
    the repo is made relative to `REPO_ROOT` — baking it verbatim wrote a
    `C:/Users/...` path under a Linux `--chdir` (fixup-ab, measured on
    Discovery's `/slurm`). One OUTSIDE the repo cannot be synced to the same
    place; it is baked as given and the export result says so (`warnings`)."""
    p = str(path)
    if os.path.isabs(p) and not outside_repo(p):
        p = os.path.relpath(os.path.abspath(p), REPO_ROOT)
    return p.replace(os.sep, "/")


def _location_warnings(out_dir):
    if outside_repo(out_dir):
        return [f"{out_dir} is outside the repo ({REPO_ROOT}): the script names it as it is here, and it will not "
                "resolve under the cluster's repo root. Export inside the repo to sync it."]
    return []


def recipe_uses_gpu(recipe):
    """True when a step of `recipe` runs a CNN (a window matrix with its `cnn`
    stage on, or a CNN block)."""
    for step in recipe.get("steps") or []:
        if step.get("algorithm") in _GPU_ALGORITHMS:
            return True
        if step.get("algorithm") == "window_matrix" and (step.get("params") or {}).get("cnn"):
            return True
    return False

_MIN_TIME_MINUTES = 30
_TIME_ROUND_MINUTES = 15
_TIME_SAFETY_FACTOR = 3  # est_seconds is from a DIFFERENT machine than the one the job lands on


def _slurm_time_from_estimate(est_seconds):
    """`--time`, per MATRIX_PROFILE_UI_PROMPT.md §5: `est_seconds * 3`,
    rounded up to the next 15 minutes, floor 30 minutes. `None` (no
    calibration on this machine) also floors to 30 minutes — a
    deliberately conservative default, not a guessed estimate.

    Then clamped to `HPC_MAX_WALLTIME_MINUTES`: this account's QOS rejects
    submission outright above that wall-clock (`Working/config.py`), so the
    §5 formula's own 30-minute floor is unreachable here in practice — every
    job this returns is effectively pinned to the QOS ceiling instead, same
    as the hand-written `wm_job.sh` already hardcodes. A resumable job just
    ends up chaining through more (shorter) resubmits than the formula
    alone would have asked for; a non-resumable one (e.g. matrix-profile)
    has no such fallback, so a workload whose real cost exceeds the ceiling
    will still be submittable but will not finish in one job.
    """
    if est_seconds is None:
        minutes = 0
    else:
        minutes = (est_seconds / 60.0) * _TIME_SAFETY_FACTOR
    rounded = math.ceil(minutes / _TIME_ROUND_MINUTES) * _TIME_ROUND_MINUTES
    minutes = max(_MIN_TIME_MINUTES, rounded)
    minutes = min(minutes, HPC_MAX_WALLTIME_MINUTES)
    h, m = divmod(int(minutes), 60)
    return f"{h:02d}:{m:02d}:00"


class _Span:
    """Lightweight stand-in for a signal array so an adapter's `estimate`
    can be evaluated for a span without materialising the array. Only `len`
    (and `shape`/`size`) are guaranteed -- the two estimators this module
    knows about need no more than the span length and `fs`."""

    def __init__(self, n):
        self._n = int(n)
        self.shape = (self._n,)
        self.size = self._n

    def __len__(self):
        return self._n


def estimate_recipe_seconds(recipe, n_samples, fs):
    """Sum of per-step runtime estimates for a recipe over a span of
    `n_samples` at `fs`, multiplied by fan-out width (PRD "Cluster routing").

    A step whose adapter declares no `estimate` contributes zero -- "Blocks
    without an estimator count as free". An estimator that returns `None`
    (uncalibrated on this machine) also contributes zero, matching the cost
    modules' never-guess contract; callers that need to distinguish "unknown"
    from "cheap" should use `route_recipe`, which reports the former.
    """
    from Adapters.registry import get_adapter

    total = 0.0
    for step in recipe["steps"]:
        spec = get_adapter(f"{step['stage']}.{step['algorithm']}")
        est = spec.estimate
        if est is None:
            continue
        value = est(_Span(n_samples), None, fs, **step["params"])
        if value is not None:
            total += float(value)
    fan = recipe.get("fan_out")
    if fan:
        total *= len(fan["targets"])
    return total


def route_recipe(recipe, n_samples, fs, ceiling_s=CLUSTER_ROUTING_CEILING_S):
    """Where a recipe should run: `'cluster'` | `'local'` | `'unknown'`.

    `'cluster'` when the summed per-step estimate (times fan-out width)
    exceeds `ceiling_s`. `'unknown'` when any step's estimator is present but
    uncalibrated (returns `None`) -- the sum is then a lower bound, and
    routing on it could send a long job to the local path. Otherwise
    `'local'`.

    The value is a headless string a run surface reads to promote "export
    cluster job" to the primary action (PRD "Cluster routing") -- not a UI
    behaviour buried in a widget callback.
    """
    from Adapters.registry import get_adapter

    total = 0.0
    any_unknown = False
    for step in recipe["steps"]:
        spec = get_adapter(f"{step['stage']}.{step['algorithm']}")
        est = spec.estimate
        if est is None:
            continue
        value = est(_Span(n_samples), None, fs, **step["params"])
        if value is None:
            any_unknown = True
        else:
            total += float(value)
    fan = recipe.get("fan_out")
    if fan:
        total *= len(fan["targets"])
    if any_unknown:
        # Even the known part exceeding the ceiling is enough to be certain.
        return "cluster" if total > ceiling_s else "unknown"
    return "cluster" if total > ceiling_s else "local"



# ── what a job needs on the cluster (the researcher, 2026-10-07) ─────────────
# Every generated script lists, in its own comments, the code modules the job
# imports, the input files and the output it writes — so the WinSCP transfer
# can be read off the script instead of guessed.

#: The repo's own packages: an import of anything else is the conda env's.
REPO_PACKAGES = ("Working", "Adapters", "Pipelines")


def _module_file(name):
    """`Working.discovery.seed_job` → `Working/discovery/seed_job.py` (or the
    package's `__init__.py`), repo-relative; None when it is not a repo file."""
    parts = name.split(".")
    if parts[0] not in REPO_PACKAGES:
        return None
    base = os.path.join(REPO_ROOT, *parts)
    # exact case: on Windows `isfile("Encoding.py")` is true of `encoding.py`, and a
    # class imported from a package would be listed as a file the cluster lacks
    siblings = set(os.listdir(os.path.dirname(base))) if os.path.isdir(os.path.dirname(base)) else set()
    if parts[-1] + ".py" in siblings and os.path.isfile(base + ".py"):
        return "/".join(parts) + ".py"
    if parts[-1] in siblings and os.path.isfile(os.path.join(base, "__init__.py")):
        return "/".join(parts) + "/__init__.py"
    return None


def _imports_of(path):
    """Every module name a file imports, at any depth (a lazy import inside a
    function is still needed on the cluster)."""
    import ast

    with open(os.path.join(REPO_ROOT, path), encoding="utf-8") as f:
        try:
            tree = ast.parse(f.read())
        except SyntaxError:
            return []
    names = []
    pkg = path.rsplit("/", 1)[0].replace("/", ".") if "/" in path else ""
    if path.endswith("__init__.py"):
        pkg = path[:-len("/__init__.py")].replace("/", ".")
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.extend(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base = ".".join(pkg.split(".")[: len(pkg.split(".")) - node.level + 1]) if pkg else ""
                mod = f"{base}.{node.module}" if node.module and base else (node.module or base)
            else:
                mod = node.module or ""
            if mod:
                names.append(mod)
                # `from X import y` where y is a submodule
                names.extend(f"{mod}.{a.name}" for a in node.names)
    return names


def repo_module_closure(*entries):
    """The repo files a job needs: the entry modules and everything they import
    through `REPO_PACKAGES`, transitively — a sorted list of repo-relative paths
    with forward slashes. The adapter registry imports every `Adapters/*.py`
    at discovery, so a closure that reaches it carries them all; a package's
    `__init__.py` rides with its modules."""
    seen, todo = set(), []
    for e in entries:
        f = _module_file(e)
        if f:
            todo.append(f)
    while todo:
        path = todo.pop()
        if path in seen:
            continue
        seen.add(path)
        # the package __init__ files on the way down
        parts = path.split("/")[:-1]
        for i in range(1, len(parts) + 1):
            init = "/".join(parts[:i]) + "/__init__.py"
            if init not in seen and os.path.isfile(os.path.join(REPO_ROOT, init)):
                todo.append(init)
        if path == "Adapters/registry.py":
            for name in sorted(os.listdir(os.path.join(REPO_ROOT, "Adapters"))):
                if name.endswith(".py") and f"Adapters/{name}" not in seen:
                    todo.append(f"Adapters/{name}")
        for name in _imports_of(path):
            f = _module_file(name)
            if f and f not in seen:
                todo.append(f)
    return sorted(seen)


def dependency_block(*, code, inputs, outputs, env):
    """The comment block under the `#SBATCH` lines: code, inputs, outputs."""
    lines = ["# ---- what this job needs on the cluster (paths relative to --chdir; transfer with WinSCP) ----",
             f"# environment : conda env `{env}` (numpy, scipy, stumpy, aeon as the repo's requirements say)",
             "# code        : the repo's own modules this job imports (git sync, or copy these files):"]
    lines += [f"#     {c}" for c in code]
    lines.append("# inputs      : files the job reads:")
    lines += [f"#     {i}" for i in inputs]
    lines.append("# outputs     : files the job writes (bring back):")
    lines += [f"#     {o}" for o in outputs]
    lines.append("# ---------------------------------------------------------------------------------------------")
    return "\n".join(lines) + "\n"


def _adapter_modules(recipe):
    return [f"Adapters.{st['stage']}_{st['algorithm']}" for st in recipe.get("steps") or []]


def recipe_dependencies(recipe, recipe_repo_path, data_files=None, outputs=None):
    """What a `run_recipe.py` job needs: the runner, the adapters the steps name
    (and what they import), the recipe file, and the data files the caller
    knows (the database, the recordings' `.npy`)."""
    code = repo_module_closure("Pipelines.run_recipe.run_recipe", "Working.execution", *_adapter_modules(recipe))
    inputs = [recipe_repo_path] + [repo_relative(d) for d in (data_files or [])]
    return {"code": code, "inputs": inputs, "outputs": [repo_relative(o) for o in (outputs or [])]}


_SCRIPT_TEMPLATE = """#!/bin/bash
#SBATCH --job-name={job_name}
#SBATCH --chdir={remote_root}
#SBATCH --output={remote_root}/logs/{base_name}_%j.out
#SBATCH --error={remote_root}/logs/{base_name}_%j.err
#SBATCH --time={slurm_time}
{gpu_line}
#SBATCH --cpus-per-task={cpus}
{array_line}
{deps_block}

echo "========================================"
echo "Job ID       : $SLURM_JOB_ID"
echo "Job name     : $SLURM_JOB_NAME"
echo "Node         : $SLURMD_NODENAME"
echo "Started      : $(date)"
echo "Working dir  : $(pwd)"
echo "========================================"

mkdir -p logs

{module_line}source ~/miniconda3/etc/profile.d/conda.sh
conda activate {conda_env}

{run_command}

echo "========================================"
echo "Finished : $(date)"
echo "========================================"
"""


def _materialize_snippet(recipe_repo_path, per_target_repo_path):
    """Bash snippet that materialises this array task's per-target recipe
    from the fan-out list baked into the recipe JSON, then runs it.

    The per-target recipe is written by `Working.run_groups.materialize_target`
    (the same function `fan_out_recipe` uses locally), so the cluster path and
    the local path cannot drift on what a task index means.
    """
    return (
        "# Materialise this array task's per-target recipe from the fan-out\n"
        "# list baked into the recipe JSON.\n"
        f"python - {recipe_repo_path} \"$SLURM_ARRAY_TASK_ID\" {per_target_repo_path} <<'PY'\n"
        "import json, sys\n"
        "from Working.run_groups import materialize_target\n"
        "recipe_path, task_id, out_path = sys.argv[1], int(sys.argv[2]), sys.argv[3]\n"
        "with open(recipe_path) as f:\n"
        "    recipe = json.load(f)\n"
        "with open(out_path, \"w\") as f:\n"
        "    json.dump(materialize_target(recipe, task_id), f)\n"
        "PY\n"
    )


def export_job(recipe, *, out_dir, base_name, job_name, est_seconds=None,
               slurm_time=None, resumable=False, max_chain=12, uses_gpu=None,
               artifact_repo_path=None, timeout_s=None, data_files=None):
    """Write a recipe JSON + `sbatch` script for an arbitrary recipe.

    This is the single generic exporter both `export_mp_job` and
    `export_wm_job` now wrap. If `recipe` carries a `fan_out` scope, it
    exports a SINGLE SLURM array job whose task index selects its target from
    the recipe's baked-in list (via `Working.run_groups.materialize_target`).

    `resumable=True` uses the window-matrix chain template (resubmits on an
    incomplete build) and requires `artifact_repo_path`; `uses_gpu` toggles
    the GPU directive/module for that template.

    `data_files` are the data the caller knows the job reads (the database,
    the recordings' `.npy`); they are named in the script's dependency block.

    Returns `{"script_path", "recipe_path", "artifact_path", "sbatch_command",
    "job_name", "slurm_time", "timeout_s", "dependencies"}`.
    """
    if slurm_time is None:
        slurm_time = _slurm_time_from_estimate(est_seconds)
    if uses_gpu is None:
        # fixup-ab: the generic template asked every recipe for an A100, a CPU
        # clustering included; a recipe without a CNN step is a CPU job
        uses_gpu = recipe_uses_gpu(recipe)
    os.makedirs(out_dir, exist_ok=True)
    recipe_path = os.path.join(out_dir, f"{base_name}.json")
    with open(recipe_path, "w") as f:
        json.dump(recipe, f, indent=2)

    # The paths baked into the script are REPO-RELATIVE (forward slashes,
    # regardless of the OS this was generated on) -- the job's own `--chdir`
    # puts it at HPC_REMOTE_REPO_ROOT, so a relative path here is what
    # resolves correctly once the generated pair is synced across to the
    # cluster at the same relative location.
    recipe_repo_path = repo_relative(recipe_path)
    script_path = os.path.join(out_dir, f"{base_name}.sh")
    script_repo_path = repo_relative(script_path)

    fan = recipe.get("fan_out")
    n_targets = len(fan["targets"]) if fan else 0
    array_line = f"#SBATCH --array=0-{n_targets - 1}" if fan else ""
    # The per-target recipe each array task writes sits next to the shared
    # fan-out recipe, named by task index so parallel tasks never collide.
    per_target_repo_path = repo_relative(os.path.join(
        out_dir, f"{base_name}_task$SLURM_ARRAY_TASK_ID.json",
    ))
    deps = recipe_dependencies(recipe, recipe_repo_path, data_files=data_files,
                               outputs=([artifact_repo_path] if artifact_repo_path else []))
    deps_block = dependency_block(env=(HPC_CONDA_ENV_GPU if uses_gpu else HPC_CONDA_ENV_CPU), **deps)

    if resumable:
        materialize = _materialize_snippet(recipe_repo_path, per_target_repo_path) if fan else ""
        run_command = (
            materialize
            + f"python Pipelines/run_recipe/run_recipe.py --config "
              f"{per_target_repo_path if fan else recipe_repo_path} --force"
        )
        resubmit_line = (
            f"sbatch --array=$SLURM_ARRAY_TASK_ID {script_repo_path} \"$NEXT\""
            if fan else f"sbatch {script_repo_path} \"$NEXT\""
        )
        manual_resubmit_line = (
            f"sbatch --array=$SLURM_ARRAY_TASK_ID {script_repo_path} 1"
            if fan else f"sbatch {script_repo_path} 1"
        )
        script = _WM_SCRIPT_TEMPLATE.format(
            job_name=job_name, remote_root=HPC_REMOTE_REPO_ROOT, base_name=base_name,
            slurm_time=slurm_time, max_chain=int(max_chain),
            # THIRD iteration, now from `sinfo`/`scontrol show partition`
            # ground truth (2026-08-31), not a guess: `--partition=gpu`
            # (the first two fixes) doesn't exist on this cluster at all
            # ("invalid partition specified: gpu") -- stale from before the
            # reconfiguration the login banner mentions. Real partitions:
            # `HPC_CPU_PARTITION` ("cpu", GRES=(null), no GPU -- correct
            # for a stat-only build, and off the tiny 2-node/2-GPU
            # `a100-test` this account defaults to) for CPU-only, or
            # `HPC_GPU_PARTITION` ("a100", 10 nodes) + `--gres=gpu:a100`
            # when the CNN stage actually needs one. A CPU-only build
            # requests NO `--gres` at all now: `cpu`'s own GRES is `(null)`,
            # so asking it for a GPU device would just be a second wrong
            # constraint on top of a fixed one.
            gpu_line=(f"#SBATCH --gres=gpu:a100\n#SBATCH --partition={HPC_GPU_PARTITION}" if uses_gpu
                      else f"#SBATCH --partition={HPC_CPU_PARTITION}"),
            module_line=("module load cuda/12.2\n" if uses_gpu else ""),
            # `torch_env` (GPU/CNN) does not have `aeon` installed --
            # confirmed 2026-08-31 by a real run failing with "No module
            # named 'aeon'" after every scheduling issue was already fixed.
            # `aeon-env` is this account's separate environment for the
            # catch22/entropy stack a stat-only build actually needs.
            conda_env=(HPC_CONDA_ENV_GPU if uses_gpu else HPC_CONDA_ENV_CPU),
            artifact_repo_path=artifact_repo_path,
            array_line=array_line, deps_block=deps_block,
            run_command=run_command,
            resubmit_line=resubmit_line,
            manual_resubmit_line=manual_resubmit_line,
        )
    else:
        materialize = _materialize_snippet(recipe_repo_path, per_target_repo_path) if fan else ""
        run_command = (
            materialize
            + f"python Pipelines/run_recipe/run_recipe.py --config "
              f"{per_target_repo_path if fan else recipe_repo_path}"
        )
        script = _SCRIPT_TEMPLATE.format(
            job_name=job_name, remote_root=HPC_REMOTE_REPO_ROOT, base_name=base_name,
            slurm_time=slurm_time, array_line=array_line, run_command=run_command, deps_block=deps_block,
            **_profile(uses_gpu),
        )
    # newline="\n": these scripts run on a Linux cluster via `sbatch`, which
    # rejects CRLF outright ("Batch script contains DOS line breaks"). Plain
    # text mode on Windows (this repo's dev environment, per CLAUDE.md)
    # silently translates every `\n` in the template to `\r\n`, so without
    # this the generator produces a script that fails on the one platform
    # it's actually meant to run on.
    with open(script_path, "w", newline="\n") as f:
        f.write(script)

    return {
        "script_path": script_path, "recipe_path": recipe_path,
        "artifact_path": artifact_repo_path,
        "sbatch_command": f"sbatch {script_repo_path}",
        "job_name": job_name, "slurm_time": slurm_time, "timeout_s": timeout_s,
        "uses_gpu": bool(uses_gpu), "warnings": _location_warnings(out_dir), "dependencies": deps,
    }


def _profile(uses_gpu, cpus=4):
    """The scheduling lines of a job: the A100 partition with its GRES, CUDA and
    the torch environment for a CNN; the CPU partition, no GRES, no CUDA and the
    aeon environment otherwise (see the partition notes in `export_job`)."""
    if uses_gpu:
        return {"gpu_line": f"#SBATCH --gres=gpu:a100\n#SBATCH --partition={HPC_GPU_PARTITION}",
                "module_line": "module load cuda/12.2\n\n", "conda_env": HPC_CONDA_ENV_GPU, "cpus": cpus}
    return {"gpu_line": f"#SBATCH --partition={HPC_CPU_PARTITION}", "module_line": "",
            "conda_env": HPC_CONDA_ENV_CPU, "cpus": cpus}


def export_training_job(recipe, *, out_dir, base_name, est_seconds=None, slurm_time=None,
                        db_repo_path="DATA/db/annotations.sqlite", root_repo_path="DATA/derived/training"):
    """A SLURM script for the paired training job (fixup-ab, `Working.training`):
    a CPU job — the forests, the clustering and the null are CPU work — that runs
    `python -m Working.training run` on the recipe written beside it. The window
    set the recipe names must be synced to the cluster with the database; the
    results come back through Jobs › Manifest inbox once that is wired."""
    if slurm_time is None:
        slurm_time = _slurm_time_from_estimate(est_seconds)
    os.makedirs(out_dir, exist_ok=True)
    recipe_path = os.path.join(out_dir, f"{base_name}.json")
    with open(recipe_path, "w") as f:
        json.dump(recipe, f, indent=2)
    script_path = os.path.join(out_dir, f"{base_name}.sh")
    run_command = (f"python -m Working.training run --db {repo_relative(db_repo_path)} "
                   f"--root {repo_relative(root_repo_path)} --recipe {repo_relative(recipe_path)}")
    deps = {"code": repo_module_closure("Working.training"), "inputs": [repo_relative(recipe_path), db_repo_path],
            "outputs": [root_repo_path]}
    script = _SCRIPT_TEMPLATE.format(job_name=base_name, remote_root=HPC_REMOTE_REPO_ROOT, base_name=base_name,
                                     slurm_time=slurm_time, array_line="", run_command=run_command,
                                     deps_block=dependency_block(env=HPC_CONDA_ENV_CPU, **deps),
                                     **_profile(False, cpus=16))
    with open(script_path, "w", newline="\n") as f:
        f.write(script)
    return {"script_path": script_path, "recipe_path": recipe_path, "script": script,
            "sbatch_command": f"sbatch {repo_relative(script_path)}", "job_name": base_name,
            "slurm_time": slurm_time, "profile": "cpu", "warnings": _location_warnings(out_dir)}


def export_mp_job(conn, recording_id, window_min, span=None, *,
                   est_seconds=None, backend="auto", out_dir=DEFAULT_OUT_DIR,
                   fan_out=None):
    """Generate a recipe JSON + `sbatch` script for a
    `detection.matrix_profile` run of `window_min` minutes over
    `recording_id` (`span=None` means the whole channel).

    `fan_out` is an optional `{"kind": "channels"|"bands", "targets": [...]}`
    scope; when present the recipe is exported as a SINGLE SLURM array job
    whose task index selects its target from the baked-in list.

    Named by config hash (`{base_name}.json` / `.sh`), so re-exporting the
    exact same job overwrites its own prior export rather than
    accumulating a new pair every time.

    Returns `{"script_path", "recipe_path", "sbatch_command", "job_name",
    "slurm_time", "timeout_s", "artifact_path"}` (all paths
    local/relative — see module docstring for what still needs to happen
    before `sbatch_command` can actually run anywhere).
    """
    recording = q.get_recording_by_id(conn, recording_id)
    if recording is None:
        raise ValueError(f"No recording with id={recording_id}")

    recipe = make_recipe(recording_id, [
        {"stage": "detection", "algorithm": "matrix_profile",
         "params": {"window_min": float(window_min), "backend": backend}},
    ], span=span, fan_out=fan_out)
    _config_id, hash8 = get_or_create_config(conn, recipe)

    channel = recording["channel"]
    stem = os.path.splitext(recording["source_file"])[0]
    base_name = f"mp_{stem}_CH{channel}_WIN{window_min:g}min_{hash8}"
    job_name = f"mp_CH{channel}_WIN{window_min:g}min"

    return export_job(
        recipe, out_dir=out_dir, base_name=base_name, job_name=job_name,
        est_seconds=est_seconds, resumable=False, uses_gpu=True,
    )


# ===========================================================================
# Window matrix (WINDOW_MATRIX_UI_PROMPT.md §7)
# ===========================================================================
#
# Differs from the matrix-profile template in exactly the ways that follow
# from the window matrix being RESUMABLE and the matrix profile not being:
#
#  - the chain resubmits itself, as `HPC/Preprocessing/wm_job.sh` does;
#  - it resubmits on `wm_status.py`'s EXIT CODE, not by grepping a status
#    string — the grep is what turned one stuck window into an infinite
#    chain (WINDOW_MATRIX_UI_PROMPT.md §0.2);
#  - there is a hard cap on chain length, so even a bug that always reports
#    incomplete terminates;
#  - resuming jobs pass `--force`, because `execute_recipe` short-circuits
#    on a completed run for the same recipe and span and would otherwise
#    "reuse" the partial matrix instead of continuing it;
#  - `--gres=gpu:a100` (and `HPC_GPU_PARTITION`) only when a CNN stage is
#    enabled; a Catch22 + entropy build is CPU-only and requests
#    `HPC_CPU_PARTITION` instead, with no `--gres` at all -- it should not
#    queue for a GPU node, both because it doesn't need one and because
#    the account's GPU partitions are small and department-shared
#    (`a100-test`: 2 nodes, 2 total A100s) next to the CPU partitions
#    (`Working/config.py`, informed by `sinfo`/`scontrol show partition`
#    on the real account, 2026-08-31).
#  - NO `--mem=` line at all. `16G` (a100-test-sized), then `4G` (a
#    measurement-informed reduction) were both rejected outright with
#    "Memory specification can not be satisfied" on `HPC_CPU_PARTITION`
#    (2026-08-31) -- two attempts at picking a number, both wrong. The
#    user's own prior experience with this exact SLURM error, matching the
#    official Rangpur guide's own working example (which never sets `--mem`
#    either), is that omitting `--mem` and letting the scheduler allocate
#    its default is what actually works here.

_WM_SCRIPT_TEMPLATE = """#!/bin/bash
#SBATCH --job-name={job_name}
#SBATCH --chdir={remote_root}
#SBATCH --output={remote_root}/logs/{base_name}_%j.out
#SBATCH --error={remote_root}/logs/{base_name}_%j.err
#SBATCH --time={slurm_time}
#SBATCH --cpus-per-task=4
{gpu_line}
{array_line}
{deps_block}
# Chain position, incremented on each resubmit. Capped at {max_chain} so a
# bug that always reports "incomplete" terminates instead of burning the
# allocation -- the failure mode the hand-written wm_job.sh has today.
CHAIN_INDEX="${{1:-1}}"
MAX_CHAIN={max_chain}

echo "========================================"
echo "Job ID       : $SLURM_JOB_ID"
echo "Job name     : $SLURM_JOB_NAME"
echo "Node         : $SLURMD_NODENAME"
echo "Chain        : $CHAIN_INDEX / $MAX_CHAIN"
echo "Started      : $(date)"
echo "Working dir  : $(pwd)"
echo "========================================"

mkdir -p logs

{module_line}
source ~/miniconda3/etc/profile.d/conda.sh
conda activate {conda_env}

# --force on every job in the chain: the recipe and span are identical each
# time (the resume path is baked in from the first export, deliberately, so
# the config hash never changes), so without it execute_recipe would reuse
# the previous job's partial run instead of continuing it.
{run_command}

echo "========================================"
echo "Run finished : $(date)"

python Pipelines/window_matrix_build/wm_status.py --artifact {artifact_repo_path}
STATUS=$?

if [ "$STATUS" -eq 0 ]; then
    echo ">>> Matrix complete -- chain finished."
elif [ "$STATUS" -ge 3 ]; then
    echo ">>> Could not read the artifact (exit $STATUS) -- stopping the chain."
    exit "$STATUS"
elif [ "$CHAIN_INDEX" -ge "$MAX_CHAIN" ]; then
    echo ">>> Work remains but the chain cap ($MAX_CHAIN) is reached -- stopping."
    echo ">>> Resubmit manually if this is expected: {manual_resubmit_line}"
else
    NEXT=$((CHAIN_INDEX + 1))
    echo ">>> Work remains -- submitting job $NEXT of $MAX_CHAIN ..."
    {resubmit_line}
    echo ">>> Submitted. Monitor with: squeue -u $USER"
fi

echo "Finished     : $(date)"
echo "========================================"
"""


def export_wm_job(conn, recording_id, window_min, span=None, *, step_frac=1.0,
                  stages=("catch22", "fast_entropy", "slow_entropy"),
                  est_seconds=None, timeout_s=None, max_chain=12,
                  cnn_model_dir="models", rf_model_path="",
                  out_dir=DEFAULT_WM_OUT_DIR, results_dir=None, fan_out=None):
    """Generate a recipe JSON + resubmitting `sbatch` script for a
    `preprocessing.window_matrix` run of `window_min` minutes over
    `recording_id` (`span=None` means the whole channel).

    `fan_out` is an optional `{"kind": "channels"|"bands", "targets": [...]}`
    scope; when present the recipe is exported as a SINGLE SLURM array job
    whose task index selects its target from the baked-in list. NOTE: the
    chain script's `wm_status --artifact` path is derived from the BASE
    recording, so a multi-target fan-out should be verified against each
    target's actual artifact path before submission.

    Named by config hash, so re-exporting the exact same job overwrites its
    own prior export rather than accumulating a new pair every time.

    `timeout_s` defaults to the SLURM wall clock minus a cleanup margin, so
    the builder saves a resumable partial artifact BEFORE SLURM kills the
    job. `wm_job.sh` gets this relationship right by hand today
    (`--time=00:20:00` against `--timeout 19`); deriving it here means it
    cannot drift.

    Returns `{"script_path", "recipe_path", "artifact_path", "sbatch_command",
    "job_name", "slurm_time", "timeout_s"}`. All paths are local/relative —
    see the module docstring for what still has to happen before
    `sbatch_command` can run anywhere.
    """
    # Imported here, not at module scope: `Working/` should not depend on
    # `Adapters/` at import time, and the artifact path is a property of the
    # STORAGE layer anyway — the adapter's `default_artifact_path` is a thin
    # wrapper over this same call.
    from Working.database import window_matrix_store as wm_store

    recording = q.get_recording_by_id(conn, recording_id)
    if recording is None:
        raise ValueError(f"No recording with id={recording_id}")

    slurm_time = _slurm_time_from_estimate(est_seconds)
    if timeout_s is None:
        hours, minutes, _sec = (int(p) for p in slurm_time.split(":"))
        # 5 minutes of cleanup margin: enough for the final npz write plus
        # the status check, and small relative to the 30-minute floor.
        timeout_s = max(60.0, (hours * 3600 + minutes * 60) - 300)

    params = {
        "window_min": float(window_min),
        "step_frac": float(step_frac),
        "catch22": "catch22" in stages,
        "fast_entropy": "fast_entropy" in stages,
        "slow_entropy": "slow_entropy" in stages,
        "cnn": "cnn" in stages,
        "rf": "rf" in stages,
        "timeout_s": float(timeout_s),
        # Baked in from the FIRST export so every job in the chain hashes to
        # the same recipe -- see the adapter's module docstring. Filled below,
        # once the recipe exists to key the name on.
        "resume_path": "",
        "cnn_model_dir": cnn_model_dir,
        "rf_model_path": rf_model_path,
    }
    recipe = make_recipe(recording_id, [
        {"stage": "preprocessing", "algorithm": "window_matrix", "params": params},
    ], span=span, fan_out=fan_out)
    # fixup-aa: the name carries the span and the recipe-prefix key, and the key
    # ignores `resume_path` -- so the path is computed from the recipe and then
    # baked into it without changing the key it was computed from.
    name_span = tuple(span) if span is not None else (0, int(recording["n_samples"]))
    artifact_path = os.path.join(
        results_dir or wm_store.DEFAULT_RESULTS_DIR,
        wm_store.artifact_name(os.path.splitext(recording["source_file"])[0],
                               recording["channel"], window_min, step_frac,
                               span=name_span, key=wm_store.matrix_key(recipe)) + ".npz",
    )
    recipe["steps"][0]["params"]["resume_path"] = artifact_path.replace(os.sep, "/")
    _config_id, hash8 = get_or_create_config(conn, recipe)

    channel = recording["channel"]
    stem = os.path.splitext(recording["source_file"])[0]
    step_pct = int(round(step_frac * 100))
    base_name = f"wm_{stem}_CH{channel}_WIN{window_min:g}min_STEP{step_pct}pct_{hash8}"
    job_name = f"wm_CH{channel}_WIN{window_min:g}min"

    return export_job(
        recipe, out_dir=out_dir, base_name=base_name, job_name=job_name,
        est_seconds=est_seconds, slurm_time=slurm_time, resumable=True,
        max_chain=max_chain, uses_gpu="cnn" in stages,
        artifact_repo_path=artifact_path.replace(os.sep, "/"),
        timeout_s=timeout_s,
    )



# ===========================================================================
# fixup-ai: RQ1 version 2 (B.2) -- the CNN arm and Ward over every window
# ===========================================================================
#
# Both read a JOB DIRECTORY the core wrote (`Working.training.shape_cnn.export_job`,
# `Working.training.full_ward.export_job`): everything the cluster needs except
# the code (the repository, synced as usual) and the channel arrays (listed, with
# their sizes, by the export). No database on the cluster. The results come back
# by copying `<job>/out/` into the same job directory here and running
# `python -m Working.training import-results <job>` (one function,
# `Working.training.hpc_import.import_results`, which Jobs > Manifest inbox calls).
#
# The CNN job is RESUMABLE and chains itself as the window-matrix job does: this
# account's QOS ends a job at `HPC_MAX_WALLTIME_MINUTES`; the run stops a few
# minutes before that between chunks / epochs (`--deadline-min`), checkpointed,
# and `cnn-status`'s EXIT CODE (0 complete, 1 work remains, >= 3 unreadable)
# decides the resubmit -- never a text match -- with a cap on the chain.

#: the margin between `--deadline-min` and the wall clock: the last epoch's checkpoint and the status check
CNN_DEADLINE_MARGIN_MIN = 3
#: CPUs for the encode workers (the images are made on the GPU node's CPUs, then cached)
CNN_CPUS = 8
#: a CPU tier with more memory than `cpu` (`HPC/README.md`'s `sinfo` table: `largecpu`, 4-5 nodes, no GRES).
#: UNVERIFIED for this account: `--mem` was refused on `cpu` twice (2026-08-31); the script says what to do if
#: `sbatch` answers "Memory specification can not be satisfied".
WARD_PARTITION = "largecpu"

_ENV_CHECK = (
    "# the environment, checked before an hour is spent: a missing package is named here\n"
    "python -c \"import {mods}; print('environment ok')\" || {{ echo \">>> conda env {env} lacks a package (above): "
    "conda install -n {env} <package>\"; exit 4; }}\n"
)

_CNN_TEMPLATE = """#!/bin/bash
#SBATCH --job-name={job_name}
#SBATCH --chdir={remote_root}
#SBATCH --output={remote_root}/logs/{base_name}_%j.out
#SBATCH --error={remote_root}/logs/{base_name}_%j.err
#SBATCH --time={slurm_time}
#SBATCH --cpus-per-task={cpus}
#SBATCH --gres=gpu:a100
#SBATCH --partition={partition}
{array_line}
# fixup-ai: arm B.2 (cluster labels, trace shape) with a CNN -- {model}
# job directory: {job_repo}  (recipe {recipe_hash})
# {estimate_line}
# Resumable: the run stops {margin} min before the wall clock, checkpointed; the status
# check's exit code resubmits this script until the job is complete (at most {max_chain} jobs).
CHAIN_INDEX="${{1:-1}}"
MAX_CHAIN={max_chain}

echo "========================================"
echo "Job ID       : $SLURM_JOB_ID{array_echo}"
echo "Node         : $SLURMD_NODENAME"
echo "Chain        : $CHAIN_INDEX / $MAX_CHAIN"
echo "Started      : $(date)"
echo "Working dir  : $(pwd)"
echo "========================================"

mkdir -p logs
module load cuda/12.2
source ~/miniconda3/etc/profile.d/conda.sh
conda activate {conda_env}

{env_check}
{run_command}
RUN=$?
if [ "$RUN" -ne 0 ]; then
    # a crash is not "work remains": resubmitting would crash again -- stop and read the .err log
    echo ">>> The run failed (exit $RUN) -- stopping the chain; see logs/{base_name}_$SLURM_JOB_ID.err"
    exit "$RUN"
fi

{status_command}
STATUS=$?

if [ "$STATUS" -eq 0 ]; then
    echo ">>> Complete. Copy {job_repo}/out/ back into the same place on your machine, then run:"
    echo ">>>     python -m Working.training import-results {job_repo}"
elif [ "$STATUS" -ge 3 ]; then
    echo ">>> The job could not be read (exit $STATUS) -- stopping the chain."
    exit "$STATUS"
elif [ "$CHAIN_INDEX" -ge "$MAX_CHAIN" ]; then
    echo ">>> Work remains but the chain cap ($MAX_CHAIN) is reached -- stopping."
    echo ">>> Resubmit by hand to continue from the last checkpoint: {manual_resubmit}"
else
    NEXT=$((CHAIN_INDEX + 1))
    echo ">>> Work remains -- submitting job $NEXT of $MAX_CHAIN ..."
    {resubmit}
fi
echo "Finished     : $(date)"
"""

_WARD_TEMPLATE = """#!/bin/bash
#SBATCH --job-name={job_name}
#SBATCH --chdir={remote_root}
#SBATCH --output={remote_root}/logs/{base_name}_%j.out
#SBATCH --error={remote_root}/logs/{base_name}_%j.err
#SBATCH --time={slurm_time}
#SBATCH --cpus-per-task=4
#SBATCH --partition={partition}
#SBATCH --mem={mem_gb}G

# fixup-ai: Ward over EVERY training window of the pool ({n:,} windows) -- the same Ward as the
# Shape clustering block (the Library's method), the same tree artifact.
# job directory: {job_repo}  (recipe {recipe_hash})
# memory: {mem_rule}
# time: {time_rule}
# If sbatch answers "Memory specification can not be satisfied": run  sinfo -o "%P %m %c"  and
# pick a partition whose memory per node (MB) exceeds {mem_gb} GB; this account refused --mem on
# `cpu` before (HPC/README.md).

echo "Job ID : $SLURM_JOB_ID   Node : $SLURMD_NODENAME   Started : $(date)"
mkdir -p logs
source ~/miniconda3/etc/profile.d/conda.sh
conda activate {conda_env}

{env_check}
python -m Working.training ward-run --job {job_repo}
python -m Working.training ward-status --job {job_repo}
STATUS=$?
if [ "$STATUS" -eq 0 ]; then
    echo ">>> Complete. Copy {job_repo}/out/ back into the same place on your machine, then run:"
    echo ">>>     python -m Working.training import-results {job_repo}"
fi
echo "Finished : $(date)"
exit "$STATUS"
"""


def _minutes(slurm_time):
    h, m, _s = (int(p) for p in slurm_time.split(":"))
    return h * 60 + m


def export_cnn_job(job_dir, *, base_name, est_seconds=None, null_shuffles=0, train_seconds=None, cpus=CNN_CPUS,
                   max_chain=None, model="CNN"):
    """The B.2 CNN's `sbatch` script, written into its job directory (and, when `null_shuffles` > 0, the
    label-shuffle null's array script beside it). Returns the scripts, the paths, the chain length and notes."""
    os.makedirs(job_dir, exist_ok=True)
    meta_path = os.path.join(job_dir, "job.json")
    meta = {}
    if os.path.isfile(meta_path):
        with open(meta_path, encoding="utf-8") as f:
            meta = json.load(f)
    slurm_time = _slurm_time_from_estimate(est_seconds)
    wall = _minutes(slurm_time)
    deadline = max(1, wall - CNN_DEADLINE_MARGIN_MIN)
    need = None if est_seconds is None else int(math.ceil(float(est_seconds) / 60.0 / deadline))
    if max_chain is None:
        max_chain = max(6, 2 * (need or 1) + 2)     # twice the estimate's job count: the estimate is an estimate
    job_repo = repo_relative(os.path.abspath(job_dir))
    script_path = os.path.join(job_dir, f"{base_name}.sh")
    script_repo = repo_relative(script_path)
    env_check = _ENV_CHECK.format(mods="torch, torchvision, numpy, scipy, skimage, PIL, matplotlib",
                                  env=HPC_CONDA_ENV_GPU)
    est_line = ("estimate: not measured yet (run the local smoke first); --time is the account's ceiling"
                if est_seconds is None else
                f"estimate: about {float(est_seconds) / 3600:.1f} h of work in all, so about {need} chained "
                f"job(s) of {wall} min -- an estimate, not a measurement")
    script = _CNN_TEMPLATE.format(
        job_name=f"b2cnn_{meta.get('encoding', 'cnn')}"[:40], remote_root=HPC_REMOTE_REPO_ROOT, base_name=base_name,
        slurm_time=slurm_time, cpus=int(cpus), partition=HPC_GPU_PARTITION, array_line="", array_echo="",
        model=meta.get("model", model), job_repo=job_repo, recipe_hash=meta.get("recipe_hash", "?"),
        estimate_line=est_line, margin=CNN_DEADLINE_MARGIN_MIN, max_chain=int(max_chain), conda_env=HPC_CONDA_ENV_GPU,
        env_check=env_check,
        run_command=(f"python -m Working.training cnn-run --job {job_repo} --workers \"$SLURM_CPUS_PER_TASK\" "
                     f"--deadline-min {deadline}"),
        status_command=f"python -m Working.training cnn-status --job {job_repo}",
        manual_resubmit=f"sbatch {script_repo} 1", resubmit=f"sbatch {script_repo} \"$NEXT\"")
    with open(script_path, "w", newline="\n", encoding="utf-8") as f:
        f.write(script)
    null_path, null_script = None, None
    null = {"n": 0, "on": False, "note": "off: the label-shuffle null is 5 full trainings (an array job)"}
    if int(null_shuffles) > 0:
        n = int(null_shuffles)
        null_path = os.path.join(job_dir, f"{base_name}_null.sh")
        null_repo = repo_relative(null_path)
        null_script = _CNN_TEMPLATE.format(
            job_name="b2cnn_null", remote_root=HPC_REMOTE_REPO_ROOT, base_name=f"{base_name}_null_%a",
            slurm_time=slurm_time, cpus=int(cpus), partition=HPC_GPU_PARTITION,
            array_line=f"#SBATCH --array=0-{n - 1}", array_echo="  task $SLURM_ARRAY_TASK_ID",
            model=f"label-shuffle null: {n} full trainings on permuted cluster labels, one per array task",
            job_repo=job_repo, recipe_hash=meta.get("recipe_hash", "?"),
            estimate_line=("each task: one full training"
                           + ("" if train_seconds is None else f", about {float(train_seconds) / 3600:.2f} GPU-h")),
            margin=CNN_DEADLINE_MARGIN_MIN, max_chain=int(max_chain), conda_env=HPC_CONDA_ENV_GPU,
            env_check=env_check,
            run_command=(f"python -m Working.training cnn-null --job {job_repo} --shuffle $SLURM_ARRAY_TASK_ID "
                         f"--workers \"$SLURM_CPUS_PER_TASK\" --deadline-min {deadline}"),
            status_command=(f"python -m Working.training cnn-null-status --job {job_repo} "
                            "--shuffle $SLURM_ARRAY_TASK_ID"),
            manual_resubmit=f"sbatch --array=$SLURM_ARRAY_TASK_ID {null_repo} 1",
            resubmit=f"sbatch --array=$SLURM_ARRAY_TASK_ID {null_repo} \"$NEXT\"")
        with open(null_path, "w", newline="\n", encoding="utf-8") as f:
            f.write(null_script)
        null = {"n": n, "on": True, "gpu_hours": (None if train_seconds is None else n * float(train_seconds) / 3600),
                "sbatch_command": f"sbatch --dependency=afterok:<the main job's id> {null_repo}",
                "note": (f"{n} full trainings on permuted cluster labels (one full training each), an array job of {n} "
                         "tasks; submit it AFTER the main job has encoded (it re-uses the image cache)")}
    return {"script_path": script_path, "script": script, "sbatch_command": f"sbatch {script_repo}",
            "null_script_path": null_path, "null_script": null_script, "null": null,
            "slurm_time": slurm_time, "deadline_min": deadline, "chain_jobs": int(max_chain), "jobs_needed": need,
            "estimate_note": est_line, "profile": "gpu", "warnings": _location_warnings(job_dir)}


def export_ward_job(job_dir, *, base_name, n, est_seconds=None, memory=None):
    """The full-pool Ward's `sbatch` script: a CPU job on a high-memory partition, `--mem` sized from n."""
    from Working.training.full_ward import memory_estimate
    mem = memory or memory_estimate(n)
    slurm_time = _slurm_time_from_estimate(est_seconds)
    job_repo = repo_relative(os.path.abspath(job_dir))
    script_path = os.path.join(job_dir, f"{base_name}.sh")
    time_rule = ("not estimated" if est_seconds is None else
                 f"about {float(est_seconds) / 60:.1f} min (AG's 57 s at 20,000 scaled by n squared -- an estimate), "
                 f"x 3 for another machine, clamped to the account's {HPC_MAX_WALLTIME_MINUTES} min")
    script = _WARD_TEMPLATE.format(
        job_name="ward_full_pool", remote_root=HPC_REMOTE_REPO_ROOT, base_name=base_name, slurm_time=slurm_time,
        partition=WARD_PARTITION, mem_gb=int(mem["request_gb"]), n=int(n), job_repo=job_repo,
        recipe_hash=_job_hash(job_dir), mem_rule=mem["rule"], time_rule=time_rule, conda_env=HPC_CONDA_ENV_CPU,
        env_check=_ENV_CHECK.format(mods="numpy, scipy, pandas", env=HPC_CONDA_ENV_CPU))
    os.makedirs(job_dir, exist_ok=True)
    with open(script_path, "w", newline="\n", encoding="utf-8") as f:
        f.write(script)
    return {"script_path": script_path, "script": script, "sbatch_command": f"sbatch {repo_relative(script_path)}",
            "slurm_time": slurm_time, "memory": mem, "partition": WARD_PARTITION, "profile": "cpu-highmem",
            "warnings": _location_warnings(job_dir)}


def _job_hash(job_dir):
    p = os.path.join(job_dir, "job.json")
    if not os.path.isfile(p):
        return "?"
    with open(p, encoding="utf-8") as f:
        return json.load(f).get("recipe_hash", "?")


# ── fixup-aj: the job directories the site wrote, as Jobs lists them ────────
#: the recipe kinds a written job directory holds (fixup-AI's two RQ1 jobs), and how Jobs names them
EXPORTED_KINDS = {"shape_cluster_cnn": "B.2 CNN · trained on the cluster categories",
                  "shape_tree_full": "Ward over every training window"}
#: never copied to the cluster: the image cache is built there, out/ is what comes back
_NOT_COPIED = ("cache", "out")


def _tree_bytes(d, skip=()):
    total = 0
    for name in os.listdir(d):
        p = os.path.join(d, name)
        if os.path.isdir(p):
            if name not in skip:
                total += _tree_bytes(p)
        elif os.path.isfile(p):
            total += os.path.getsize(p)
    return total


def _read_json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _imported_run(conn, recipe_hash):
    """The completed run a recipe hash was imported as -- the identity `hpc_import.import_results` uses."""
    if conn is None or not recipe_hash:
        return None
    row = conn.execute("SELECT r.id, r.name FROM runs r JOIN configs c ON c.id = r.config_id WHERE c.config_hash = ? "
                       "AND r.status = 'completed' ORDER BY r.id LIMIT 1", (str(recipe_hash),)).fetchone()
    return None if row is None else {"run_id": int(row[0]), "name": row[1]}


def describe_job_dir(job_dir, conn=None):
    """One written job directory as Jobs lists it. Its `job.json` is the record the site keeps of what it wrote:
    the recipe hash, when, the channel arrays (CNN). Never raises: an unreadable job is a row with `error`."""
    from Working.recipes import short_hash
    job_dir = os.path.abspath(str(job_dir))
    name = os.path.basename(job_dir.rstrip("/\\"))
    row = {"name": name, "job_dir": job_dir, "job_repo": repo_relative(job_dir), "kind": None, "kind_label": None,
           "recipe_hash": None, "recipe_ok": None, "written_at": None, "smoke": False, "model": None, "pool_key": None,
           "scripts": [], "sbatch_command": None, "copy": [], "total_bytes": 0, "returned": None, "imported": None,
           "error": None}
    try:
        meta = _read_json(os.path.join(job_dir, "job.json"))
        recipe = _read_json(os.path.join(job_dir, "recipe.json"))
    except Exception as e:                                    # loud: the row says what is wrong with it
        row["error"] = f"{type(e).__name__}: {e}"
        return row
    kind = meta.get("kind") or recipe.get("kind")
    h = meta.get("recipe_hash")
    row.update({"kind": kind, "kind_label": EXPORTED_KINDS.get(kind, kind), "recipe_hash": h,
                "recipe_ok": short_hash(recipe) == h, "written_at": meta.get("created_at"),
                "smoke": bool(meta.get("smoke") or recipe.get("smoke")), "model": meta.get("model"),
                "pool_key": (recipe.get("pool") or {}).get("key") or recipe.get("pool_key") or meta.get("pool_key"),
                "n": meta.get("n") or meta.get("n_windows")})
    scripts = sorted(f for f in os.listdir(job_dir) if f.endswith(".sh"))
    row["scripts"] = [{"name": f, "path": os.path.join(job_dir, f), "repo": repo_relative(os.path.join(job_dir, f))}
                      for f in scripts]
    main = [s for s in row["scripts"] if not s["name"].endswith("_null.sh")]
    row["sbatch_command"] = f"sbatch {main[0]['repo']}" if main else None
    copy = [{"what": "job directory", "path": row["job_repo"], "bytes": int(_tree_bytes(job_dir, _NOT_COPIED)),
             "note": "everything in it but cache/ and out/"}]
    copy += [{"what": "channel array", "path": c.get("path"), "bytes": int(c.get("bytes") or 0),
              "note": f"{c.get('source_file')} channel {c.get('channel')}"} for c in meta.get("channels") or []]
    row["copy"] = copy
    row["total_bytes"] = int(sum(c["bytes"] for c in copy))
    done = os.path.join(job_dir, "out", "done.json")
    if os.path.isfile(done):
        try:
            d = _read_json(done)
            row["returned"] = {"status": d.get("status"), "recipe_hash": d.get("recipe_hash"),
                               "finished_at": d.get("finished_at")}
        except Exception as e:
            row["returned"] = {"status": f"unreadable: {e}", "recipe_hash": None, "finished_at": None}
    row["imported"] = _imported_run(conn, h)
    return row


def list_exported_jobs(roots, conn=None):
    """Every job directory under `roots` (each root's immediate sub-folders holding a `job.json`), newest first."""
    rows = []
    for root in roots:
        if not root or not os.path.isdir(root):
            continue
        for name in sorted(os.listdir(root)):
            d = os.path.join(root, name)
            if os.path.isdir(d) and os.path.isfile(os.path.join(d, "job.json")):
                rows.append(describe_job_dir(d, conn))
    rows.sort(key=lambda r: (r["written_at"] or ""), reverse=True)
    return rows
