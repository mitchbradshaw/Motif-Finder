"""
test_window_matrix_artifact_name.py
====================================
fixup-aa item 3: a window matrix used to be written to
`wm_v1_<stem>_CH<n>_WIN<w>min_STEP<p>pct.npz` — no span, no recipe — so a run
and its own paired surrogate (runs 80/81 in the 2026-10-03 sandbox) registered
the SAME file and the second write replaced the first's matrix on disk.

The name now carries the span and a hash of the recipe prefix through the
window-matrix step (minus the two execution-only parameters, `resume_path` and
`timeout_s`, so an HPC resubmit chain — which bakes the path into the recipe
before the first job — still names one file). Existing names keep working: the
old call form is unchanged and the registry scanner reads both.

Run from the project root:
    /c/ProgramData/anaconda3/python.exe -m pytest tests/test_window_matrix_artifact_name.py -q
"""

import json
import os
import shutil
import sys
import tempfile

import numpy as np
import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from Adapters.registry import discover_adapters  # noqa: E402
from Working.database import queries as q  # noqa: E402
from Working.database import window_matrix_store as store  # noqa: E402
from Working.database.schema import init_db  # noqa: E402
from Working.recipes import make_recipe  # noqa: E402

discover_adapters()

N = 1200


@pytest.fixture
def env(monkeypatch):
    import Adapters.preprocessing_window_matrix as wm
    import Working.config as cfg
    tmp = tempfile.mkdtemp(prefix="aa_wm_")
    npy = os.path.join(tmp, "CH1.npy")
    np.save(npy, np.random.default_rng(0).standard_normal(N))
    db = os.path.join(tmp, "t.sqlite")
    conn = init_db(db)
    q.insert_recording(conn, "M2_aug_concat_fs1.mat", 1, 1.0, N, 0, npy)
    conn.close()
    monkeypatch.setattr(wm, "RESULTS_DIR", os.path.join(tmp, "wm"))
    monkeypatch.setattr(cfg, "STEP_CACHE_ROOT", os.path.join(tmp, "cache"))
    try:
        yield db, tmp
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _wm_step(**over):
    p = {"window_min": 1.0, "step_frac": 1.0, "catch22": False, "fast_entropy": True,
         "slow_entropy": False, "cnn": False, "rf": False}
    p.update(over)
    return {"stage": "preprocessing", "algorithm": "window_matrix", "params": p}


def _artifact_paths(db):
    conn = init_db(db)
    try:
        return [r[0] for r in conn.execute(
            "SELECT path FROM artifacts WHERE path LIKE '%wm_v1_%' ORDER BY id")]
    finally:
        conn.close()


def test_the_old_name_form_is_unchanged():
    assert store.artifact_name("M2_aug_concat_fs1", 1, 1.0, 1.0) == \
        "wm_v1_M2_aug_concat_fs1_CH1_WIN1min_STEP100pct"


def test_the_name_carries_the_span_and_the_prefix_key():
    name = store.artifact_name("M2_aug_concat_fs1", 1, 1.0, 1.0, span=(600, 1800), key="0123abcd")
    assert name == "wm_v1_M2_aug_concat_fs1_CH1_WIN1min_STEP100pct_span600-1800_0123abcd"


def test_the_key_ignores_the_execution_only_params():
    r1 = make_recipe(1, [_wm_step()], span=(0, N))
    r2 = make_recipe(1, [_wm_step(resume_path="Results/x.npz", timeout_s=600.0)], span=(0, N))
    r3 = make_recipe(1, [_wm_step(window_min=2.0)], span=(0, N))
    assert store.matrix_key(r1) == store.matrix_key(r2)
    assert store.matrix_key(r1) != store.matrix_key(r3)
    assert len(store.matrix_key(r1)) == 8


def test_a_run_its_surrogate_and_a_second_span_each_keep_their_own_file(env):
    """Acceptance 3: two spans of one channel, each paired with its surrogate,
    leave four distinct window-matrix files on disk."""
    from Working.run_groups import run_paired_recipe
    db, _ = env
    for span in ((0, 600), (600, 1200)):
        out = run_paired_recipe(make_recipe(1, [_wm_step()], span=span), db_path=db, force=True,
                                surrogate=True, surrogate_params={"method": "phase_randomize", "seed": 0})
        assert out["surrogate_run_id"] is not None
    paths = _artifact_paths(db)
    assert len(paths) == 4
    assert len(set(os.path.normcase(p) for p in paths)) == 4, paths
    assert all(os.path.isfile(p) for p in paths)
    assert sum("_span0-600_" in os.path.basename(p) for p in paths) == 2


def test_a_downstream_change_does_not_rename_the_matrix(env):
    """The key is the PREFIX through the window-matrix step: changing a later
    step must not write a second copy of the same matrix."""
    from Working.execution import execute_recipe
    db, _ = env
    base = [_wm_step(),
            {"stage": "catalogue", "algorithm": "cluster", "params": {"k": 2}}]
    execute_recipe(make_recipe(1, base, span=(0, N)), db_path=db, force=True)
    base[1]["params"]["k"] = 3
    execute_recipe(make_recipe(1, base, span=(0, N)), db_path=db, force=True)
    paths = _artifact_paths(db)
    assert len(set(os.path.normcase(p) for p in paths)) == 1, paths


def test_the_registry_scanner_reads_old_and_new_names():
    from Working.registration.kinds import _WM_NAME
    old = _WM_NAME.match("wm_v1_M2_aug_concat_fs1_CH1_WIN1min_STEP100pct.npz")
    new = _WM_NAME.match("wm_v1_M2_aug_concat_fs1_CH1_WIN1min_STEP100pct_span600-1800_0123abcd.npz")
    assert old and old.group("stem") == "M2_aug_concat_fs1" and old.group("ch") == "1"
    assert new and new.group("stem") == "M2_aug_concat_fs1" and new.group("ch") == "1"
    assert new.group("a") == "600" and new.group("b") == "1800"


def test_an_hpc_export_names_the_file_the_run_will_write(env, tmp_path):
    """The resubmit chain bakes `resume_path` in before job 1 runs; that path
    must be the one `persist` writes, or job 2 resumes from nothing."""
    from Working.hpc.job_export import export_wm_job
    db, _ = env
    conn = init_db(db)
    try:
        out = export_wm_job(conn, 1, 1.0, span=(0, 600), out_dir=str(tmp_path), stages=("fast_entropy",))
    finally:
        conn.close()
    with open(out["recipe_path"], encoding="utf-8") as f:
        recipe = json.load(f)
    key = store.matrix_key(recipe)
    assert os.path.basename(out["artifact_path"]).endswith(f"_span0-600_{key}.npz")
    assert recipe["steps"][0]["params"]["resume_path"].endswith(f"_span0-600_{key}.npz")
