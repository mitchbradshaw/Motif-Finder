# The 2 Hz sweep, round 2: the 702 tasks that did not come back (2026-11-05)

## In plain words

The first cluster round (27 Oct bundle, `../README.md`) ran out partway. Of its 1,014 tasks, 312 came back complete.
- **31 whole jobs are now in the app** (every channel back):
  - MJu26a 13: OASIS ×3, deconvolved troughs ×3, `drop_detection_v1`, symbol search ×2, wavelet encoded ×3 and
    the Dehshibi wavelet prototype;
  - SH 9 and SO 9: OASIS ×3, deconvolved troughs ×3 and wavelet encoded ×3.
- **Nothing crashed.** The failure lists are empty.
- **It most likely stopped on space.** Each MJu26a task returns 30–100 MB (its first step's full signal), and the
  returned folder reached 15 GB of the 30 GB allowance.
- **Three tasks ran out of memory:** symbol search at 10 s per symbol on MJu26a CH4, CH13 and CH14 (a 1.7 GiB
  array, with eight tasks to a node).

This archive runs **only the 702 tasks that are left**. It holds the same code (commit `4294c55`'s, as in round 1),
the same 24 channel arrays and the same job specs, so every result it computes fits the round-1 jobs exactly. The
three out-of-memory tasks move to `rq4n_cpu2`, which runs three at a time.

| pack | tasks | MJu26a | SH | SO |
|---|---|---|---|---|
| `rq4n_cpu1` (8 at a time, 20-min jobs that chain) | 368 | 224 | 72 | 72 |
| `rq4n_cpu2` (3 at a time: Dehshibi, and the 3 big symbol searches) | 45 | 21 | 12 | 12 |
| `rq4n_gpuA` (A100) | 142 | 92 | 25 | 25 |
| `rq4n_gpuB` (A100) | 147 | 97 | 25 | 25 |
| **all** | **702** | 434 | 134 | 134 |

**Space is the risk.** MJu26a's 434 tasks should return about 26 GB and SH + SO about 4 GB, which is roughly the
whole 30 GB allowance. So bring results back in waves, and free each wave on the cluster once it is on the PC.
`rq4n_returns.py` does the bookkeeping:
- **Freeing keeps a task done.** It deletes a returned task's big `step_cache/` but keeps its `result.json`, so the
  task still counts as complete and no pack runs it again.
- **Freeing waits for the copy.** It only frees tasks that are already in a wave's list.

## Files

| | |
|---|---|
| Archive | `DATA/derived/hpc/rq4_newsets_20261027/rq4n_remaining_upload.tar.gz` (not tracked: DATA/ is gitignored); its sha256 is printed by `scripts/thesis/rq4n_remaining.py archive` and written below |
| Task lists | `tasks_rq4n_*.txt` here; inside the archive they replace the round-1 lists at `docs/thesis/hpc/rq4_newsets_20261027/` |
| Waves | `rq4n_returns.py` (`list`, `free`, `free --apply`) |
| Built by | `scripts/thesis/rq4n_remaining.py archive` (from the round-1 archive and the returned folders on the PC) |

sha256: see `SHA256.txt` beside this file.

## The researcher's commands, in order

Git Bash on the PC, from `C:\Users\mmebr\Documents\CNN`; `ssh` lines on rangpur from `~/CNN`.

**1. Copy the archive up.**

```bash
scp DATA/derived/hpc/rq4_newsets_20261027/rq4n_remaining_upload.tar.gz s4699158@rangpur.compute.eait.uq.edu.au:~/
```

**2. Clear round 1 on the cluster, then unpack.** The PC holds round 1's returns (all 312 complete tasks), so the
cluster's copy can go; that frees about 15 GB. If any task finished on the cluster after you copied round 1 back, it
is simply run again.

```bash
ssh s4699158@rangpur.compute.eait.uq.edu.au
cd ~/CNN
squeue -u $USER -o "%i %j %T"                      # nothing named rq4n_* should still be running
quota -s
rm -rf docs/thesis/hpc/rq4_newsets_20261027        # round 1's folder (the PC has its results)
sha256sum ~/rq4n_remaining_upload.tar.gz           # compare with SHA256.txt
tar xzf ~/rq4n_remaining_upload.tar.gz && rm ~/rq4n_remaining_upload.tar.gz
wc -l docs/thesis/hpc/rq4_newsets_20261027/tasks_rq4n_*.txt    # 368, 45, 142, 147
ls MODELS/GASF_cnn.pth MODELS/GADF_cnn.pth MODELS/recurrence_cnn.pth MODELS/fusion_cnn_3.pth
source ~/miniconda3/etc/profile.d/conda.sh
conda activate aeon-env && python -c "import pyarrow, numba, stumpy; print('cpu env ok')"
conda activate torch_env && python -c "import torch, pyarrow; print('gpu env ok')"
conda deactivate
python scripts/rq4_overnight.py report --out docs/thesis/hpc/rq4_newsets_20261027   # 702 tasks, all "missing"
quota -s
```

**3. Submit.** This is the only step that spends cluster time.

```bash
bash docs/thesis/hpc/rq4_newsets_20261027/submit_rq4n.sh
```

**4. Watch the space, and bring back a wave whenever the folder passes about 10 GB** (and once at the end).

```bash
du -sh docs/thesis/hpc/rq4_newsets_20261027; quota -s
python scripts/rq4_overnight.py report --out docs/thesis/hpc/rq4_newsets_20261027
```

A wave, on the cluster:

```bash
L=$(python docs/thesis/hpc/rq4_newsets_20261027/remaining_20261105/rq4n_returns.py list | tail -1)
tar czf ~/rq4n_wave_$(date +%m%d_%H%M).tar.gz -T "$L" "$L"
ls -l ~/rq4n_wave_*.tar.gz
```

On the PC, from the repo root (paths are kept, so it lands in the right folders):

```bash
scp s4699158@rangpur.compute.eait.uq.edu.au:~/rq4n_wave_*.tar.gz DATA/derived/hpc/rq4_newsets_20261027/
for W in DATA/derived/hpc/rq4_newsets_20261027/rq4n_wave_*.tar.gz; do tar xzf "$W"; done
"/c/ProgramData/anaconda3/python.exe" scripts/thesis/rq4n_status.py | grep -c WHOLE
```

Then, back on the cluster, free that wave (dry run first) and delete its tar:

```bash
python docs/thesis/hpc/rq4_newsets_20261027/remaining_20261105/rq4n_returns.py free
python docs/thesis/hpc/rq4_newsets_20261027/remaining_20261105/rq4n_returns.py free --apply
rm ~/rq4n_wave_*.tar.gz
```

**5. If a pack stops early.** A pack stops after 60 chained jobs, or if every task in a job crashed. Its log names
the command to continue: `sbatch docs/thesis/hpc/rq4_newsets_20261027/rq4n_<pack>.sh 1`.

**6. On the PC: the import.** Tell me when a wave is unpacked; I import the jobs that are now whole. The import uses
the same route as round 1, through the running 8765 bridge, with a database backup first, one recording's Discovery
session at a time, and `adopt --only <whole jobs> --apply --allow-project`. Afterwards I delete the returned copies
that duplicate the step cache.
