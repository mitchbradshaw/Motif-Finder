"""
test_hpc_job_dependencies.py
============================
The researcher's request of 2026-10-07: every generated SLURM script says, in
its own comments, **everything it needs on the cluster** — the code modules
the job imports, the input files, the output it writes — so the transfer by
WinSCP can be done from the script alone, without guessing.

`Working.hpc.job_export.repo_module_closure` walks the imports of an entry
module through the repo's own packages (`Working`, `Adapters`, `Pipelines`)
and names the files; `dependency_block` renders them as a comment block the
exporters put under the `#SBATCH` lines.
"""

import os
import sys
import tempfile

import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (PROJECT_ROOT, os.path.join(PROJECT_ROOT, "tests")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from Working.hpc import job_export  # noqa: E402
from test_job_export_paths import CPU_RECIPE  # noqa: E402


def test_the_closure_of_the_seed_job_names_its_repo_modules():
    files = job_export.repo_module_closure("Working.discovery.seed_job")
    assert "Working/discovery/seed_job.py" in files
    assert "Working/discovery/seeded_search.py" in files
    assert "Adapters/detection_seed_matches.py" in files, "imported inside a function, still needed"
    assert "Adapters/preprocessing_surrogate.py" in files, "every adapter: the registry imports them all"
    assert "Working/database/schema.py" in files
    for f in files:
        assert "\\" not in f and not os.path.isabs(f), f
        assert os.path.isfile(os.path.join(PROJECT_ROOT, f)), f
    assert not any(f.startswith(("webui", "tests")) for f in files), "the bridge and the tests are not the job's"


def test_the_dependency_block_is_a_comment_with_three_lists():
    block = job_export.dependency_block(
        code=["Working/a.py", "Adapters/b.py"], inputs=["DATA/derived/channels/x/CH0.npy", "HPC/x.spec.json"],
        outputs=["HPC/x.result.json"], env="aeon-env")
    lines = block.splitlines()
    assert all(line.startswith("#") for line in lines if line.strip())
    assert "DATA/derived/channels/x/CH0.npy" in block and "HPC/x.result.json" in block
    assert block.index("Working/a.py") < block.index("DATA/derived") < block.index("HPC/x.result.json")
    assert "aeon-env" in block


@pytest.fixture
def in_repo_dir():
    d = tempfile.mkdtemp(prefix="deps_slurm_", dir=os.path.join(PROJECT_ROOT, "webui"))
    yield d
    import shutil
    shutil.rmtree(d, ignore_errors=True)


def test_a_chain_script_lists_the_runner_the_adapters_the_recipe_and_the_data(in_repo_dir):
    res = job_export.export_job(CPU_RECIPE, out_dir=in_repo_dir, base_name="dep", job_name="dep", est_seconds=60,
                                data_files=["DATA/db/annotations.sqlite", "DATA/derived/channels/syn/CH2.npy"])
    with open(res["script_path"], encoding="utf-8") as f:
        s = f.read()
    head, body = s.split("mkdir -p logs", 1)
    assert "needs on the cluster" in head
    assert "Pipelines/run_recipe/run_recipe.py" in head
    assert "Adapters/preprocessing_window_matrix.py" in head and "Adapters/catalogue_cluster.py" in head
    assert job_export.repo_relative(res["recipe_path"]) in head
    assert "DATA/db/annotations.sqlite" in head and "DATA/derived/channels/syn/CH2.npy" in head
    assert res["dependencies"]["inputs"][0] == job_export.repo_relative(res["recipe_path"])
