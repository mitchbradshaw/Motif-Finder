# Resume the drop transfer and 2 Hz detector sweep — 8 November 2026

This archive resumes the five unfinished drop-search channels and computes only the 285 detector tasks that did not return successfully. It does not submit from the PC, train a classifier, change the live annotation database or create review queues.

## Correction after the first submission rejection

The first recovery launchers incorrectly requested --mem=16G. Working/config.py records that this account's CPU partition has rejected both explicit 16G and 4G requests; the established launchers omit memory and use scheduler defaults. The corrected launchers follow Working.hpc.job_export._profile, request eight CPUs for the three-worker CPU pack, and restore the established CUDA module setup on GPU jobs.

The correction also replaces a malformed generated chain-index expression. The generated shell control flow was exercised with mocked Python and SLURM for completion, resubmission, chain limits, worker failures and scheduler failures. The submit script now validates every resource request with sbatch --test-only before any real submission; this option does not submit a job (https://slurm.schedmd.com/sbatch.html).

For a bundle already unpacked on rangpur, upload only the small patch:

    scp "C:\Users\mmebr\Documents\CNN\DATA\derived\hpc\recovery_20261108_slurm_fix.tar.gz" s4699158@rangpur.compute.eait.uq.edu.au:~/

Then on rangpur:

    cd ~/CNN
    tar -xzf ~/recovery_20261108_slurm_fix.tar.gz
    bash DATA/derived/hpc/recovery_20261108/submit_all.sh

This patch contains only the five pack scripts, submit_all.sh and this README. It does not overwrite checkpoints, scientific specifications, the manifest, input data, the runtime or models. The full upload archive is corrected too. The earlier release/cleanup steps need not be repeated for this launcher correction.

## Audited state

| Experiment | Complete | Remaining |
|---|---:|---:|
| Drop transfer | 59/64 channels | MJu26a CH6–CH10: 110/120/120/120/110 of 200 phase draws saved; 420 draws remain |
| 2 Hz sweep | 729/1,014 tasks | 258 missing and 27 failed: 29 CPU, 250 CNN, six matrix-profile tasks |

The seed channel names above are the zero-based names in the exported seed filenames. The detector sweep uses its own one-based CH1–CH16 display names.

The detector failures include shared job.json.tmp rename conflicts and SQLite disk-I/O errors. The latter do not establish a unique cause without the cluster logs; the earlier batch had a documented quota problem. Recovery uses isolated output/scratch directories, process-unique atomic JSON temporaries, lower CPU concurrency and explicit space management. Scientific specs, input arrays, detector settings, surrogate seeds and CNN checkpoints are unchanged.

The original 2 Hz return folders contain duplicated nested copies. The audit selected results by their matching specification hash and logical task; it did not count copied folders as new work. Of the 729 complete tasks, 280 are already imported on the PC and 449 have usable returned data ready for later import.

## Upload

Archive on the PC:

C:\Users\mmebr\Documents\CNN\DATA\derived\hpc\recovery_20261108_upload.tar.gz

PowerShell:

    scp "C:\Users\mmebr\Documents\CNN\DATA\derived\hpc\recovery_20261108_upload.tar.gz" s4699158@rangpur.compute.eait.uq.edu.au:~/

## Unpack, free verified backups, submit

On rangpur:

    cd ~/CNN
    tar -xzf ~/recovery_20261108_upload.tar.gz
    source ~/miniconda3/etc/profile.d/conda.sh
    conda activate aeon-env
    python DATA/derived/hpc/recovery_20261108/worker.py release
    python DATA/derived/hpc/recovery_20261108/worker.py release --apply
    quota -s
    bash DATA/derived/hpc/recovery_20261108/submit_all.sh

The release command checks the complete result file and every cached file against SHA-256 fingerprints of intact PC copies before deleting only that task's remote step_cache directory. It preserves result.json, scratch work, inputs, specifications and models. There are 334 such backed-up cache folders in the plan; changed, missing or unmatched folders are skipped. The dry run prints the space actually eligible on the cluster.

Submission refuses while older rq4n_, rq2x_1107_drop_ or rec1108_ jobs are queued/running. If older jobs are still active, let them finish before using this recovery plan. It does not cancel them. It checks input shapes, frozen CNN checkpoint hashes and the isolated runtime snapshot, then validates all five resource requests before submitting. No complete recordings or CNN weights are included; the files already used for the previous cluster rounds must still be present.

The five pack names are rec1108_seed, rec1108_cpu, rec1108_cnn, rec1108_mpA and rec1108_mpB. The scheduler decides concurrency:

- Seed: five channels in parallel; same checkpoint files, one-draw checkpoint intervals and a larger margin before the 20-minute wall.
- CPU: three tasks in parallel with eight reserved CPUs, scheduler-default memory, 20-minute chained jobs.
- CNN: four tasks in parallel, A100, 20-minute chained jobs; completed windows remain checkpointed.
- Matrix profile: two balanced packs, three tasks each, one task at a time per A100. These require the existing five-hour A100 requests because the exported profiles are not split into resumable intra-step blocks. A completed real-profile stage can be reused on a later submission for its surrogate.

Finished recovery tasks are skipped. A genuine task error stops its pack and names its log. Packs stop rather than accumulate over 8 GiB of recovery outputs; this guard is additional to checking the account quota. Up to 60 chained submissions are permitted. No wall-time completion estimate includes scheduler waiting.

## Monitor and collect

    squeue -u "$USER" -o "%.18i %.35j %.10T %.10M"
    python DATA/derived/hpc/recovery_20261108/worker.py status

Logs: ~/CNN/logs/rec1108_*.out and DATA/derived/hpc/recovery_20261108/logs/.

When status reports every task complete:

    python DATA/derived/hpc/recovery_20261108/worker.py collect

This writes the following archive and prints its SHA-256:

DATA/derived/hpc/recovery_20261108_return.tar.gz

Collection also works for a partial wave and reports the exact tasks still pending. Keep its remote task caches until the copied return archive is verified on the PC; the initial release manifest covers old PC-backed results only.

PowerShell on the PC:

    scp s4699158@rangpur.compute.eait.uq.edu.au:~/CNN/DATA/derived/hpc/recovery_20261108_return.tar.gz "C:\Users\mmebr\Documents\CNN\DATA\derived\hpc\"

After bringing that archive back, unpack it from the PC repository root and merge the recovered detector task folders into their original import locations:

    cd C:\Users\mmebr\Documents\CNN
    tar -xzf DATA/derived/hpc/recovery_20261108_return.tar.gz
    C:\ProgramData\anaconda3\python.exe DATA/derived/hpc/recovery_20261108/worker.py restore-rq4
    C:\ProgramData\anaconda3\python.exe DATA/derived/hpc/rq2_drop_transfer_20261107/worker.py collect --manifest DATA/derived/hpc/rq2_drop_transfer_20261107/manifest.json

The restore command checks specification hashes and preserves already complete originals. The original seed collector then requires all 64 channels complete, merges them and reports the frozen-cut and separately recalibrated comparisons. The detector results can subsequently be adopted through the existing Discovery import workflow; do not treat a partial sweep as a finished candidate/agreement census.

## Local validation

The archive was checked for safe relative paths, included task specifications and runtime files. PC checks verified array shapes and model/runtime hashes. A concurrency check exercised 200 shared-file JSON writes using eight writers. The corrected launch scripts were syntax-checked and their scheduling/chaining branches executed using mocks. Scientific computation is not rerun locally as part of this packaging check; live resource validation occurs on rangpur before submission.
