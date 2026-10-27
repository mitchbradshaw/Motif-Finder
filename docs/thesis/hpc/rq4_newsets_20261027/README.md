# MJu26a, SH and SO at 2 Hz on rangpur: the detector sweep (2026-10-27)

## In plain words

Three recordings were only in the app at 10 Hz: MJu26a (lion's mane, 16 channels, 26.5 days), SH and SO (4 channels,
20 days each). Ten readings a second is more detail than the detectors need, and it makes every run five times dearer.
So each was turned into a 2 Hz copy by averaging every five readings into one, exactly as CO_fs2 and LM_fs2 were made
for batch 3. Think of it as printing a long photo at a lower resolution: the shapes we look for (drops and bursts lasting
seconds to hours) are all still there.

This folder runs the same 43 detector settings every other UQ recording got (batch 3's volts set) over the three new
copies on the cluster, each with one shuffled copy of the signal as a control. Then the results come back into the app
through Discovery, one session per recording.

Nothing here has been submitted. The bundle was built on a sandbox copy of the database
(`scripts/thesis/newsets_fs2.py bundle`); the real database was not written by the build.

## What is in this folder

| | |
|---|---|
| Recordings | `MJu26a_fs2.mat` (ids **692–707**, 16 ch), `SH_fs2.mat` (**708–711**, 4 ch), `SO_fs2.mat` (**712–715**, 4 ch). All 2 Hz, **V**, active. MJu26a: 4,578,553 samples a channel (635.9 h); SH and SO: 3,456,000 (480.0 h) |
| Settings | the same 43 as batch 3's volts recordings (`LM_fs2`, `CO_fs2`): 30 CPU templates (base `signal_threshold` and its V copies, not the mV ones; the three `dehshibi_spikes` settings included, as in batch 3), the 12 W4-A CNN templates, and `mp_threshold__backend_auto` on CH1 and CH2 of each recording |
| Null | one phase-randomised draw per run (seed 0), as every batch |
| Jobs | 129 P2 chain jobs (43 per recording), **1,014 tasks**: MJu26a 674, SH 170, SO 170. One sub-folder per recording with its specs, `_out/job.json` and `manifest.json` |
| Packs | `rq4n_cpu1` (648 tasks, 8 at a time), `rq4n_cpu2` (72 dehshibi tasks, 3 at a time: a 3.4 GB array each), `rq4n_gpuA` (147), `rq4n_gpuB` (147); `submit_rq4n.sh` submits all four |
| Size | 5.0 MB (no data arrays) |
| Upload archive | `DATA/derived/hpc/rq4_newsets_20261027/rq4_newsets_upload.tar.gz` (**660 MB**, gzip; 811 MB unpacked; not tracked: DATA/ is gitignored): `Working/`, `Adapters/`, `Pipelines/`, `scripts/rq4_overnight.py`, this folder (without this README) and the 24 channel arrays. sha256 `c6c7a1ec15bc7f1e0ed9c03d0ffd66e8eb3315a6b7056d3922388bbd23fce7e1` |

The CNN checkpoints (`MODELS/{GASF,GADF,recurrence}_cnn.pth`, `MODELS/fusion_cnn_3.pth`) are already on the cluster
from batch 3; the submit script refuses, naming them, if any is missing.

The archive holds the working tree's code as of 2026-10-27 11:57. Its 432 code files (`Working/`, `Adapters/`,
`Pipelines/`, `scripts/rq4_overnight.py`) equal commit `4294c55` file by file, line endings aside (checked 2026-10-27).

## How the 2 Hz copies were made

`scripts/thesis/newsets_fs2.py derive`, the method of `scripts/derive_fs2.py`: non-overlapping means of 5 consecutive
10 Hz samples (`Working/registration/excerpt.py::block_mean`), the trailing partial block dropped and counted, no other
filter, no detrending, no rescaling, float64. Read from the registered 10 Hz channel files, memory-mapped, one channel at
a time. No source sample is NaN or infinite. Each `DATA/derived/channels/<stem>/manifest.json` records the derivation.

- **SH, SO**: the 10 Hz is now **read**, not inferred: each file's MATLAB `duration` vector (decoded streaming) steps
  exactly 100 ms for all 17,280,000 steps, starting at t = 1,800,000 ms (30 min in), as LM and CO do.
- **MJu26a**: the block mean of `MJu26a_fs10`, itself MJu26a.mat's uneven samples linearly interpolated onto a 0.1 s
  grid.

## Cost estimate

Batch 3 (LM_fs2, CO_fs2, L_LM_fs2: 13 channels, 50.5 M channel-samples at 2 Hz) is the yardstick: all 552 tasks were
done 3.5 h after the first started, every CPU task under 7 min, each matrix profile 2.5–3.2 h a channel on the A100.
This batch is 24 channels and 100.9 M channel-samples, about twice batch 3, with the same six matrix-profile channels.

- **CPU:** 720 tasks. The balancing estimate is 35 core-hours (28.2 + 6.8). With start-up and imports, allow
  **40–60 core-hours**. `rq4n_cpu1` runs 8 at a time in 20-minute jobs that chain: about **5–8 h wall**.
- **A100:** 282 CNN tasks and 6 matrix profiles (about 2.5–3.2 h each, as batch 3's same-length channels). Balancing
  estimate 83 core-hours over two 8-task jobs: about **6–8 h wall each**, so **12–16 A100-hours** allocated in all.
- **Returned data: about 10 GB, possibly much more.** LM_fs2 and CO_fs2 returned 1.4 GB each for 13.8 M
  channel-samples, so SH and SO should bring about 1.4 GB each and MJu26a (73.3 M, 5.3 times as much) about 7.4 GB.
  On L_LM almost every task also returned its first step's full-length signal (33 MB a task). If MJu26a does the same
  (36.6 MB a task × 674), it adds up to about 25 GB more. LM and CO did not, and MJu26a is a volts recording like
  them, but watch the size (step 5).
- **Quota:** the allocation is 30 GB, and batch 2 stopped at about 16 GB of returned results in the home folder.
  The archive (660 MB) plus its unpacked copy (811 MB) add 1.5 GB. **Free at least 15 GB first** (step 3).
- **Locally after import:** batch 3's 129 jobs grew the database by about 170 MB and the step cache by 3.6 GB
  (11.7 GB returned). Expect about +200–300 MB and +4–8 GB here. The PC has about 56 GB free on C:.

## The researcher's commands, in order

Git Bash on the PC, from `C:\Users\mmebr\Documents\CNN`; `ssh` lines on rangpur from `~/CNN`
(`/home/Student/s4699158/CNN`). `PY="/c/ProgramData/anaconda3/python.exe"` on the PC.

**1. Copy the archive to the cluster.**

```bash
scp DATA/derived/hpc/rq4_newsets_20261027/rq4_newsets_upload.tar.gz s4699158@rangpur.compute.eait.uq.edu.au:~/
```

**2. Check the code and the inputs on the cluster.** The archive overwrites `Working/`, `Adapters/`, `Pipelines/` and
`scripts/rq4_overnight.py` with today's code, so the cluster computes exactly what the specs were hashed from.

```bash
ssh s4699158@rangpur.compute.eait.uq.edu.au
cd ~/CNN
sha256sum ~/rq4_newsets_upload.tar.gz      # c6c7a1ec15bc7f1e0ed9c03d0ffd66e8eb3315a6b7056d3922388bbd23fce7e1
tar xzf ~/rq4_newsets_upload.tar.gz && rm ~/rq4_newsets_upload.tar.gz      # frees the 660 MB once unpacked
ls -l DATA/derived/channels/MJu26a_fs2/ | head -3     # CH0.npy ... CH15.npy, 36,628,552 bytes each
ls -l DATA/derived/channels/SH_fs2/ DATA/derived/channels/SO_fs2/   # CH0..CH3.npy, 27,648,128 bytes each
ls MODELS/GASF_cnn.pth MODELS/GADF_cnn.pth MODELS/recurrence_cnn.pth MODELS/fusion_cnn_3.pth
source ~/miniconda3/etc/profile.d/conda.sh
conda activate aeon-env && python -c "import pyarrow, numba, stumpy; print('cpu env ok')"   # pyarrow: event_shape
conda activate torch_env && python -c "import torch, pyarrow; print('gpu env ok', torch.__version__)"
conda deactivate
python scripts/rq4_overnight.py report --out docs/thesis/hpc/rq4_newsets_20261027   # 1,014 tasks, all "missing"
```

If a CNN model is missing, copy it from the PC to the same path:
`scp MODELS/GASF_cnn.pth s4699158@rangpur.compute.eait.uq.edu.au:~/CNN/MODELS/` (each file is 16 MB).

**3. Check the space.** Need at least 15 GB free.

```bash
quota -s
du -sh HPC/Detection/generated/rq4_* docs/thesis/hpc/rq4_* 2>/dev/null
# if short, delete what the PC already holds (dry run first):
#   bash HPC/Detection/generated/rq4_batch3/cleanup_copied.sh
#   bash HPC/Detection/generated/rq4_batch3/cleanup_copied.sh --apply
```

**4. Submit.** This is the only step that spends cluster time.

```bash
bash docs/thesis/hpc/rq4_newsets_20261027/submit_rq4n.sh
```

**5. Monitor.**

```bash
squeue -u $USER -o "%i %j %T %M %L"
python scripts/rq4_overnight.py report --out docs/thesis/hpc/rq4_newsets_20261027   # complete / refused / crashed
tail -n 30 logs/rq4n_*.out
du -sh docs/thesis/hpc/rq4_newsets_20261027; quota -s                              # the returned size, as it grows
# cancel everything: squeue -u $USER -h -o "%i %j" | awk '$2 ~ /^rq4n_/ {print $1}' | xargs -r scancel
```

The packs resubmit themselves while any task has work left (at most 60 jobs each). Done when `report` shows 1,014
complete. A refused task names its reason; a `deconvolved_troughs` refusal means pyarrow is missing (step 2). If the
folder passes about 12 GB with tasks still to run, bring back what is complete (step 6) and free it before continuing.

**6. Bring the results back.** On the cluster, one archive per recording (paths kept), so each can be copied and
checked on its own:

```bash
for R in MJu26a_fs2 SH_fs2 SO_fs2; do
  tar czf ~/rq4n_return_$R.tar.gz docs/thesis/hpc/rq4_newsets_20261027/$R/*_out/return
done
ls -l ~/rq4n_return_*.tar.gz
```

On the PC, from the repo root:

```bash
for R in MJu26a_fs2 SH_fs2 SO_fs2; do
  scp s4699158@rangpur.compute.eait.uq.edu.au:~/rq4n_return_$R.tar.gz DATA/derived/hpc/rq4_newsets_20261027/
  tar xzf DATA/derived/hpc/rq4_newsets_20261027/rq4n_return_$R.tar.gz
done
"$PY" scripts/rq4_overnight.py report --out docs/thesis/hpc/rq4_newsets_20261027    # 1,014 complete, here too
```

The returned `step_cache/` folders under this folder are gitignored (`docs/thesis/hpc/**/*_out/return/*/step_cache/`);
each `result.json` is the record.

**7. Back up the database, then open one Discovery session per recording.** `adopt` files each job into the newest
Discovery session on its recording, and there is none yet. Changing the recording opens that recording's own session
and leaves the others alone. Through the running 8765 bridge, without restarting it:

```bash
curl -s -X POST http://127.0.0.1:8765/api/backups
curl -s -X PUT http://127.0.0.1:8765/api/discovery/session -H "Content-Type: application/json" \
  -d '{"recording": "MJu26a_fs2", "channels": ["CH1","CH2","CH3","CH4","CH5","CH6","CH7","CH8","CH9","CH10","CH11","CH12","CH13","CH14","CH15","CH16"], "section": [0, 635.92], "name": "MJu26a_fs2_rq4"}'
curl -s -X PUT http://127.0.0.1:8765/api/discovery/session -H "Content-Type: application/json" \
  -d '{"recording": "SH_fs2", "channels": ["CH1","CH2","CH3","CH4"], "section": [0, 480], "name": "SH_fs2_rq4"}'
curl -s -X PUT http://127.0.0.1:8765/api/discovery/session -H "Content-Type: application/json" \
  -d '{"recording": "SO_fs2", "channels": ["CH1","CH2","CH3","CH4"], "section": [0, 480], "name": "SO_fs2_rq4"}'
curl -s http://127.0.0.1:8765/api/discovery/session | "$PY" -c "import json,sys; s=json.load(sys.stdin)['session']; print(s['id'], s['name'], s['recordingFile'], s['channels'])"
```

The last line shows the open one (SO_fs2_rq4). Each PUT prints its session; note the three ids.

**8. Adopt: a dry run first, then for real, one recording at a time.**

```bash
for R in MJu26a_fs2 SH_fs2 SO_fs2; do
  "$PY" scripts/rq4_overnight.py adopt --url http://127.0.0.1:8765 --out docs/thesis/hpc/rq4_newsets_20261027/$R
done
```

Each dry run lists 43 jobs, each with every channel's task back (2 for `mp_threshold__backend_auto`), and the bytes it
would restore with the disk free. Then:

```bash
"$PY" scripts/rq4_overnight.py adopt --url http://127.0.0.1:8765 --out docs/thesis/hpc/rq4_newsets_20261027/MJu26a_fs2 --apply --allow-project
"$PY" scripts/rq4_overnight.py adopt --url http://127.0.0.1:8765 --out docs/thesis/hpc/rq4_newsets_20261027/SH_fs2 --apply --allow-project
"$PY" scripts/rq4_overnight.py adopt --url http://127.0.0.1:8765 --out docs/thesis/hpc/rq4_newsets_20261027/SO_fs2 --apply --allow-project
```

`--apply` imports the jobs one by one and then runs the three matrix-profile copies from the cached profiles: 46 runs
in each session. BEADs may differ from the cluster by 1–3 spans per channel, as in every batch.

Then put Discovery back on M2_aug:

```bash
curl -s -X PUT http://127.0.0.1:8765/api/discovery/session -H "Content-Type: application/json" -d '{"recording": "M2_aug_concat_fs1"}'
```

## Known points

- **The 10 Hz originals stay active** (`MJu26a_fs10`, `SH`, `SO`): whether to deactivate them is the researcher's call.
- **Species:** MJu26a_fs2 is recorded as lion's mane. SH and SO are left blank: not known.
- **L_LM_Jul_26_J_raw is MJu26a** (checked read-only 2026-10-27): its five channels are MJu26a_fs10 CH10, CH13, CH14,
  CH15, CH16 (1-based) × 1000 plus a constant offset per channel. Sweeping MJu26a_fs2 therefore re-sweeps those five
  channels, already swept at 2 Hz as `L_LM_Jul_26_J_raw_fs2` in batch 3 (now inactive). See
  `docs/datasets/NEW_RAW_2026-10.md`.
- Rebuild (needs a fresh backup taken through the bridge after any registration change, because a file copy of the
  live database misses its WAL):
  `"$PY" scripts/thesis/newsets_fs2.py bundle --date 20261027 --db-source DATA/db/backups/<stamp>.sqlite`.
