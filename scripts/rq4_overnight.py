"""The RQ4 overnight sweep: every detection template over every M2_aug channel, as packed cluster jobs.

The researcher's plan of 2026-10-17 (docs/rq_roundA_2/RQ4b-detector-sweep.md), as decided that evening:

* **What runs.** Every M2_aug detection template, on the whole signal, with one null draw (phase randomisation,
  seed 0, the RQ4b sweep setting):
  - the 13 base templates and the 24 `[rq4-sweep]` variants that apply to a volts recording (the three mV
    copies of `signal_threshold` are for mV recordings);
  - the twelve W4-A CNN templates.

  What is left out:
  - `dehshibi_spikes` and its two variants: `preprocessing.wavelet_transform`'s 320,000-sample cap is a memory
    limit that holds on the cluster too, so they wait for P3's windows.
  - The matrix profile, mostly. It runs as ONE template, `mp_threshold` with `backend: auto` (exact, GPU where
    there is one), on CH1_A1 and CH2_A1, with its null draw. The other three MP templates (thresholds 6 and 10,
    motifs) share its detrend → profile prefix, so once the result is imported their local runs read the
    profiles from the cache. Four profiles instead of eight, all reusable.
* **How it runs.** Each template run is a P2 chain job (`Working.discovery.chain_job`): one spec, one task per
  channel, the task computing the real chain and its draw on a scratch database and writing `return/task<i>/`.
  The account runs three jobs at once (HPC/README.md), so instead of P2's arrays the tasks go into four PACKS.
  A pack runs many tasks side by side, one core each (the detection blocks here are single-threaded), and
  resubmits itself while any of its tasks has work left:
  - `rq4_cpu1`, `rq4_cpu2`: the CPU templates, on the `cpu` partition, 8 cores, 20-minute wall;
  - `rq4_gpuA`, `rq4_gpuB`: the CNN templates and the matrix profile, on the `a100`, 8 cores, with no `--time`
    (the researcher's instruction). Each reads its own time left from `squeue` for its budget.
  The fourth pack queues until a slot frees.
* **How it comes back.** P2's import finds a job by the Discovery run waiting for it, and these specs are made
  here, not by the bridge. When P2 is merged, an adoption step registers one waiting run per spec and imports it
  (`chain_job.verify_results` / `restore_cache`, then the ordinary local sweep). Until then the results wait in
  `<spec>_out/return/`.

    python scripts/rq4_overnight.py build --db <copy of DATA/db/annotations.sqlite> [--only NAME ...] [--span A B]
    python scripts/rq4_overnight.py pending <tasks file> <failed file>   # used by the pack scripts on the cluster

`build` must run with the main checkout as the working directory (it reads `DATA/derived/channels/...` and hashes
those files), and the database must be a COPY: `init_db()` and the canonical templates are written into it.

Dev tooling: not imported by the app.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

SOURCE = "M2_aug_concat_fs1.mat"
SPAN = (0, 2_595_600)                       # the Discovery session's whole-recording section, as the bridge plans it
NULL = {"paired": True, "params": {"method": "phase_randomize", "seed": 0}, "draws": 1}
NO_NULL = {"paired": False, "params": None, "draws": 0}
OUT_REL = os.path.join("HPC", "Detection", "generated", "rq4_overnight")

BASE = ["drop_detection_v1", "drop_detection_v5", "symbol_search", "Wavelet_detection_prototype", "wavelet_encoded",
        "signal_threshold", "noise_threshold", "deconvolved_troughs", "OASIS_Deconvolution", "BEADs_invert_detect_v1"]
#: refused on the whole signal anywhere (wavelet_transform's memory cap): they wait for P3's windows
WAIT_FOR_WINDOWS = ["dehshibi_spikes", "dehshibi_spikes__epsilon_factor_0p02", "dehshibi_spikes__epsilon_factor_0p1"]
#: the mV copies of signal_threshold: M2_aug is stored in volts
NOT_FOR_VOLTS = ["signal_threshold__threshold_mV_m2", "signal_threshold__threshold_mV_m5",
                 "signal_threshold__threshold_mV_m10"]
MP_TEMPLATES = ["mp_threshold", "mp_motifs", "mp_threshold__threshold_6", "mp_threshold__threshold_10"]
MP_CHANNELS = ["CH1_A1", "CH2_A1"]

#: rough seconds per task (real run + one draw, one 721-h channel), for balancing the packs only.
#: - CPU: one whole-signal task each, measured 2026-10-17 on the PC with about 30 processes on 16 cores, halved
#:   (drop_detection_v1 133 s, BEADs 137, symbol_search 156, OASIS 321, wavelet_encoded 325, deconvolved_troughs
#:   346, Wavelet_detection_prototype 415).
#: - CNN: W4-A's per-window timings (CPU-bound picture making).
#: - The matrix profile on the A100 is not measured, so it is a placeholder.
EST_S = {"drop_detection": 70, "symbol_search": 80, "Wavelet_detection_prototype": 210, "wavelet_encoded": 165,
         "signal_threshold": 40, "noise_threshold": 40, "deconvolved_troughs": 175, "OASIS_Deconvolution": 160,
         "BEADs_invert_detect_v1": 70, "mp_threshold": 5400,
         "cnn_fusion3_1min": 4400, "cnn_fusion3_10min": 440, "cnn_fusion3_60min": 90,
         "cnn_1min": 1950, "cnn_10min": 220, "cnn_60min": 50}


def _est(name):
    if name.startswith("cnn_"):
        model, scale = name.split("_")[1], name.split("_")[-1]
        return EST_S.get(f"cnn_{model}_{scale}") or EST_S[f"cnn_{scale}"]
    for key, s in EST_S.items():
        if name.startswith(key):
            return s
    return 120


def _load_templates(conn):
    from webui.server import templates as T
    T.seed_canonical(conn)                                    # the twelve CNN templates are code, not yet rows
    rows = conn.execute("SELECT id, name, kind, steps_json, description FROM templates ORDER BY id").fetchall()
    return {r[1]: {"id": r[0], "name": r[1], "kind": r[2], "steps": json.loads(r[3]), "description": r[4]}
            for r in rows}


def sweep_entries(templates):
    """[(label, template name, steps, channel names or None for all, null, pack kind)]: what tonight runs."""
    variants = [n for n, t in templates.items() if (t["description"] or "").startswith("[rq4-sweep]")]
    cpu = [n for n in BASE + variants
           if n not in WAIT_FOR_WINDOWS + NOT_FOR_VOLTS + MP_TEMPLATES and not n.startswith("mp_")]
    missing = [n for n in BASE if n not in templates]
    if missing:
        raise SystemExit(f"templates not in the database: {missing}")
    out = [(n, n, templates[n]["steps"], None, NULL, "cpu") for n in cpu]
    cnn = sorted(n for n, t in templates.items() if n.startswith("cnn_") and n != "cnn_detection"
                 and t["kind"] == "detection")
    if len(cnn) != 12:
        raise SystemExit(f"expected the twelve W4-A CNN templates, found {cnn}")
    out += [(n, n, templates[n]["steps"], None, NULL, "gpu") for n in cnn]
    mp = [dict(s) for s in templates["mp_threshold"]["steps"]]
    for s in mp:
        if (s.get("algorithm") or "") == "matrix_profile":
            s["params"] = dict(s.get("params") or {}, backend="auto")
    out.append(("mp_threshold__backend_auto", "mp_threshold__backend_auto", mp, MP_CHANNELS, NULL, "gpu"))
    return out


def _recordings(conn, names=None):
    from Working.discovery.channels import channel_name
    rows = conn.execute("SELECT id, channel FROM recordings WHERE source_file = ? AND active = 1 ORDER BY channel",
                        (SOURCE,)).fetchall()
    chans = [(int(r[0]), channel_name(SOURCE, int(r[1]), len(rows))) for r in rows]
    if names:
        chans = [c for c in chans if c[1] in names]
    return chans


def build(db, *, only=None, span=SPAN, out_rel=OUT_REL, null_draws=None):
    """Write one P2 chain job per sweep entry and the four packs. Returns the manifest."""
    from Working.database.schema import init_db
    from Working.discovery import chain_job, fanout

    conn = init_db(db)
    templates = _load_templates(conn)
    entries = sweep_entries(templates)
    if only:
        entries = [e for e in entries if e[0] in only]
    out_dir = os.path.join(REPO, out_rel)
    os.makedirs(out_dir, exist_ok=True)
    manifest = {"source": SOURCE, "span": list(span), "jobs": [], "refused": []}
    tasks = {"cpu": [], "gpu": []}
    for label, template, steps, names, null, kind in entries:
        null = dict(null, draws=null_draws) if (null_draws is not None and null["paired"]) else null
        chans = _recordings(conn, names)
        plan = fanout.plan(conn, steps=steps, recording_ids=[c[0] for c in chans], span=tuple(span),
                           ceiling_s=fanout.ceiling_s(conn), null_draws=null["draws"], surrogate=null["paired"],
                           surrogate_params=null["params"])
        plan["null"] = dict(null, reason=None)
        plan["template"] = template
        if not plan.get("runnable"):
            manifest["refused"].append({"label": label, "reason": plan.get("reason"), "refused": plan.get("refused")})
            continue
        try:
            spec = chain_job.build_spec(conn, plan, label=label, null=null, template=template)
        except chain_job.ExportRefused as e:
            manifest["refused"].append({"label": label, "reason": str(e)})
            continue
        h = chain_job.spec_hash(spec)
        base = f"{label}_{len(chans)}ch_{int(span[0])}-{int(span[1])}_{h[:6]}"
        made = chain_job.write_job(spec, out_dir=out_dir, base_name=base)
        manifest["jobs"].append({"label": label, "template": template, "specHash": h, "kind": kind,
                                 "spec": made["spec_repo_path"], "out": made["result_repo_path"],
                                 "channels": [c[1] for c in chans], "draws": null["draws"],
                                 "profile": spec["profile"]})
        for t in spec["targets"]:
            tasks[kind].append((_est(label), made["spec_repo_path"], made["result_repo_path"], t["index"],
                                f"{label}/{t['channelName']}"))
    packs = _write_packs(out_dir, out_rel, tasks)
    manifest["packs"] = packs
    with open(os.path.join(out_dir, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
    conn.close()
    return manifest


def _balance(tasks, n):
    """Longest first into the emptiest of n bins; each bin keeps longest-first order, so the long tasks start
    early and the short ones fill the cores at the end."""
    bins = [[] for _ in range(n)]
    load = [0.0] * n
    for t in sorted(tasks, key=lambda t: -t[0]):
        i = load.index(min(load))
        bins[i].append(t)
        load[i] += t[0]
    return bins, load


# The pack script. Everything in it is scheduling: the computation is `python -m Working.discovery.chain_job`, one
# process per task, exactly the command P2's own array script runs.
_PACK = r"""#!/bin/bash
#SBATCH --job-name={name}
#SBATCH --chdir={remote_root}
#SBATCH --output={remote_root}/logs/{name}_%j.out
#SBATCH --error={remote_root}/logs/{name}_%j.err
{time_line}{partition_lines}
#SBATCH --cpus-per-task={cpus}
# RQ4 overnight sweep (scripts/rq4_overnight.py), pack {name}: {n_tasks} chain-job tasks, {parallel} at a time,
# one core each, from {tasks_file}.
# Each task is `python -m Working.discovery.chain_job --spec S --out O --task I`, P2's own command: the real chain
# and its null draw for one channel, written to O/return/task<I>/. A finished task is skipped, and a stopped one
# continues from its own cache.
# {wall_note}
# No task starts with under {min_launch} s left. A task that crashes is noted in {failed_file} and tried once more
# in the next job. While any task has work left this script resubmits itself; it is capped at {max_chain} jobs. If
# every task this job started crashed, the environment is wrong: it stops and does not resubmit.
CHAIN_INDEX="${{1:-1}}"
MAX_CHAIN={max_chain}
TASKS={tasks_file}
FAILED={failed_file}
PARALLEL={parallel}
MIN_LAUNCH={min_launch}

echo "========================================"
echo "Job ID       : $SLURM_JOB_ID"
echo "Job name     : $SLURM_JOB_NAME"
echo "Node         : $SLURMD_NODENAME"
echo "CPUs         : ${{SLURM_CPUS_PER_TASK:-?}}, $PARALLEL tasks at a time"
echo "Chain        : $CHAIN_INDEX / $MAX_CHAIN"
echo "Started      : $(date)"
echo "========================================"

mkdir -p logs "$(dirname "$FAILED")"
touch "$FAILED"

{module_line}source ~/miniconda3/etc/profile.d/conda.sh
conda activate {conda_env}

# one core per task: numba, BLAS and torch would otherwise each size their thread pools from the node
export NUMBA_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1

START=$(date +%s)
{limit_block}
DEADLINE=$((START + LIMIT * 85 / 100))
echo "Time limit   : $LIMIT s; no task starts after $((DEADLINE - MIN_LAUNCH - START)) s; budgets end by $((DEADLINE - START)) s"

# the tasks still to do (not complete, not refused, not failed twice), one python start for the whole list
python scripts/rq4_overnight.py pending "$TASKS" "$FAILED" > "logs/{name}_${{SLURM_JOB_ID}}.todo" || {{
    echo ">>> The pending check failed -- NOT resubmitting (is scripts/rq4_overnight.py on the cluster?)"; exit 1; }}
echo "To do        : $(wc -l < "logs/{name}_${{SLURM_JOB_ID}}.todo") tasks"

LAUNCHED=0; CRASHED=0
declare -A WHAT
# reap N: wait until at most N tasks run, noting each finished task's exit. Exit 0 is done or stopped at its
# budget, 3 is refused (the reason is in its result.json), 124 is `timeout` inside a step (it continues next job);
# anything else is a crash. Portable to bash 4 (no `wait -n -p`).
reap() {{
    local keep="$1" P RC RUNNING
    while true; do
        RUNNING=" $(jobs -rp | tr '\n' ' ') "
        for P in "${{!WHAT[@]}}"; do
            case "$RUNNING" in *" $P "*) continue;; esac
            wait "$P"; RC=$?
            if [ "$RC" -ne 0 ] && [ "$RC" -ne 124 ] && [ "$RC" -ne 3 ]; then
                echo "${{WHAT[$P]}} $RC" >> "$FAILED"; CRASHED=$((CRASHED + 1))
                echo ">>> crashed (exit $RC): ${{WHAT[$P]}}"
            fi
            unset "WHAT[$P]"
        done
        [ "${{#WHAT[@]}}" -le "$keep" ] && return 0
        sleep 5
    done
}}
while read -r SPEC OUT TASK LABEL; do
    reap $((PARALLEL - 1))
    NOW=$(date +%s); BUDGET=$((DEADLINE - NOW))
    if [ "$BUDGET" -lt "$MIN_LAUNCH" ]; then
        echo ">>> $BUDGET s left: no more tasks start in this job"
        break
    fi
    LOG="logs/{name}_${{SLURM_JOB_ID}}_$(echo "$LABEL" | tr '/' '_').log"
    # a matrix profile with `backend: auto` runs on the GPU; should CUDA be missing it falls back to stump on the
    # CPU, which on one thread would take days, so it gets four
    THREADS=1; case "$LABEL" in mp_*) THREADS=4;; esac
    NUMBA_NUM_THREADS=$THREADS OMP_NUM_THREADS=$THREADS \
    timeout --signal=TERM $((BUDGET + 60)) python -m Working.discovery.chain_job --spec "$SPEC" --out "$OUT" \
        --task "$TASK" --budget-s "$BUDGET" > "$LOG" 2>&1 &
    WHAT[$!]="$SPEC $OUT $TASK $LABEL"
    LAUNCHED=$((LAUNCHED + 1))
done < "logs/{name}_${{SLURM_JOB_ID}}.todo"
reap 0

echo "========================================"
echo "Run finished : $(date): $LAUNCHED started, $CRASHED crashed"

if [ "$LAUNCHED" -ge 3 ] && [ "$CRASHED" -eq "$LAUNCHED" ]; then
    echo ">>> Every task this job started crashed: the environment or the code on the cluster is wrong -- NOT"
    echo ">>> resubmitting. Read one of logs/{name}_${{SLURM_JOB_ID}}_*.log; when fixed: sbatch {script} $CHAIN_INDEX"
    exit 1
fi

LEFT=$(python scripts/rq4_overnight.py pending "$TASKS" "$FAILED" | wc -l)
if [ "$LEFT" -eq 0 ]; then
    echo ">>> Pack {name} is done. Refused or failed tasks, if any, are listed by: python scripts/rq4_overnight.py report"
elif [ "$CHAIN_INDEX" -ge "$MAX_CHAIN" ]; then
    echo ">>> $LEFT tasks remain but the chain cap ($MAX_CHAIN) is reached -- stopping. To continue: sbatch {script} 1"
else
    NEXT=$((CHAIN_INDEX + 1))
    echo ">>> $LEFT tasks remain -- submitting job $NEXT of $MAX_CHAIN ..."
    sbatch {script} "$NEXT"
fi
echo "Finished     : $(date)"
echo "========================================"
"""

_TIME_LEFT = r"""# no --time (the researcher's instruction): the job's own limit, read from SLURM, sizes the budgets
LEFT_STR="$(squeue -h -j "$SLURM_JOB_ID" -o %L 2>/dev/null)"
to_seconds() {{  # D-HH:MM:SS, HH:MM:SS or MM:SS -> seconds; anything else -> empty
    local s="$1" d=0 h=0 m=0 x=0
    case "$s" in *-*) d="${{s%%-*}}"; s="${{s#*-}}";; esac
    IFS=: read -r a b c <<< "$s"
    if [ -n "$c" ]; then h=$a; m=$b; x=$c; elif [ -n "$b" ]; then m=$a; x=$b; else return; fi
    echo $(( 10#$d * 86400 + 10#$h * 3600 + 10#$m * 60 + 10#$x ))
}}
LIMIT="$(to_seconds "$LEFT_STR")"
if [ -z "$LIMIT" ]; then
    LIMIT={fallback_s}
    echo ">>> squeue gave '$LEFT_STR' for this job's time left: assuming $LIMIT s (the researcher's 5 h, less a margin)"
fi"""


def _write_packs(out_dir, out_rel, tasks):
    from Working.config import HPC_CONDA_ENV_CPU, HPC_CONDA_ENV_GPU, HPC_CPU_PARTITION, HPC_GPU_PARTITION, \
        HPC_REMOTE_REPO_ROOT

    rel = out_rel.replace(os.sep, "/")
    plans = []
    cpu_bins, cpu_load = _balance(tasks["cpu"], 2)
    gpu_bins, gpu_load = _balance(tasks["gpu"], 2)
    for kind, bins, loads in (("cpu", cpu_bins, cpu_load), ("gpu", gpu_bins, gpu_load)):
        for i, (b, load) in enumerate(zip(bins, loads)):
            name = f"rq4_{kind}{(i + 1) if kind == 'cpu' else 'AB'[i]}"
            tasks_file = f"{rel}/tasks_{name}.txt"
            with open(os.path.join(out_dir, f"tasks_{name}.txt"), "w", newline="\n", encoding="utf-8") as f:
                for _est_s, spec, out, task, label in b:
                    f.write(f"{spec} {out} {task} {label}\n")
            gpu = kind == "gpu"
            script_rel = f"{rel}/{name}.sh"
            text = _PACK.format(
                name=name, remote_root=HPC_REMOTE_REPO_ROOT, n_tasks=len(b), parallel=8, cpus=8,
                tasks_file=tasks_file, failed_file=f"{rel}/state/{name}.failed", max_chain=60,
                min_launch=(600 if gpu else 240), script=script_rel,
                time_line=("" if gpu else "#SBATCH --time=00:20:00\n"),
                partition_lines=(f"#SBATCH --partition={HPC_GPU_PARTITION}\n#SBATCH --gres=gpu:a100" if gpu
                                 else f"#SBATCH --partition={HPC_CPU_PARTITION}"),
                wall_note=("No --time: the a100 job runs to the account's own limit (the researcher expects 5 h); "
                           "budgets are sized from the time SLURM reports left." if gpu else
                           "Wall 20 min: the cpu partition's own limit is unverified (Working/config.py), so this "
                           "is the conservative floor; the pack chains through it."),
                module_line=("module load cuda/12.2\n" if gpu else ""),
                conda_env=(HPC_CONDA_ENV_GPU if gpu else HPC_CONDA_ENV_CPU),
                limit_block=(_TIME_LEFT.format(fallback_s=4 * 3600 + 30 * 60) if gpu else "LIMIT=1200"))
            with open(os.path.join(out_dir, f"{name}.sh"), "w", newline="\n", encoding="utf-8") as f:
                f.write(text)
            plans.append({"name": name, "script": script_rel, "tasks": len(b), "estimateCoreS": round(load)})
    lines = ["#!/bin/bash",
             "# The RQ4 overnight sweep (scripts/rq4_overnight.py): four packs. The account runs three jobs at once, "
             "so the",
             "# fourth waits in the queue until one finishes. Run from the repo root on the cluster "
             f"({HPC_REMOTE_REPO_ROOT}).",
             "#",
             "# Cancel the sweep:  squeue -u $USER -h -o \"%i %j\" | awk '$2 ~ /^rq4_/ {print $1}' | xargs -r scancel",
             "# Progress:          python scripts/rq4_overnight.py report",
             f"# Bring back:        every {rel}/*_out/return/ folder (keep the paths)",
             "set -euo pipefail",
             ""] + [f"sbatch {p['script']}" for p in plans] + [""]
    with open(os.path.join(out_dir, "submit_rq4_overnight.sh"), "w", newline="\n", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return plans


def pending(tasks_file, failed_file):
    """Print the task lines with work left: not complete, not refused, not crashed twice."""
    from Working.discovery import chain_job
    failed = {}
    if os.path.isfile(failed_file):
        with open(failed_file, encoding="utf-8") as f:
            for line in f:
                parts = line.split()
                if len(parts) >= 3:
                    key = (parts[0], parts[1], parts[2])
                    failed[key] = failed.get(key, 0) + 1
    with open(tasks_file, encoding="utf-8") as f:
        for line in f:
            parts = line.split()
            if len(parts) < 4:
                continue
            spec, out, task = parts[0], parts[1], parts[2]
            if failed.get((spec, out, task), 0) >= 2:
                continue
            if chain_job.task_status(out, int(task))["state"] in ("missing", "partial"):
                sys.stdout.write(line if line.endswith("\n") else line + "\n")
    return 0


def report(out_rel=OUT_REL):
    """Per pack: tasks complete / partial / missing / refused / crashed, and every refusal's reason."""
    from Working.discovery import chain_job
    out_dir = os.path.join(REPO, out_rel)
    with open(os.path.join(out_dir, "manifest.json"), encoding="utf-8") as f:
        manifest = json.load(f)
    for p in manifest["packs"]:
        counts, notes = {}, []
        failed_path = os.path.join(out_dir, "state", f"{p['name']}.failed")
        crashed = set()
        if os.path.isfile(failed_path):
            with open(failed_path, encoding="utf-8") as f:
                crashed = {tuple(l.split()[:3]) for l in f if l.strip()}
        with open(os.path.join(out_dir, f"tasks_{p['name']}.txt"), encoding="utf-8") as f:
            for line in f:
                spec, out, task, label = line.split()[:4]
                st = chain_job.task_status(out, int(task))
                state = st["state"]
                if state in ("missing", "partial") and (spec, out, task) in crashed:
                    state = "crashed"
                counts[state] = counts.get(state, 0) + 1
                if state in ("refused", "other", "unreadable"):
                    notes.append(f"    {label}: {state} — {st['reason']}")
        print(f"{p['name']}: {p['tasks']} tasks · " + " · ".join(f"{k} {v}" for k, v in sorted(counts.items())))
        for n in notes:
            print(n)
    if manifest.get("refused"):
        print("not exported (refused before the cluster):")
        for r in manifest["refused"]:
            print(f"    {r['label']}: {r['reason']}")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description="the RQ4 overnight sweep as packed P2 chain jobs")
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build", help="write the chain jobs, the packs and submit_rq4_overnight.sh")
    b.add_argument("--db", required=True, help="a COPY of DATA/db/annotations.sqlite (it is written to)")
    b.add_argument("--only", nargs="*", default=None, help="only these sweep labels (tests)")
    b.add_argument("--span", nargs=2, type=int, default=None, help="a section instead of the whole recording (tests)")
    b.add_argument("--out", default=OUT_REL, help="repo-relative output folder")
    b.add_argument("--draws", type=int, default=None, help="null draws for the paired runs (default 1)")
    p = sub.add_parser("pending", help="the task lines with work left (the pack scripts call this)")
    p.add_argument("tasks")
    p.add_argument("failed")
    r = sub.add_parser("report", help="progress per pack, and every refusal")
    r.add_argument("--out", default=OUT_REL)
    args = ap.parse_args(argv)
    if args.cmd == "pending":
        return pending(args.tasks, args.failed)
    if args.cmd == "report":
        return report(args.out)
    m = build(args.db, only=args.only, span=tuple(args.span) if args.span else SPAN, out_rel=args.out,
              null_draws=args.draws)
    print(f"{len(m['jobs'])} chain jobs, {sum(p['tasks'] for p in m['packs'])} tasks in {len(m['packs'])} packs:")
    for p in m["packs"]:
        print(f"    {p['name']}: {p['tasks']} tasks, about {p['estimateCoreS'] / 3600:.1f} core-hours")
    for r in m["refused"]:
        print(f"    refused: {r['label']}: {r['reason']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
