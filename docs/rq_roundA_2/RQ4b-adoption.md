# RQ4b: the overnight sweep comes back into Discovery (2026-10-18)

The record of bringing the RQ4 overnight sweep's 43 cluster jobs back as ordinary Discovery runs, so they show on
Discovery › Map. It belongs in `RQ4b-detector-sweep.md` ("What is still needed", the matrix-profile decision and the
log). That file has another session's uncommitted edits in the main checkout, so this file holds the record until
they are committed. RQ4b should then link here.

## In plain words

The cluster did the slow part overnight: for every detector and every channel it ran the chain and its null draw,
and kept its intermediate results. Importing a job copies those saved results into this machine's step cache, then
runs the ordinary sweep here. The heavy steps read from the cache and the cheap ones recompute. Every run is
therefore written into the database by the same code as a local run, and checked against what the cluster found.

## What was built

- **Adopting a job.** `POST /api/discovery/chain/adopt` registers the waiting Discovery run a job written outside
  the bridge needs. The import is P2's own, unchanged.
- **The whole round.** `python scripts/rq4_overnight.py adopt --url <bridge> [--apply [--allow-project]]` adopts
  and imports every job, then runs the matrix-profile copies.
- **Running a template like a job.** `POST /api/discovery/chain/local` runs a template over a job's channels, span
  and null, only when its matrix profiles are cached.
- How they work: `HPC/README.md`, "Adopting the overnight packs".

## The matrix-profile decision: option 1 built

`scripts/create_rq4_variants.py` writes `mp_threshold__backend_auto` (the overnight job's own template, until now not
a row) and the `backend: "auto"` copies of `mp_threshold__threshold_6`, `mp_threshold__threshold_10` and
`mp_motifs`, all marked `[rq4-sweep]`.

- `tests/test_create_rq4_variants.py` checks, against the tracked overnight spec, that their detrend → profile keys
  are the overnight job's for the real run and its draw.
- `adopt` runs them over CH1_A1 and CH2_A1, the whole signal and the job's null, from the imported profiles.
- Option 2 (a cache alias across the exact backends) is not built.

## What came back

- **Tasks.** All 674 are complete.
  - The first return had 47 refused, all `deconvolved_troughs` (its three jobs). The cluster's conda env had no
    pyarrow, and the chain's `event_shape` step writes a parquet table.
  - Re-run with pyarrow, they are back. Their 47 parquet tables read here (pandas with pyarrow 21).
- **Size.** 1,176 cache entries, 4.29 GB to restore, 1,348 runs.
- **Detections.** About 2.38 M from the real runs and 2.11 M from the null draws. Many come from a few loose
  variants:
  - `OASIS_Deconvolution__threshold_3`: 658 k;
  - `deconvolved_troughs__recovery_half_s_60`: 593 k;
  - the null draws of `signal_threshold__threshold_V_m0p002`: 723 k.
- **The overnight matrix profile.** `mp_threshold__backend_auto` finds **0 spans** on CH1_A1 and CH2_A1, real and
  draw. The profile is sound: values 0–7.88, median 3.04, against a possible ≈ 15.5 for a 1-minute window.
  Threshold 8 lies above every value on the whole signal. The A100 took 780 s per profile.

## The sandbox import (2026-10-18)

The worktree's code ran on a copy of the real database, reading the real channel files. Six jobs were imported:

| Job | Spans here | Agrees with the cluster | Import time |
|---|---|---|---|
| `drop_detection_v1` | 688 | yes, every channel | 286 s |
| `Wavelet_detection_prototype` | 24,859 | yes | 30 s |
| `noise_threshold` | 19,870 | yes | 196 s |
| `cnn_gasf_10min` | 6,706 | yes | 35 s |
| `mp_threshold__backend_auto` | 0 | yes | 15 s |
| `deconvolved_troughs` (then refused) | — | registered, waiting, its 16 tasks named | — |

The three `backend: "auto"` copies ran from the cached profiles in 10–45 s each. Threshold 6 found 44,258 spans
over the two channels, threshold 10 none, motifs 30.

**What an import costs:**
- about 39 bytes of database per detection;
- a step cache about 2.7 times what is restored, because the local sweep caches the steps it recomputes;
- 3–5 min for a CPU job whose cheap steps recompute, under a minute for a CNN or matrix-profile job.

**Found and fixed there.** On an uncalibrated machine the matrix profile has no cap and no estimate. The like-run
planned "unknown" and would have computed both whole-signal profiles locally. It now requires every matrix-profile
step to be cached, for the real run and for each draw.

## The real import (2026-10-18, 08:07–09:04)

Run through a project bridge on the main checkout. The bridge backed the database up first, to
`DATA/db/backups/20261018-080022.sqlite`. It seeded the 12 CNN templates, and templates 71–74 (the backend copies)
were created. Then `rq4_overnight.py adopt --apply --allow-project` ran.

- **All 43 jobs imported**, plus the three matrix-profile copies: 46 Discovery runs in session 2
  (`M2_aug_concat_fs1 screen`), all done, 2.42 M spans in all. Discovery › Map shows 48 algorithm rows on M2_aug.
- **Agreement with the cluster.** 40 jobs found exactly what the cluster found on every channel. The three
  `BEADs_invert_detect_v1` jobs differ by 1–3 spans on some channels (for example CH4_A2: 322 here, 323 on the
  cluster). Their run rows say so (`clusterCheck`). The likely cause is a floating-point difference between the two
  machines' libraries in BEADs' iterative baseline, but it is not investigated.
- **The matrix-profile copies:** threshold 6 found 44,258 spans over CH1_A1 and CH2_A1, threshold 10 none, motifs 30;
  the overnight threshold 8 found none.
- **Cost.**
  - The database grew from 67 MB to 251 MB.
  - The step cache now holds 4.6 GB in all: many cheap steps were already cached from earlier local runs, so it grew
    less than the sandbox suggested.
  - 57 min in all, mostly 25–105 s a job.
- `HPC/Detection/generated/rq4_overnight_upload.tar.gz` went to the Recycle Bin: it carried P2's code to the
  cluster before P2 merged.
