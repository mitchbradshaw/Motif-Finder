"""
test_job_export_cnn.py
======================
fixup-AI: the two SLURM scripts the site writes for RQ1 version 2 (B.2), from a
job directory the core exported (`Working.training.shape_cnn.export_job`,
`Working.training.full_ward.export_job`):

* **the CNN arm** — the GPU partition with its GRES, CUDA, the torch
  environment, repo-relative paths (`AB`'s rule), LF endings, the estimate
  labelled as one, RESUMABLE: the run stops before the wall clock (`--deadline-min`),
  a status exit code decides the resubmit (never a grep), a cap on the chain;
  the label-shuffle null (5 full trainings) as an ARRAY job in its own script,
  written only when asked (off by default), its cost stated;
* **Ward over every training window** — a CPU, high-memory job: the partition,
  `--mem` sized from the window count (two copies of the condensed distances),
  the CPU environment, the same Ward, the same tree artifact.

Run from the project root:
    /c/ProgramData/anaconda3/python.exe -m pytest tests/test_job_export_cnn.py -q
"""

import json
import os
import re
import shutil
import sys
import tempfile

import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from Working.config import (HPC_CONDA_ENV_CPU, HPC_CONDA_ENV_GPU, HPC_GPU_PARTITION,  # noqa: E402
                            HPC_MAX_WALLTIME_MINUTES, HPC_REMOTE_REPO_ROOT)


@pytest.fixture
def job_dir():
    d = tempfile.mkdtemp(prefix="ai_slurm_", dir=os.path.join(PROJECT_ROOT, "webui"))
    with open(os.path.join(d, "job.json"), "w", encoding="utf-8") as f:
        json.dump({"kind": "shape_cluster_cnn", "recipe_hash": "abcd1234", "encoding": "fusion"}, f)
    yield d
    shutil.rmtree(d, ignore_errors=True)


def _read(p):
    with open(p, "rb") as f:
        raw = f.read()
    assert b"\r\n" not in raw, "sbatch refuses DOS line breaks"
    return raw.decode("utf-8")


def test_the_cnn_script_asks_for_a_gpu_and_is_resumable(job_dir):
    from Working.hpc.job_export import export_cnn_job
    res = export_cnn_job(job_dir, base_name="b2cnn_fusion_abcd1234", est_seconds=3 * 3600)
    s = _read(res["script_path"])
    rel = os.path.relpath(job_dir, PROJECT_ROOT).replace(os.sep, "/")
    assert "#SBATCH --gres=gpu:a100" in s and f"#SBATCH --partition={HPC_GPU_PARTITION}" in s
    assert "module load cuda" in s and f"conda activate {HPC_CONDA_ENV_GPU}" in s
    assert f"#SBATCH --chdir={HPC_REMOTE_REPO_ROOT}" in s
    assert f"python -m Working.training cnn-run --job {rel}" in s
    assert f"python -m Working.training cnn-status --job {rel}" in s
    assert PROJECT_ROOT.replace(os.sep, "/") not in s and ":/" not in s.replace("#!/bin/bash", "")
    # the wall clock is the account's ceiling; the run stops before it, checkpointed, and the chain resubmits
    m = re.search(r"#SBATCH --time=(\d+):(\d+):00", s)
    assert m and int(m.group(1)) * 60 + int(m.group(2)) <= HPC_MAX_WALLTIME_MINUTES
    dl = re.search(r"--deadline-min (\d+(?:\.\d+)?)", s)
    assert dl and float(dl.group(1)) < int(m.group(1)) * 60 + int(m.group(2))
    assert "STATUS=$?" in s and "MAX_CHAIN=" in s and f"sbatch {rel}/b2cnn_fusion_abcd1234.sh" in s
    assert "grep" not in s
    # the environment is checked before an hour is spent
    assert "import torch" in s and "torchvision" in s and "skimage" in s
    # the estimate is said to be one
    assert res["slurm_time"] and res["estimate_note"] and "estimate" in res["estimate_note"].lower()
    assert res["chain_jobs"] >= 1
    assert res["null_script_path"] is None                         # the null is off by default


def test_the_label_shuffle_null_is_an_array_job_of_five_full_trainings_when_asked(job_dir):
    from Working.hpc.job_export import export_cnn_job
    res = export_cnn_job(job_dir, base_name="b2cnn_fusion_abcd1234", est_seconds=3600, null_shuffles=5,
                         train_seconds=1800)
    s = _read(res["null_script_path"])
    rel = os.path.relpath(job_dir, PROJECT_ROOT).replace(os.sep, "/")
    assert "#SBATCH --array=0-4" in s and "#SBATCH --gres=gpu:a100" in s
    assert f"python -m Working.training cnn-null --job {rel} --shuffle $SLURM_ARRAY_TASK_ID" in s
    assert "sbatch --array=$SLURM_ARRAY_TASK_ID" in s                   # a task resumes itself
    assert res["null"]["n"] == 5 and res["null"]["gpu_hours"] == pytest.approx(5 * 1800 / 3600)
    assert "full training" in res["null"]["note"]


def test_the_ward_script_is_a_cpu_high_memory_job_sized_from_the_window_count(job_dir):
    from Working.hpc.job_export import export_ward_job
    res = export_ward_job(job_dir, base_name="ward_full_pool", n=60_000, est_seconds=600)
    s = _read(res["script_path"])
    rel = os.path.relpath(job_dir, PROJECT_ROOT).replace(os.sep, "/")
    assert "--gres" not in s and "module load cuda" not in s
    assert f"conda activate {HPC_CONDA_ENV_CPU}" in s
    m = re.search(r"#SBATCH --mem=(\d+)G", s)
    assert m and int(m.group(1)) == res["memory"]["request_gb"]
    # two copies of n(n-1)/2 float64 distances at 60,000 windows is ~28.8 GB: the request covers it
    assert int(m.group(1)) >= 27
    assert re.search(r"#SBATCH --partition=\S+", s)
    assert f"python -m Working.training ward-run --job {rel}" in s
    assert res["memory"]["rule"] and "8" in res["memory"]["rule"]
