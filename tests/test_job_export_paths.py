"""
test_job_export_paths.py
========================
fixup-ab item 5: the SLURM script the bridge writes would not have run on the
cluster (measured 2026-10-02/03, `docs/prompts/fixup/AB-models-paired-job.md`):

* Discovery's `/slurm` handed `export_job` an ABSOLUTE `out_dir` (the sandbox's
  `webui/runtime/<stamp>/hpc`), and the exporter baked it verbatim — a
  `C:/Users/.../x.json` path under a `--chdir=/home/.../CNN`. The baked paths
  must be repo-relative whatever the caller passes; a directory outside the
  repo cannot be synced to the same place and is refused.
* the generic template asked for `--gres=gpu:a100`, CUDA and the GPU conda env
  for every recipe — a CPU clustering included. A recipe with no CNN step gets
  the CPU partition, no GRES, no CUDA module and the CPU environment.
* the paired training job has its own export: a CPU job running
  `python -m Working.training run`.
"""

import os
import sys
import tempfile

import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from Working.config import HPC_CONDA_ENV_CPU, HPC_CONDA_ENV_GPU, HPC_CPU_PARTITION, HPC_GPU_PARTITION  # noqa: E402

CPU_RECIPE = {"recording_id": 1, "span": [0, 3600], "steps": [
    {"stage": "preprocessing", "algorithm": "window_matrix",
     "params": {"window_min": 1.0, "catch22": True, "fast_entropy": True, "cnn": False, "rf": False}},
    {"stage": "catalogue", "algorithm": "cluster", "params": {"k": 3}}],
    "fan_out": {"kind": "channels", "targets": [2, 6, 7]}}
GPU_RECIPE = {"recording_id": 1, "span": [0, 3600], "steps": [
    {"stage": "preprocessing", "algorithm": "window_matrix",
     "params": {"window_min": 10.0, "catch22": True, "cnn": True}}]}


@pytest.fixture
def in_repo_dir():
    d = tempfile.mkdtemp(prefix="ab_slurm_", dir=os.path.join(PROJECT_ROOT, "webui"))
    yield d
    import shutil
    shutil.rmtree(d, ignore_errors=True)


def _script(res):
    with open(res["script_path"], encoding="utf-8") as f:
        return f.read()


def test_an_absolute_out_dir_inside_the_repo_is_baked_repo_relative(in_repo_dir):
    from Working.hpc.job_export import export_job
    res = export_job(CPU_RECIPE, out_dir=in_repo_dir, base_name="cluster_k3", job_name="cluster_k3", est_seconds=60)
    s = _script(res)
    rel = os.path.relpath(in_repo_dir, PROJECT_ROOT).replace(os.sep, "/")
    assert f"{rel}/cluster_k3.json" in s
    assert PROJECT_ROOT.replace(os.sep, "/") not in s and ":/" not in s.replace("#!/bin/bash", "")
    assert "\\" not in s.split("<<'PY'")[0], "no Windows separators in the baked paths"
    assert res["sbatch_command"] == f"sbatch {rel}/cluster_k3.sh"


def test_an_out_dir_outside_the_repo_says_it_will_not_resolve_on_the_cluster():
    from Working.hpc.job_export import export_job
    outside = tempfile.mkdtemp(prefix="ab_outside_")
    res = export_job(CPU_RECIPE, out_dir=outside, base_name="x", job_name="x", est_seconds=60)
    assert res["warnings"] and "outside the repo" in res["warnings"][0]


def test_an_out_dir_inside_the_repo_carries_no_warning(in_repo_dir):
    from Working.hpc.job_export import export_job
    assert export_job(CPU_RECIPE, out_dir=in_repo_dir, base_name="w", job_name="w", est_seconds=60)["warnings"] == []


def test_a_cpu_recipe_asks_for_the_cpu_partition_and_no_gpu(in_repo_dir):
    from Working.hpc.job_export import export_job
    s = _script(export_job(CPU_RECIPE, out_dir=in_repo_dir, base_name="c", job_name="c", est_seconds=60))
    assert f"--partition={HPC_CPU_PARTITION}" in s
    assert "--gres" not in s and "module load cuda" not in s
    assert f"conda activate {HPC_CONDA_ENV_CPU}" in s
    assert "#SBATCH --array=0-2" in s


def test_a_cnn_recipe_still_asks_for_the_gpu(in_repo_dir):
    from Working.hpc.job_export import export_job
    s = _script(export_job(GPU_RECIPE, out_dir=in_repo_dir, base_name="g", job_name="g", est_seconds=60))
    assert f"--partition={HPC_GPU_PARTITION}" in s and "--gres=gpu:a100" in s
    assert f"conda activate {HPC_CONDA_ENV_GPU}" in s


def test_the_paired_training_job_exports_as_a_cpu_job(in_repo_dir):
    from Working.hpc.job_export import export_training_job
    recipe = {"kind": "paired_training", "window_set": {"name": "ws", "key": "k"}, "arms": {}}
    res = export_training_job(recipe, out_dir=in_repo_dir, base_name="paired_ab", est_seconds=9000,
                              db_repo_path="DATA/db/annotations.sqlite", root_repo_path="DATA/derived/training")
    s = _script(res)
    rel = os.path.relpath(in_repo_dir, PROJECT_ROOT).replace(os.sep, "/")
    assert f"python -m Working.training run --db DATA/db/annotations.sqlite --root DATA/derived/training " \
           f"--recipe {rel}/paired_ab.json" in s
    assert f"--partition={HPC_CPU_PARTITION}" in s and "--gres" not in s
    assert "\r\n" not in open(res["script_path"], "rb").read().decode("utf-8")
