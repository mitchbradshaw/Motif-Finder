"""Render recovery launchers using this repository's established Rangpur profile."""
from pathlib import Path
import sys

MAIN = Path("C:/Users/mmebr/Documents/CNN")
sys.path.insert(0, str(MAIN))

from Working.hpc.job_export import _profile


def render_launchers(manifest, relative, remote="/home/Student/s4699158/CNN"):
    scripts = {}
    for pack, cfg in manifest["packs"].items():
        # The existing heavy CPU pack reserves eight CPUs for three concurrent tasks.
        cpus = {"seed": 5, "cpu": 8, "cnn": 8, "mpA": 4, "mpB": 4}[pack]
        profile = _profile(cfg["gpu"], cpus=cpus)
        cuda = 'python -c "import torch; assert torch.cuda.is_available()" || exit 3' if cfg["gpu"] else ""
        scripts[pack + ".sh"] = f"""#!/bin/bash
#SBATCH --job-name=rec1108_{pack}
#SBATCH --chdir={remote}
#SBATCH --output={remote}/logs/rec1108_{pack}_%j.out
#SBATCH --error={remote}/logs/rec1108_{pack}_%j.err
#SBATCH --time={'05:00:00' if pack.startswith('mp') else '00:20:00'}
{profile['gpu_line']}
#SBATCH --cpus-per-task={cpus}
# Memory is allocated by the scheduler, as in the working repository launchers.
set -uo pipefail
CHAIN_INDEX=1
if [ "$#" -gt 0 ]; then CHAIN_INDEX="$1"; fi
case "$CHAIN_INDEX" in ''|*[!0-9]*) echo "Invalid chain index"; exit 2;; esac
cd {remote} || exit 3
{profile['module_line']}source ~/miniconda3/etc/profile.d/conda.sh || exit 3
conda activate {profile['conda_env']} || exit 3
export NUMBA_NUM_THREADS={'4' if pack.startswith('mp') else '1'} OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
{cuda}
python {relative}/worker.py pack --pack {pack}
RC=$?
if [ "$RC" -eq 10 ]; then
    NEXT=$((CHAIN_INDEX + 1))
    if [ "$NEXT" -le 60 ]; then
        sbatch {relative}/{pack}.sh "$NEXT"
    else
        echo "Chain cap reached; restart this pack manually."
    fi
elif [ "$RC" -ne 0 ]; then
    echo "Stopped with exit $RC. Read recovery/logs and collect outputs if the storage guard fired."
    exit "$RC"
fi
"""
    header = f"""#!/bin/bash
set -euo pipefail
cd {remote}
mkdir -p logs
QUEUED="$(squeue -u "$(id -un)" -h -o "%j")"
if printf '%s\\n' "$QUEUED" | grep -Eq '^(rec1108_|rq4n_|rq2x_1107_drop_)'; then
    echo 'Earlier sweep/transfer/recovery jobs are still queued or running; avoid duplicate work and try after they finish.'
    exit 1
fi
source ~/miniconda3/etc/profile.d/conda.sh
conda activate aeon-env
python {relative}/worker.py prepare
python {relative}/worker.py check
"""
    active = [p for p in manifest["packs"] if any(t["pack"] == p for t in manifest["tasks"])]
    # Check every resource request before the first real submission.
    header += "\n".join(f"sbatch --test-only {relative}/{p}.sh" for p in active) + "\n"
    header += "\n".join(f"sbatch {relative}/{p}.sh" for p in active) + "\n"
    scripts["submit_all.sh"] = header
    return scripts


def write_launchers(out, manifest, relative):
    for name, contents in render_launchers(manifest, relative).items():
        (Path(out) / name).write_text(contents, encoding="utf-8", newline="\n")
