# Drop-seed transfer to seven other recordings

Prepared 7 November 2026. This is a follow-up experiment, not a result already incorporated into Chapter 7. The author explicitly authorised including M4 after its original classifier exam. No classifier is trained, no review queue is created and no database is written.

## Protocol

- Fixed original M2_aug drop exemplar: Library entry 185, seed ID `library:2:1553283:1553660`, 377 samples at 1 Hz.
- Targets: M2_concat, M4, LM, CO, full 16-channel MJu26a, SH and SO; 64 channels in total, each over its full cached recording.
- Up to 200 returns per channel, exclusion zone half the query length, 200 phase-randomised draws per channel, random seed 0.
- Preserve **377 seconds**, not 377 samples irrespective of sampling rate. M2_concat and M4 use the original query at 1 Hz. The 2 Hz recordings use the existing seed-bank adapter with sampling factor 2: the query is interpolated to 754 samples, and its distances are multiplied by sqrt(377/754). They remain on the original query's distance footing. This factor converts sampling rates; it is not a test of events lasting twice as long.
- Primary transfer comparison: keep the original M2_aug threshold **2.2080859509008204** fixed and compare recording and surrogate returns at that same threshold.
- Separate exploratory comparison: derive a new common target-specific threshold using the original rule (alpha 0.01 matches per draw per channel, no across-channel correction). Do not describe these recalibrated returns as transfer at the original threshold.
- Outputs are unreviewed shape matches. Neither a match nor a low surrogate count establishes human acceptance or biological identity. A channel returning 200 passing matches is flagged as capped.

## Files and inputs

The ready upload archive is in the main checkout:

`C:/Users/mmebr/Documents/CNN/DATA/derived/hpc/rq2_drop_transfer_20261107_upload.tar.gz`

It contains job specifications, resumable SLURM pack scripts, a small worker and a manifest. It contains the seed samples needed by the jobs, but no complete recordings. Keep this generated bundle under ignored `DATA/`; do not add its embedded signal samples to a public commit.

The cluster needs the existing CNN repository, its `aeon-env` environment and the caches listed in the archive's `INPUTS.txt`. All listed caches were found on the PC under `C:/Users/mmebr/Documents/CNN/DATA/derived/channels/`. The submission script checks all paths and array lengths before submitting anything. If the cluster lacks a cache, copy the corresponding folder from that PC path into `~/CNN/DATA/derived/channels/`, then rerun submission.

## Upload and submit

PowerShell on the PC:

```powershell
scp "C:\Users\mmebr\Documents\CNN\DATA\derived\hpc\rq2_drop_transfer_20261107_upload.tar.gz" s4699158@rangpur.compute.eait.uq.edu.au:~/
```

On rangpur:

```bash
cd ~/CNN
tar -xzf ~/rq2_drop_transfer_20261107_upload.tar.gz
bash DATA/derived/hpc/rq2_drop_transfer_20261107/submit_all.sh
```

Submission activates `aeon-env`, checks the inputs and refuses duplicate submissions while this experiment's jobs are queued or running. It submits 21 CPU packs using the existing seed-job code and 20-minute requests. Each pack runs its channel jobs on separate cores, checkpoints after every ten surrogate draws and resubmits unfinished work, with the repository's existing 30-submission chain limit. The account's scheduler decides when the packs run; no GPU is requested. Each worker is restricted to one computational thread.

Monitor with:

```bash
squeue -u "$USER" -o "%.18i %.50j %.10T %.10M"
```

Jobs are named `rq2x_1107_drop_*`. Logs go into `~/CNN/logs/`, with a separate channel log inside each pack. Existing unrelated jobs are not cancelled or changed.

## Collect and return

When the experiment's jobs have finished:

```bash
cd ~/CNN
bash DATA/derived/hpc/rq2_drop_transfer_20261107/collect_results.sh
```

Collection refuses missing, unfinished or mismatched channel results. It merges the seven searches and writes:

- `summary.csv` and `summary.json`: frozen-cut and target-recalibrated counts, surrogate means and cap flags;
- `matches.csv`: native sample indices, times in seconds, physical duration, distances and threshold flags;
- `return_results.tar.gz`: merged results, manifest and summaries, without full recordings.

PowerShell on the PC:

```powershell
scp s4699158@rangpur.compute.eait.uq.edu.au:~/CNN/DATA/derived/hpc/rq2_drop_transfer_20261107/return_results.tar.gz "C:\Users\mmebr\Documents\CNN\DATA\derived\hpc\rq2_drop_transfer_20261107_return.tar.gz"
```

These results can then be reviewed before updating the thesis. The bundle does not automatically import results into MycoWave or modify Library membership.

## Reproducing the bundle locally

The builder uses the repository's `Working.discovery.seed_job` and `scripts.seed_job_parallel`; it does not implement another search algorithm:

```powershell
cd C:\Users\mmebr\Documents\CNN
python scripts/thesis/seed_cross_recording.py build --data-root C:/Users/mmebr/Documents/CNN/DATA
```

An existing completed manifest is not overwritten; use a fresh `--out` path for a different experiment. The experiment has been checked locally; it has not been submitted or executed on rangpur by the assistant.
