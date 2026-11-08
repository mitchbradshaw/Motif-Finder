# Returned recovery audit — 8 November 2026

All seed work, the 29 recovered CPU tasks and all six recovered matrix-profile tasks are complete. The seed
checkpoint files were initially outside the copied recovery folder, then supplied by WinSCP and verified.
Only the **183 remaining CNN tasks** require computation. These are applications of existing reference CNN
checkpoints, not classifier training or the frozen M4 classifier examination.

| Recovery pack | Planned | Verified complete on PC | Left |
|---|---:|---:|---:|
| Seed channels | 5 | 5 | 0 |
| CPU detector tasks | 29 | 29 | 0 |
| CNN detector tasks | 250 | 67 | 183 |
| Matrix profile A | 3 | 3 | 0 |
| Matrix profile B | 3 | 3 | 0 |

The full 2 Hz sweep is now **831/1,014 complete**: MJu26a 587/674; SH 122/170; SO 122/170.
There are 97 whole settings out of 129 (35, 31, 31). The 183 pending recovery tasks comprise three confirmed
stall refusals and 180 not returned. Seven of those not-returned tasks still have older refused outputs in their
original directories; these historical errors are not seven additional recovery failures. Complete returns were
verified against frozen specification hashes and their declared cache-directory sizes. Frozen runtime and CNN
checkpoint hashes also match. All 102 complete detector recovery tasks were restored into their original import
locations on the PC; they have not been represented as a finished, imported candidate-agreement census.

## Completed seed experiment

All 64 searched channels now have 200 draws, a total of 12,800 channel-draws. The unchanged threshold returns
464 matches across seven target recordings. On MJu26a the complete 16-channel comparison is **71 real matches
against nine surrogate matches across 200 draws**, or **0.045 per draw summed across channels**. No channel hits
the 200-return limit at this threshold. Separate target recalibration returns 48 MJu26a matches at cut
2.0182372834533737; this is distinct from unchanged-threshold transfer. Full data: `seed_summary.csv`.
The completed blind review of those unchanged-threshold proposals is in the adjacent completed-reviews report.

## Why the CNN pack stopped

Slurm jobs 747683 and 747858 interrupted the one-minute fusion tasks on target indices 11, 13 and 15 at the
wall guard. Job 747967 then reported the existing two-no-progress-jobs guard and stopped the pack. Their state
files show `[0,0,0]` progress and two stalls. Code inspection confirms that CNN scoring checks cancellation
between batches but does **not** persist a within-step batch/window score checkpoint. Until a whole step is
cached, the next job repeats it. The earlier bundle README's statement that completed windows were checkpointed
was incorrect. Complete steps and finished real/surrogate runs can still be reused.

Repeated `ModuleNotFoundError: ruptures` messages come from the optional adapter registry. They also occur in
successful tasks and are not the cause of these CNN refusals. The supplied Slurm logs do not show a new quota,
OOM or scheduler-memory rejection for the recovery failure. There is no need to rerun successful CPU, MP or seed
work, or to change detector thresholds or model weights.

## Prepared continuation

PC folder: `C:/Users/mmebr/Documents/CNN/DATA/derived/hpc/recovery_20261108_cnn_resume/`.
Copy `cnn_longwall.py`, `cnn_longwall.sh`, `pc_verified_returns.json` into the existing Rangpur folder:
`/home/Student/s4699158/CNN/DATA/derived/hpc/recovery_20261108/`.
An equivalent small tar archive is beside the PC folder. The README gives the execution commands; transfer is
by WinSCP, with no collection commands required.

At the author's subsequent request, the continuation now uses a **three-hour pack budget (10,800 seconds)**,
a **9,900-second per-task budget** and a 40-minute minimum launch margin, with one concurrent CNN task. The
existing five-hour A100 scheduler allocation supplies additional margin. The regenerated helper, expanded folder
and tar archive contain the revised limits. A process already running retains the settings loaded at its start;
the replacement helper applies when a pack starts. It archives only the three confirmed
short-wall stall counters on an explicit one-time retry, retaining caches and the original result/error files.
The original no-progress guard remains active during the longer jobs. No scientific specification, runtime,
input or model hash is changed. Scheduler acceptance and actual completion still require running on Rangpur;
no remote jobs were submitted from this PC.

The 8-GiB output guard remains. Optional cache release in the helper accepts only exact result hashes, exact
cache file sets and every file's SHA-256, backed by verified intact PC copies. Its acknowledgement covers 98
cache directories among the 102 complete returns; four windowed results have no returned step cache. Results,
scratch work, inputs, specs, models and incomplete tasks are retained. No such release was executed locally.

After the CNN jobs complete, WinSCP source folders are:

- `/home/Student/s4699158/CNN/DATA/derived/hpc/recovery_20261108/rq4/` — returned results and caches;
- `/home/Student/s4699158/CNN/DATA/derived/hpc/recovery_20261108/logs/` — task diagnostics;
- `/home/Student/s4699158/CNN/logs/` — new `rec1108_cnnL_*.out` and `.err` files.

Copy into the matching PC project folders. The seed folder has already been supplied successfully.

Validation: eight focused tests passed across catalogue provenance/boundary handling and the operational retry
and exact-copy release helpers. Figures and aggregate counts were inspected; no classifier was trained, no raw
detector result recomputed locally, and no thesis PDF rebuilt. The longer-wall launcher is a proposed remedy
supported by the observed step timeouts, not a claim of remotely verified completion.
