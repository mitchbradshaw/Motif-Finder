# *S. commune* on rangpur: the detector sweep and the second unseen-recording test (2026-10-26)

## In plain words

R4 (the MiniRocket classifier) learned what a "real" event looks like from six UQ recording groups. We now want to
know whether that skill carries over to another lab's fungus: Adamatzky's public *Schizophyllum commune* recording.
Think of it as giving a student a past paper from a different school. First the 43 detector settings every UQ
recording got run over the new recording on the cluster, each with one shuffled copy of the signal as a control.
Then the results come back into the app, and we write down and fingerprint the marking rules before looking at
anything. Only then do we draw about 300 candidate events for the researcher to judge blind, and score the frozen
models once.

Nothing here has been submitted. The bundle was built on a sandbox copy of the database
(`scripts/thesis/scommune_bundle.py`); the real database was not written.

## What is in this folder

| | |
|---|---|
| Recording | `Schizophyllum commune.txt`, recordings 600–606 (active), 7 channels, 1 Hz, **mV**, 263,687 samples (73.2 h) |
| Settings | the same 43 as batch 3's mV recording (`L_LM_Jul_26_J_raw_fs2`): 30 CPU templates (the three `signal_threshold__threshold_mV_*` copies, not the V ones), the 12 W4-A CNN templates, and `mp_threshold__backend_auto` on CH1 and CH2. `dehshibi_spikes` waits for windows, as in every batch |
| Null | one phase-randomised draw per run (seed 0), as every batch |
| Jobs | 43 P2 chain jobs, **296 tasks**, in `Schizophyllum_commune/` (specs, `_out/job.json`, the recording's `manifest.json`) |
| Packs | `rq4s_cpu1` (105 tasks), `rq4s_cpu2` (105), `rq4s_gpuA` (44), `rq4s_gpuB` (42); `submit_rq4s.sh` submits all four |
| Size | 1.7 MB (no data arrays) |
| Upload archive | `DATA/derived/hpc/rq4_scommune_20261026/rq4_scommune_upload.tar.gz` (4.2 MB, not tracked: DATA/ is gitignored): `Working/`, `Adapters/`, `Pipelines/`, `scripts/rq4_overnight.py`, this folder and the 7 channel arrays. sha256 `7128fe033eecd38b78431820a1bd4d84199ace388ab605b88582e7ac53d15e4f` |

The CNN checkpoints (`MODELS/{GASF,GADF,recurrence}_cnn.pth`, `MODELS/fusion_cnn_3.pth`) are already on the cluster
from batch 3; the submit script refuses, naming them, if any is missing.

## Cost estimate

S. commune is short: 263,687 samples a channel, about a tenth of M2_aug and a thirteenth of LM_fs2.

- **CPU:** 210 tasks. The balancing estimate (batch 1's timings scaled by length) is 0.6 core-hours. Each task also
  pays about 20–40 s of Python start-up and imports, so allow **1–3 core-hours**. Two 8-core `cpu` jobs, 20-minute
  walls chaining: about **20–40 min wall**.
- **A100:** 84 CNN tasks and 2 matrix profiles. The CNN estimate is 2.3 core-hours. Each matrix profile takes about
  8 s on the A100 (780 s at M2_aug's length; the cost grows with the square of the length). Two jobs, 8 tasks at a
  time: about **15–30 min wall each**, so **at most 1 A100-hour** allocated in all.
- **Returned data: about 0.2–0.8 GB.** LM_fs2 returned 1.4 GB for 13.8 M channel-samples; this is 1.85 M, about
  0.2 GB. If every task also returns its full-length first-step signal, as L_LM's did (33 MB a task there, 1.9 MB
  here), add about 0.6 GB.
- **Quota:** small next to the 30 GB allocation, but batch 2 stopped at about 16 GB of returned results in the home
  folder. Check `quota -s` first (step 3).
- **Locally after import:** the database grows by about 39 bytes per detection. Batch 3's LM/CO added about 55 MB
  each; expect well under that. The step cache grows by about 2.7 times what is restored, so under 2 GB.

## The researcher's commands, in order

Git Bash on the PC, from `C:\Users\mmebr\Documents\CNN`; `ssh` lines on rangpur from `~/CNN`
(`/home/Student/s4699158/CNN`). `PY="/c/ProgramData/anaconda3/python.exe"` on the PC.

**1. Copy the archive to the cluster.**

```bash
scp DATA/derived/hpc/rq4_scommune_20261026/rq4_scommune_upload.tar.gz s4699158@rangpur.compute.eait.uq.edu.au:~/
```

**2. Unpack it into the repo on the cluster, then check the code and inputs.** The archive overwrites `Working/`,
`Adapters/`, `Pipelines/` and `scripts/rq4_overnight.py` with today's code, so the cluster computes exactly what the
specs were hashed from. Batch 3 ran the same way.

```bash
ssh s4699158@rangpur.compute.eait.uq.edu.au
cd ~/CNN
sha256sum ~/rq4_scommune_upload.tar.gz      # 7128fe033eecd38b78431820a1bd4d84199ace388ab605b88582e7ac53d15e4f
tar xzf ~/rq4_scommune_upload.tar.gz
ls DATA/derived/channels/Schizophyllum_commune_fs1/      # CH0.npy ... CH6.npy (2,109,624 bytes each)
ls MODELS/GASF_cnn.pth MODELS/GADF_cnn.pth MODELS/recurrence_cnn.pth MODELS/fusion_cnn_3.pth
source ~/miniconda3/etc/profile.d/conda.sh
conda activate aeon-env && python -c "import pyarrow, numba, stumpy; print('cpu env ok')"   # pyarrow: event_shape
conda activate torch_env && python -c "import torch, pyarrow; print('gpu env ok', torch.__version__)"
conda deactivate
python scripts/rq4_overnight.py report --out docs/thesis/hpc/rq4_scommune_20261026   # 296 tasks, all "missing"
```

If a CNN model is missing, copy it from the PC to the same path:
`scp MODELS/GASF_cnn.pth s4699158@rangpur.compute.eait.uq.edu.au:~/CNN/MODELS/` (each file is 16 MB).

**3. Check the space.**

```bash
quota -s          # need about 1 GB free; batch 2 died at about 16 GB of returned results
du -sh HPC/Detection/generated/rq4_* 2>/dev/null
# if short: bash HPC/Detection/generated/rq4_batch3/cleanup_copied.sh            (dry run)
#           bash HPC/Detection/generated/rq4_batch3/cleanup_copied.sh --apply    (only what the PC already holds)
```

**4. Submit.** This is the only step that spends cluster time.

```bash
bash docs/thesis/hpc/rq4_scommune_20261026/submit_rq4s.sh
```

**5. Monitor.**

```bash
squeue -u $USER -o "%i %j %T %M %L"
python scripts/rq4_overnight.py report --out docs/thesis/hpc/rq4_scommune_20261026   # complete / refused / crashed
tail -n 30 logs/rq4s_*.out
# cancel everything: squeue -u $USER -h -o "%i %j" | awk '$2 ~ /^rq4s_/ {print $1}' | xargs -r scancel
```

The packs resubmit themselves while any task has work left (at most 60 jobs each). Done when `report` shows
296 complete. A refused task names its reason; a `deconvolved_troughs` refusal means pyarrow is missing (step 2).

**6. Bring the results back.** On the cluster, one archive of every `return/` folder (paths kept):

```bash
tar czf ~/rq4s_return.tar.gz docs/thesis/hpc/rq4_scommune_20261026/Schizophyllum_commune/*_out/return
```

On the PC, from the repo root:

```bash
scp s4699158@rangpur.compute.eait.uq.edu.au:~/rq4s_return.tar.gz DATA/derived/hpc/rq4_scommune_20261026/
tar xzf DATA/derived/hpc/rq4_scommune_20261026/rq4s_return.tar.gz
"$PY" scripts/rq4_overnight.py report --out docs/thesis/hpc/rq4_scommune_20261026    # 296 complete, here too
```

The returned `step_cache/` folders under this folder are gitignored (`docs/thesis/hpc/**/*_out/return/*/step_cache/`);
each `result.json` is the record.

**7. Open a Discovery session on S. commune.** `adopt` files each job into the newest Discovery session on its
recording, and there is none yet. Since main `0ffadd5`, changing the recording opens that recording's own session
and leaves the others alone. Do this through the running 8765 bridge, without restarting it:

```bash
curl -s -X PUT http://127.0.0.1:8765/api/discovery/session -H "Content-Type: application/json" \
  -d '{"recording": "Schizophyllum commune", "channels": ["CH1","CH2","CH3","CH4","CH5","CH6","CH7"], "section": [0, 73.25], "name": "Schizophyllum_commune_rq4"}'
curl -s http://127.0.0.1:8765/api/discovery/session | "$PY" -c "import json,sys; s=json.load(sys.stdin)['session']; print(s['id'], s['name'], s['recordingFile'], s['channels'])"
```

Note the session id it prints: the exam's freeze needs it. Optionally, back up the database first:
`"$PY" -c "import sqlite3; sqlite3.connect('DATA/db/annotations.sqlite').backup(sqlite3.connect('DATA/db/backups/pre-scommune-20261026.sqlite'))"`.

**8. Adopt: a dry run first, then for real.**

```bash
"$PY" scripts/rq4_overnight.py adopt --url http://127.0.0.1:8765 --out docs/thesis/hpc/rq4_scommune_20261026/Schizophyllum_commune
"$PY" scripts/rq4_overnight.py adopt --url http://127.0.0.1:8765 --out docs/thesis/hpc/rq4_scommune_20261026/Schizophyllum_commune --apply --allow-project
```

The dry run lists 43 jobs, each with 7 tasks back (2 for `mp_threshold__backend_auto`), and the bytes it would
restore. `--apply` imports them one by one and then runs the three matrix-profile copies from the cached profiles:
46 runs in the new session. BEADs may differ from the cluster by 1–3 spans per channel, as in every batch.

Then put Discovery back on M2_aug:

```bash
curl -s -X PUT http://127.0.0.1:8765/api/discovery/session -H "Content-Type: application/json" -d '{"recording": "M2_aug_concat_fs1"}'
```

## The exam, after the import

The rules mirror the M4 held-out exam. *S. commune* is not held out, so no lock applies. Instead, the scripts
refuse any step out of order:

- the draw refuses a table other than the frozen one, and a seed or quota other than the manifest's;
- the marking refuses a verdict older than the freeze.

**1. Build the candidate-event table** (read-only on the database; prints the table folder):

```bash
"$PY" scripts/rq1b_candidate_events.py build --real --file "Schizophyllum commune.txt" --json
```

**2. Freeze the manifest and log it in the audit log through the bridge** (prints the sha256; writes
`DATA/derived/exam/scommune/{manifest.json, detectors.json, audit_body.json}` and copies to
`docs/rq_roundA_2/exam/scommune-exam-*.json`):

```bash
"$PY" scripts/m4_exam_freeze.py --recording "Schizophyllum commune.txt" --session <session id from step 7> \
    --table DATA/derived/candidate_events/<table key from step 1> --slug scommune --post-audit http://127.0.0.1:8765
```

Without `--post-audit`, POST `audit_body.json` yourself:
`curl -s -X POST http://127.0.0.1:8765/api/audit -H "Content-Type: application/json" -d @DATA/derived/exam/scommune/audit_body.json`.
The freeze is refused if the table holds a run that is not one of the session's.

**3. Look at the draw (a dry run: prints the strata, writes nothing):**

```bash
"$PY" scripts/rq1b_candidate_events.py queue --table DATA/derived/candidate_events/<table key> --real \
    --seed 20261027 --per-level 40 --per-family 15 \
    --exam-manifest DATA/derived/exam/scommune/manifest.json --exam-sha256 <sha256>
```

**4. Draw the sample and create the blind Review queue:** the same command with `--apply`. It saves
`<table>/sample_seed20261027_l40_f15/` and writes one blind queue, served shuffled. The draw is audited as
"unseen-recording exam: sample drawn". Expect up to 5 × 40 + 6 × 15 = 290 items, fewer where a stratum is small.

**5. The researcher judges.** In Review, open only the new queue; do not open Discovery's Map, Library or another
queue showing S. commune until it is done.

**6. Score once** (read-only; a `--dry-run` with the same arguments rehearses on synthetic verdicts first):

```bash
"$PY" scripts/m4_exam_score.py --real --manifest DATA/derived/exam/scommune/manifest.json --sha256 <sha256> \
    --sample DATA/derived/candidate_events/<table key>/sample_seed20261027_l40_f15 --queue <queue id from step 4>
```

This writes `DATA/derived/exam/scommune/results.json` and `docs/rq_roundA_2/findings/scommune-exam-<date>.md`:

- R4: AUC and balanced accuracy, with the within-stratum bootstrap (unweighted primary, design-weighted secondary);
- the four reference CNNs as in M4's amendment 1, each beside R4;
- detector agreement as a comparator;
- the estimated share of real candidates, the agreement ladder, and per-family and per-setting precision;
- R4's side-feature quantiles on the answered items (the known risk below).

## Known risks (also frozen in the manifest's `known_risks`)

- **Units and amplitude.** R4 was trained on V and mV recordings at 1 and 2 Hz, all read as mV. Their whole-signal
  standard deviation is 50–170 mV. S. commune's is 0.15–0.6 mV, and its sample-to-sample noise is 0.001–0.024 mV,
  against 0.008–0.042 mV for the training recordings. R4's shape features are z-normalised. Its side features
  (log duration, peak-to-peak, noise, SNR) are not, so they may fall outside their training range. This is recorded
  as a risk; nothing is rescaled.
- **Fixed-mV detectors.** The `signal_threshold` mV copies (−2/−5/−10 mV) and BEADs `delta_mv` 5/25 may find little
  or nothing at this amplitude. Their strata can be small or empty, which is reported, not filled.
- **Quota:** see the cost estimate; check `quota -s` before step 4.
