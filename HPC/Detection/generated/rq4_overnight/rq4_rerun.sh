#!/bin/bash
#SBATCH --job-name=rq4_rerun
#SBATCH --chdir=/home/Student/s4699158/CNN
#SBATCH --output=/home/Student/s4699158/CNN/logs/rq4_rerun_%j.out
#SBATCH --error=/home/Student/s4699158/CNN/logs/rq4_rerun_%j.err
#SBATCH --time=00:20:00
#SBATCH --partition=cpu
#SBATCH --cpus-per-task=8
# RQ4 overnight sweep (scripts/rq4_overnight.py), pack rq4_rerun: 47 chain-job tasks, 8 at a time,
# one core each, from HPC/Detection/generated/rq4_overnight/tasks_rq4_rerun.txt.
# Each task is `python -m Working.discovery.chain_job --spec S --out O --task I`, P2's own command: the real chain
# and its null draw for one channel, written to O/return/task<I>/. A finished task is skipped, and a stopped one
# continues from its own cache.
# Wall 20 min: the cpu partition's own limit is unverified (Working/config.py), so this is the conservative floor; the pack chains through it.
# No task starts with under 240 s left. A task that crashes is noted in HPC/Detection/generated/rq4_overnight/state/rq4_rerun.failed and tried once more
# in the next job. While any task has work left this script resubmits itself; it is capped at 20 jobs. If
# every task this job started crashed, the environment is wrong: it stops and does not resubmit.
CHAIN_INDEX="${1:-1}"
MAX_CHAIN=20
TASKS=HPC/Detection/generated/rq4_overnight/tasks_rq4_rerun.txt
FAILED=HPC/Detection/generated/rq4_overnight/state/rq4_rerun.failed
PARALLEL=8
MIN_LAUNCH=240

echo "========================================"
echo "Job ID       : $SLURM_JOB_ID"
echo "Job name     : $SLURM_JOB_NAME"
echo "Node         : $SLURMD_NODENAME"
echo "CPUs         : ${SLURM_CPUS_PER_TASK:-?}, $PARALLEL tasks at a time"
echo "Chain        : $CHAIN_INDEX / $MAX_CHAIN"
echo "Started      : $(date)"
echo "========================================"

mkdir -p logs "$(dirname "$FAILED")"
touch "$FAILED"

source ~/miniconda3/etc/profile.d/conda.sh
conda activate aeon-env

# one core per task: numba, BLAS and torch would otherwise each size their thread pools from the node
export NUMBA_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1

# The overnight refusals were 'Unable to find a usable engine' for parquet: check the engine is in THIS environment
# before setting anything aside
python -c "import fastparquet" 2>/dev/null || python -c "import pyarrow" 2>/dev/null || {
    echo ">>> No parquet engine (fastparquet or pyarrow) in $CONDA_DEFAULT_ENV -- NOT running. Install it there first."
    exit 1; }

# The first job of this chain sets each refused result aside (into the task's work/ folder, which stays here), so
# P2's task runs again from its own cache. Later jobs do not: a task that refuses again keeps its reason.
if [ "$CHAIN_INDEX" -eq 1 ]; then
    python scripts/rq4_rerun.py retry-refused "$TASKS" || {
        echo ">>> Could not set the refused results aside -- NOT running (is scripts/rq4_rerun.py on the cluster?)"; exit 1; }
fi

START=$(date +%s)
LIMIT=1200
DEADLINE=$((START + LIMIT * 85 / 100))
echo "Time limit   : $LIMIT s; no task starts after $((DEADLINE - MIN_LAUNCH - START)) s; budgets end by $((DEADLINE - START)) s"

# the tasks still to do (not complete, not refused, not failed twice), one python start for the whole list
python scripts/rq4_overnight.py pending "$TASKS" "$FAILED" > "logs/rq4_rerun_${SLURM_JOB_ID}.todo" || {
    echo ">>> The pending check failed -- NOT resubmitting (is scripts/rq4_overnight.py on the cluster?)"; exit 1; }
echo "To do        : $(wc -l < "logs/rq4_rerun_${SLURM_JOB_ID}.todo") tasks"

LAUNCHED=0; CRASHED=0
declare -A WHAT
# reap N: wait until at most N tasks run, noting each finished task's exit. Exit 0 is done or stopped at its
# budget, 3 is refused (the reason is in its result.json), 124 is `timeout` inside a step (it continues next job);
# anything else is a crash. Portable to bash 4 (no `wait -n -p`).
reap() {
    local keep="$1" P RC RUNNING
    while true; do
        RUNNING=" $(jobs -rp | tr '\n' ' ') "
        for P in "${!WHAT[@]}"; do
            case "$RUNNING" in *" $P "*) continue;; esac
            wait "$P"; RC=$?
            if [ "$RC" -ne 0 ] && [ "$RC" -ne 124 ] && [ "$RC" -ne 3 ]; then
                echo "${WHAT[$P]} $RC" >> "$FAILED"; CRASHED=$((CRASHED + 1))
                echo ">>> crashed (exit $RC): ${WHAT[$P]}"
            fi
            unset "WHAT[$P]"
        done
        [ "${#WHAT[@]}" -le "$keep" ] && return 0
        sleep 5
    done
}
while read -r SPEC OUT TASK LABEL; do
    reap $((PARALLEL - 1))
    NOW=$(date +%s); BUDGET=$((DEADLINE - NOW))
    if [ "$BUDGET" -lt "$MIN_LAUNCH" ]; then
        echo ">>> $BUDGET s left: no more tasks start in this job"
        break
    fi
    LOG="logs/rq4_rerun_${SLURM_JOB_ID}_$(echo "$LABEL" | tr '/' '_').log"
    # a matrix profile with `backend: auto` runs on the GPU; should CUDA be missing it falls back to stump on the
    # CPU, which on one thread would take days, so it gets four
    THREADS=1; case "$LABEL" in mp_*) THREADS=4;; esac
    NUMBA_NUM_THREADS=$THREADS OMP_NUM_THREADS=$THREADS \
    timeout --signal=TERM $((BUDGET + 60)) python -m Working.discovery.chain_job --spec "$SPEC" --out "$OUT" \
        --task "$TASK" --budget-s "$BUDGET" > "$LOG" 2>&1 &
    WHAT[$!]="$SPEC $OUT $TASK $LABEL"
    LAUNCHED=$((LAUNCHED + 1))
done < "logs/rq4_rerun_${SLURM_JOB_ID}.todo"
reap 0

echo "========================================"
echo "Run finished : $(date): $LAUNCHED started, $CRASHED crashed"

if [ "$LAUNCHED" -ge 3 ] && [ "$CRASHED" -eq "$LAUNCHED" ]; then
    echo ">>> Every task this job started crashed: the environment or the code on the cluster is wrong -- NOT"
    echo ">>> resubmitting. Read one of logs/rq4_rerun_${SLURM_JOB_ID}_*.log; when fixed: sbatch HPC/Detection/generated/rq4_overnight/rq4_rerun.sh $CHAIN_INDEX"
    exit 1
fi

LEFT=$(python scripts/rq4_overnight.py pending "$TASKS" "$FAILED" | wc -l)
if [ "$LEFT" -eq 0 ]; then
    echo ">>> Pack rq4_rerun is done. Refused or failed tasks, if any, are listed by: python scripts/rq4_overnight.py report"
elif [ "$CHAIN_INDEX" -ge "$MAX_CHAIN" ]; then
    echo ">>> $LEFT tasks remain but the chain cap ($MAX_CHAIN) is reached -- stopping. To continue: sbatch HPC/Detection/generated/rq4_overnight/rq4_rerun.sh 1"
else
    NEXT=$((CHAIN_INDEX + 1))
    echo ">>> $LEFT tasks remain -- submitting job $NEXT of $MAX_CHAIN ..."
    sbatch HPC/Detection/generated/rq4_overnight/rq4_rerun.sh "$NEXT"
fi
echo "Finished     : $(date)"
echo "========================================"
