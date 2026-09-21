# HPC/results/ — where a cluster job's output lands before it is registered

One directory per job, named as the job was (`Working/hpc/job_export.py` names them
`<kind>_<stem>_CH<n>_WIN<len>min_<hash8>`):

    HPC/results/<job>/
        <job>.json          the recipe the job ran (the JSON job_export wrote next to the .sh)
        mp_v2_*.npz         the artifacts the job produced, under their conventional names
        wm_v1_*.npz
        manifest.json       optional: written by Pipelines/run_recipe on the cluster (Working/manifest.py)

Drop the bundle here (`scp`, or the pull action on Settings › Storage & backups once it exists), then
Settings › Storage & backups › HPC results › scan, or `POST /api/registry/hpc_result/register`. The
checks are the ones Jobs › Upload shows (spec P24): the recipe parses and hashes, its recording is
registered, every artifact's per-channel shape matches the recording, `len(mp) == span − m + 1`, no NaN.
A recipe hash that matches a paused run is reported (`paused_run_id`); continuing the run is the job
model's step (Prompt 01). See `docs/DATA_REGISTRATION.md`.

Everything under this directory except this README is gitignored: results are bulk data.
