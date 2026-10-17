"""A Discovery seed job split into one cluster job per channel, and merged back.

The script the Seed page writes (`Working/discovery/seed_job.py`) does one channel per 20-minute submission and then
sbatches the next one. Sixteen channels are sixteen submissions in a row, all on one node: `dip_search_allch` took
about three hours from script to import. The channels are independent, so they can run at the same time.

A one-channel spec computes exactly that channel's row of the full result. `run_spec` gives draw n of every channel
the seed `base + n`, wherever the channel falls in the order, so the parts' nulls are the full run's nulls.

    python scripts/seed_job_parallel.py split HPC/Detection/generated/<name>.spec.json
    python scripts/seed_job_parallel.py merge HPC/Detection/generated/<name>.spec.json

`split` writes `<name>_parts/` beside the spec, holding:
  - per channel, a spec and its script, written by `seed_job.write_job` (so they get the same partition, wall,
    environment, resubmission and failure checks as the chained script);
  - `submit_all.sh`, which submits every part at once.

`pack` is for an account that runs only a few jobs at once (rangpur runs three per user and queues the rest). One
channel's search uses one core: measured 2026-10-17, CPU time was 1.08× wall time, peak about 0.5 GB. So `pack`
writes `--jobs` scripts, each running several parts at the same time, one core per part. Each pack reads and writes
the parts' own spec and result files, so a finished part is skipped and a stopped one continues from its last
checkpoint. You can therefore cancel the one-channel jobs mid-run and submit the packs without losing work.

    python scripts/seed_job_parallel.py pack HPC/Detection/generated/<name>.spec.json --jobs 3

`merge` reads the parts' results from that folder. It refuses the merge unless every channel's result is present
and complete and was computed from this spec's own part (checked by spec hash, which also covers the exemplar). It
then writes `<name>.result.json`, the file the chained job would have written, ready for the Seed page's *Import HPC
result*.

Dev tooling: the app does not import it.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from Working.config import HPC_REMOTE_REPO_ROOT  # noqa: E402
from Working.discovery import seed_job  # noqa: E402
from Working.hpc.job_export import repo_relative  # noqa: E402

SUBMIT_NAME = "submit_all.sh"


def _load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _base(spec_path):
    name = os.path.basename(spec_path)
    if not name.endswith(seed_job.SPEC_SUFFIX):
        raise SystemExit(f"{spec_path} is not a seed job spec (*{seed_job.SPEC_SUFFIX})")
    return name[: -len(seed_job.SPEC_SUFFIX)]


def parts_dir(spec_path):
    return os.path.join(os.path.dirname(os.path.abspath(spec_path)), _base(spec_path) + "_parts")


def part_spec(spec, ch):
    """One channel of `spec`, everything else unchanged: its hash is what a part's result must name."""
    return dict(spec, channels=[ch])


def part_name(spec_path, ch):
    return f"{_base(spec_path)}__{ch['name']}"


def part_result_path(spec_path, ch):
    return os.path.join(parts_dir(spec_path), part_name(spec_path, ch) + seed_job.RESULT_SUFFIX)


def split(spec_path):
    """Write one chained job per channel and `submit_all.sh`. Returns (write_job results, submit script path)."""
    spec = _load(spec_path)
    if int(spec.get("version") or 0) != seed_job.SPEC_VERSION:
        raise SystemExit(f"{spec_path}: spec version {spec.get('version')!r} is not {seed_job.SPEC_VERSION}")
    out_dir = parts_dir(spec_path)
    made = [seed_job.write_job(part_spec(spec, ch), out_dir=out_dir, base_name=part_name(spec_path, ch))
            for ch in spec["channels"]]
    base = _base(spec_path)
    submit = os.path.join(out_dir, SUBMIT_NAME)
    lines = [
        "#!/bin/bash",
        f"# Submits the {len(made)} one-channel parts of {base} at once (scripts/seed_job_parallel.py split).",
        "# The channels are independent: SLURM's own queue decides how many run together. Each part is the",
        "# Seed page's chained seed job for one channel, so it resubmits itself if a channel outlasts the wall.",
        f"# Run from the repo root on the cluster ({HPC_REMOTE_REPO_ROOT}).",
        "#",
        f"# Cancel them all:  squeue -u $USER -h -o \"%i %j\" | awk '$2 ~ /^{base}__/ {{print $1}}' | xargs -r scancel",
        f"# When every part is done, bring back {repo_relative(out_dir)}/*{seed_job.RESULT_SUFFIX} and on the PC run:",
        f"#   python scripts/seed_job_parallel.py merge {repo_relative(spec_path)}",
        "# then import the merged result on the Seed page.",
        "set -euo pipefail",
        "",
    ] + [m["sbatch_command"] for m in made] + [""]
    # LF only: sbatch rejects DOS line breaks (HPC/README.md)
    with open(submit, "w", newline="\n", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return made, submit


def _pack_script(*, name, parts, parts_repo_dir, cpus, slurm_time, deps_block, script_repo_path, per_part_guard):
    from Working.hpc.job_export import _profile
    prof = _profile(False, cpus=cpus)
    budget = int(seed_job._wall_seconds(slurm_time) * 0.85)
    listed = " ".join(parts)
    return f"""#!/bin/bash
#SBATCH --job-name={name}
#SBATCH --chdir={HPC_REMOTE_REPO_ROOT}
#SBATCH --output={HPC_REMOTE_REPO_ROOT}/logs/{name}_%j.out
#SBATCH --error={HPC_REMOTE_REPO_ROOT}/logs/{name}_%j.err
#SBATCH --time={slurm_time}
{prof['gpu_line']}
#SBATCH --cpus-per-task={cpus}
{deps_block}
# {len(parts)} one-channel parts at the same time, one core each (a seed search is single-threaded and takes about
# 0.5 GB per channel). Each part reads and writes its own spec and result in {parts_repo_dir}/,
# so a finished part is skipped and a stopped one continues from its last checkpoint. Each part has a budget of
# {budget} s and exits at its next checkpoint after that. While any part reads incomplete this script resubmits
# itself; it is capped at {seed_job.MAX_CHAIN} submissions. A part that fails stops the chain.
# Do not run this alongside the parts' own one-channel jobs: {per_part_guard}
CHAIN_INDEX="${{1:-1}}"
MAX_CHAIN={seed_job.MAX_CHAIN}
DIR={parts_repo_dir}
PARTS=({listed})

echo "========================================"
echo "Job ID       : $SLURM_JOB_ID"
echo "Job name     : $SLURM_JOB_NAME"
echo "Node         : $SLURMD_NODENAME"
echo "CPUs         : $SLURM_CPUS_PER_TASK for ${{#PARTS[@]}} parts"
echo "Chain        : $CHAIN_INDEX / $MAX_CHAIN"
echo "Started      : $(date)"
echo "Working dir  : $(pwd)"
echo "========================================"

mkdir -p logs

{prof['module_line']}source ~/miniconda3/etc/profile.d/conda.sh
conda activate {prof['conda_env']}

PIDS=()
for P in "${{PARTS[@]}}"; do
    python -m Working.discovery.seed_job --spec "$DIR/$P.spec.json" --out "$DIR/$P{seed_job.RESULT_SUFFIX}" \\
        --max-channels 1 --budget-s {budget} > "logs/${{P}}_${{SLURM_JOB_ID}}.log" 2>&1 &
    PIDS+=($!)
done
FAILED=0
for I in "${{!PIDS[@]}}"; do
    if ! wait "${{PIDS[$I]}}"; then
        echo ">>> ${{PARTS[$I]}} failed -- see logs/${{PARTS[$I]}}_${{SLURM_JOB_ID}}.log"
        FAILED=1
    fi
    tail -n 1 "logs/${{PARTS[$I]}}_${{SLURM_JOB_ID}}.log"
done

echo "========================================"
echo "Run finished : $(date)"

if [ "$FAILED" -ne 0 ]; then
    echo ">>> A part failed -- NOT resubmitting. When fixed, resume with: sbatch {script_repo_path} $CHAIN_INDEX"
    exit 1
fi

LEFT=0
for P in "${{PARTS[@]}}"; do
    python -m Working.discovery.seed_job --status "$DIR/$P{seed_job.RESULT_SUFFIX}"
    S=$?
    if [ "$S" -eq 1 ]; then
        LEFT=$((LEFT + 1))
    elif [ "$S" -ne 0 ]; then
        echo ">>> The status check failed for $P (exit $S) -- NOT resubmitting. Resume with: sbatch {script_repo_path} $CHAIN_INDEX"
        exit $S
    fi
done

if [ "$LEFT" -eq 0 ]; then
    echo ">>> Every part of this pack is complete."
elif [ "$CHAIN_INDEX" -ge "$MAX_CHAIN" ]; then
    echo ">>> $LEFT parts remain but the chain cap ($MAX_CHAIN) is reached -- stopping."
    echo ">>> Resubmit manually if this is expected: sbatch {script_repo_path} 1"
else
    NEXT=$((CHAIN_INDEX + 1))
    echo ">>> $LEFT parts remain -- submitting job $NEXT of $MAX_CHAIN ..."
    sbatch {script_repo_path} "$NEXT"
    echo ">>> Submitted. Monitor with: squeue -u $USER"
fi

echo "Finished     : $(date)"
echo "========================================"
"""


def pack(spec_path, jobs=3):
    """`jobs` scripts that between them run every part, each part on its own core, plus `submit_packs.sh`.
    Needs `split` first: the packs run the parts' own specs. Returns (script paths, submit script path)."""
    from Working.config import HPC_CONDA_ENV_CPU
    from Working.hpc.job_export import _slurm_time_from_estimate, dependency_block, repo_module_closure

    spec = _load(spec_path)
    chans = spec["channels"]
    missing = [ch["name"] for ch in chans
               if not os.path.isfile(os.path.join(parts_dir(spec_path), part_name(spec_path, ch) + seed_job.SPEC_SUFFIX))]
    if missing:
        raise SystemExit(f"no part specs for {missing}: run `split` first")
    jobs = max(1, min(int(jobs), len(chans)))
    # contiguous, as even as the count allows: 16 over 3 is 6, 5, 5
    sizes = [len(chans) // jobs + (1 if i < len(chans) % jobs else 0) for i in range(jobs)]
    base, out_dir = _base(spec_path), parts_dir(spec_path)
    parts_repo_dir = repo_relative(out_dir)
    part_prefix = f"{base}__CH"
    per_part_guard = (f"cancel those first: squeue -u $USER -h -o \"%i %j\" | awk '$2 ~ /^{part_prefix}/ {{print $1}}' "
                      f"| xargs -r scancel")
    slurm_time = _slurm_time_from_estimate(None)
    code = repo_module_closure("Working.discovery.seed_job")
    scripts, at = [], 0
    for i, n in enumerate(sizes, start=1):
        group = chans[at:at + n]
        at += n
        names = [part_name(spec_path, ch) for ch in group]
        name = f"{base}__pack{i}of{jobs}"
        path = os.path.join(out_dir, f"{name}.sh")
        deps = dependency_block(env=HPC_CONDA_ENV_CPU, code=code,
                                inputs=[f"{parts_repo_dir}/{p}{seed_job.SPEC_SUFFIX}" for p in names]
                                + [ch["npy"] for ch in group if ch.get("npy")],
                                outputs=[f"{parts_repo_dir}/{p}{seed_job.RESULT_SUFFIX}" for p in names])
        script = _pack_script(name=name, parts=names, parts_repo_dir=parts_repo_dir, cpus=n, slurm_time=slurm_time,
                              deps_block=deps, script_repo_path=repo_relative(path), per_part_guard=per_part_guard)
        with open(path, "w", newline="\n", encoding="utf-8") as f:
            f.write(script)
        scripts.append(path)
    submit = os.path.join(out_dir, "submit_packs.sh")
    lines = [
        "#!/bin/bash",
        f"# Submits {jobs} packs that between them run all {len(chans)} one-channel parts of {base}, each part on its own",
        f"# core ({', '.join(str(n) for n in sizes)} per pack); written by scripts/seed_job_parallel.py pack. The parts' own",
        "# one-channel jobs must not be queued or running at the same time (two jobs would write one result file):",
        "# this script refuses while any is.",
        f"# Run from the repo root on the cluster ({HPC_REMOTE_REPO_ROOT}).",
        "#",
        f"# Cancel the one-channel parts:  {per_part_guard.split(': ', 1)[1]}",
        f"# Cancel the packs:  squeue -u $USER -h -o \"%i %j\" | awk '$2 ~ /^{base}__pack/ {{print $1}}' | xargs -r scancel",
        f"# When every part is done, bring back {parts_repo_dir}/*{seed_job.RESULT_SUFFIX} and on the PC run:",
        f"#   python scripts/seed_job_parallel.py merge {repo_relative(spec_path)}",
        "set -euo pipefail",
        "",
        "# read the queue first, outside the `if`: a failing squeue then stops the script (set -e) instead of",
        "# reading as 'nothing queued'",
        "QUEUED=\"$(squeue -u \"$(id -un)\" -h -o \"%j\")\"",
        f"if printf '%s\\n' \"$QUEUED\" | grep -q '^{part_prefix}'; then",
        "    echo 'One-channel parts of this search are still queued or running. Cancel them first: the command is at the top of this script.'",
        "    exit 1",
        "fi",
        "",
    ] + [f"sbatch {repo_relative(p)}" for p in scripts] + [""]
    with open(submit, "w", newline="\n", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return scripts, submit


def merge(spec_path, out=None, force=False):
    """The full result from the parts' results, in the spec's channel order. Refuses unless every part is there,
    complete, and answers this spec's own part."""
    spec = _load(spec_path)
    out = out or os.path.join(os.path.dirname(os.path.abspath(spec_path)), _base(spec_path) + seed_job.RESULT_SUFFIX)
    if os.path.isfile(out) and not force and _load(out).get("complete"):
        raise SystemExit(f"{out} is already a complete result; pass --force to replace it")
    rows, problems, provenance = [], [], []
    for ch in spec["channels"]:
        path = part_result_path(spec_path, ch)
        if not os.path.isfile(path):
            problems.append(f"{ch['name']}: no result at {path}")
            continue
        part = _load(path)
        want = seed_job.spec_hash(part_spec(spec, ch))
        if part.get("specHash") != want:
            problems.append(f"{ch['name']}: {path} answers spec {part.get('specHash')!r}, not this spec's part {want}")
            continue
        if not part.get("complete"):
            problems.append(f"{ch['name']}: {path} is incomplete (the part is still running, or stopped)")
            continue
        per = part.get("perChannel") or []
        if len(per) != 1 or per[0].get("name") != ch["name"]:
            problems.append(f"{ch['name']}: {path} holds {[p.get('name') for p in per]}, not this one channel")
            continue
        rows.append(per[0])
        provenance.append({"name": ch["name"], "specHash": want, "elapsedS": part.get("elapsedS"),
                           "finishedAt": part.get("finishedAt")})
    if problems:
        raise SystemExit("not merged:\n  " + "\n  ".join(problems))
    result = seed_job._result_shell(spec, rows, True, time.time())
    # each part's elapsedS is its last submission's, so the sum is a floor on the compute time
    result["elapsedS"] = round(sum(float(p["elapsedS"] or 0.0) for p in provenance), 1)
    result["finishedAt"] = max(p["finishedAt"] for p in provenance if p["finishedAt"])
    result["mergedFrom"] = provenance
    seed_job._write_checkpoint(out, result)
    return out, result


def main(argv=None):
    ap = argparse.ArgumentParser(description="split a Discovery seed job into one cluster job per channel, or merge "
                                             "the parts' results back into one")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sp = sub.add_parser("split", help="write one job per channel and submit_all.sh beside the spec")
    sp.add_argument("spec")
    pk = sub.add_parser("pack", help="write --jobs scripts that run the parts several at a time (after split)")
    pk.add_argument("spec")
    pk.add_argument("--jobs", type=int, default=3, help="how many jobs the account runs at once (rangpur: 3)")
    mp = sub.add_parser("merge", help="merge the parts' results into <name>.result.json")
    mp.add_argument("spec")
    mp.add_argument("--out", default=None, help="where to write the merged result (default: beside the spec)")
    mp.add_argument("--force", action="store_true", help="replace an existing complete result")
    args = ap.parse_args(argv)
    if args.cmd == "split":
        made, submit = split(args.spec)
        warnings = sorted({w for m in made for w in m["warnings"]})
        for w in warnings:
            print(f"warning: {w}")
        print(f"{len(made)} parts in {repo_relative(parts_dir(args.spec))}/")
        print(f"on the cluster, from the repo root:  bash {repo_relative(submit)}")
        return 0
    if args.cmd == "pack":
        scripts, submit = pack(args.spec, jobs=args.jobs)
        print(f"{len(scripts)} packs in {repo_relative(parts_dir(args.spec))}/")
        print(f"on the cluster, from the repo root:  bash {repo_relative(submit)}")
        return 0
    out, result = merge(args.spec, out=args.out, force=args.force)
    n = sum(len(c["candidates"]) for c in result["perChannel"])
    print(f"merged {len(result['perChannel'])} channels, {n} candidates -> {out}")
    print("import it on the Seed page (Import HPC result)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
