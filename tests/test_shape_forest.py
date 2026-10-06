"""
test_shape_forest.py
====================
fixup-ag seam (iii): the forest on the CLUSTER categories — arm **B.2 cluster
labels · trace shape** (`Working.training.shape_forest`).

Decided (the researcher, 2026-10-06), pinned here:

* the model is trained on the ORIGINAL RAW signal of each window — features
  measured on the raw samples at the window's re-cut bounds; centring decides
  WHICH samples a window covers, detrend and normalise exist only to compare
  shapes for clustering. A window's training features are therefore unchanged by
  the detrend option. The recipe says so, so the CNN arm (`AI`) inherits it;
* the forest learns the cluster of every TRAINING window (sampled and assigned);
  validation, test and exam windows are assigned only by the trained model;
* the pool is unlabelled, so there is no arm A; the results keep the shape `AH`
  reads — exams (i) later block and (ii) unseen channels, per-cluster predictions
  on the test and exam windows (on disk, by path), the mapping — and the
  yardstick-(B) row says "not yet labelled";
* how well the forest reproduces the clustering on held-back training windows is
  a DIAGNOSTIC, labelled as one, never a result;
* the cut and the mapping are frozen once a run on the pool has a test score
  (`store.CutFrozen`), with the run named.

Run from the project root:
    /c/ProgramData/anaconda3/python.exe -m pytest tests/test_shape_forest.py -q
"""

import json
import os
import shutil
import sys

import numpy as np
import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from Working.database import queries as q  # noqa: E402
from Working.database.schema import init_db  # noqa: E402

AUG = "syn_aug_concat_fs1.mat"
PLAIN = "syn_concat_fs1.mat"
K = 3


def _sf():
    from Working.training import shape_forest
    return shape_forest


def _add_recording(conn, tmp, source, n, seed=0):
    d = os.path.join(tmp, "channels", os.path.splitext(source)[0])
    os.makedirs(d, exist_ok=True)
    for ch in range(16):
        rng = np.random.default_rng(seed + ch)
        t = np.arange(int(n))
        x = (0.01 * rng.standard_normal(int(n)) + 0.3 * (t / n)
             - 0.5 * np.exp(-(((t - 777) % 2400) / 15.0) ** 2) + 0.4 * np.exp(-(((t - 1900) % 3100) / 40.0) ** 2))
        npy = os.path.join(d, f"CH{ch}.npy")
        np.save(npy, x)
        rid = q.insert_recording(conn, source, ch, 1.0, int(n), 0, npy)
        conn.execute("UPDATE recordings SET units = 'V' WHERE id = ?", (rid,))
    conn.commit()


@pytest.fixture(scope="module")
def _built(tmp_path_factory):
    from Working.training import pool as tpool
    from Working.training import shape as sh
    from Working.training import store as ts
    tmp = tmp_path_factory.mktemp("forest")
    conn = init_db(str(tmp / "t.sqlite"))
    _add_recording(conn, str(tmp), AUG, 36_000, seed=0)
    _add_recording(conn, str(tmp), PLAIN, 18_000, seed=100)
    ids = []
    for src in (AUG, PLAIN):
        for scale in (1, 10, 30):
            u = tpool.build_unlabelled_set(conn, src, scale_min=scale)
            ids.append(ts.save_window_set(conn, u, str(tmp / "window_sets"), f"ws_{os.path.splitext(src)[0]}_{scale}min"))
    plan = tpool.plan_for(conn, [AUG, PLAIN], hold_out_pack="D")
    pool = tpool.combine(conn, ids, plan, sample={1: 300, 10: 300, 30: 300}, seed=0)
    pid = tpool.save_pool(conn, pool, str(tmp / "window_sets"), "pool_test")
    shapes = sh.trace_shapes(conn, sh.pool_frame(sh.pool_windowset(pool)))
    tree = sh.cluster_shapes(shapes, sample=200, seed=0)
    tree.save(str(tmp / "trees" / tree.meta["key"]))
    conn.close()
    return {"db": tmp / "t.sqlite", "pool_id": pid, "pool": pool, "tree_root": tmp / "trees", "tmp": tmp}


@pytest.fixture
def env(_built, tmp_path):
    shutil.copyfile(_built["db"], tmp_path / "t.sqlite")
    conn = init_db(str(tmp_path / "t.sqlite"))
    yield conn, _built, tmp_path
    conn.close()


def _mapping(k=K):
    return {"k": k, "clusters": {str(c): {"name": f"p{c}", "class": "interesting" if c == 1 else "not_interesting"}
                                 for c in range(1, k + 1)}}


def _recipe(conn, built, k=K, mapping=None):
    sf = _sf()
    from Working.training import pool as tpool
    row, pool = tpool.load_pool(conn, built["pool_id"])
    steps = [{"stage": "preprocessing", "algorithm": "window_pool", "params": {"pool": str(built["pool_id"])}},
             {"stage": "preprocessing", "algorithm": "trace_shape", "params": {}},
             {"stage": "catalogue", "algorithm": "shape_cluster",
              "params": {"sample": 200, "seed": 0, "k": k, "mapping": json.dumps(mapping or _mapping(k))}}]
    return sf.make_recipe({"id": int(row["id"]), "name": row["name"], "version": int(row["version"]), "key": pool.key},
                          {"id": 7, "name": "shape_clusters", "steps": steps}, n_estimators=40)


# ── the raw-input rule ──────────────────────────────────────────────────────

def test_training_features_are_measured_on_the_raw_samples_at_the_recut_bounds_and_ignore_detrend(env):
    conn, built, _tmp = env
    sf = _sf()
    from Working.training import shape as sh
    from Working.Preprocessing.window_matrix.build import features_at
    frame = sh.pool_frame(sh.pool_windowset(built["pool"]))
    off = sh.trace_shapes(conn, frame, align="centre", detrend="off")
    lin = sh.trace_shapes(conn, frame, align="centre", detrend="linear")
    assert list(off.frame["start"]) == list(lin.frame["start"])
    f_off = sf.raw_features(conn, off.frame)
    f_lin = sf.raw_features(conn, lin.frame)
    assert list(f_off.columns) == list(f_lin.columns)
    assert np.allclose(f_off.to_numpy(), f_lin.to_numpy(), equal_nan=True)
    # and they ARE the window-matrix measures of the raw samples at the re-cut start
    row = off.frame.iloc[5]
    npy = conn.execute("SELECT npy_path FROM recordings WHERE id = ?", (int(row["recording_id"]),)).fetchone()[0]
    vals, _computed, cols = features_at(np.load(npy, mmap_mode="r"), [int(row["start"])], int(row["length"]), sf.DEFAULT_STAGES)
    assert list(cols) == list(f_off.columns)
    assert np.allclose(f_off.iloc[5].to_numpy(dtype=float), vals[0].astype(float), equal_nan=True)


def test_the_recipe_carries_the_raw_input_rule_for_the_cnn_arm_too(env):
    conn, built, _tmp = env
    sf = _sf()
    r = _recipe(conn, built)
    assert r["kind"] == sf.RECIPE_KIND and r["arm"]["label"] == "B.2 cluster labels · trace shape"
    rule = r["inputs"]["rule"]
    assert "raw" in rule and "CNN" in rule and "detrend" in rule
    assert r["inputs"]["features"] == "raw samples at the re-cut bounds"
    assert r["arm"]["k"] == K and r["arm"]["mapping"]["clusters"]["1"]["class"] == "interesting"


def test_the_mapping_must_cover_every_cluster_at_the_cut(env):
    conn, built, _tmp = env
    sf = _sf()
    bad = _mapping()
    del bad["clusters"]["2"]
    with pytest.raises(ValueError, match="map"):
        sf.make_recipe({"id": 1, "name": "p", "version": 1, "key": "x"},
                       {"id": 1, "name": "t", "steps": _recipe(conn, built)["template"]["steps"][:2] + [
                           {"stage": "catalogue", "algorithm": "shape_cluster",
                            "params": {"k": K, "mapping": json.dumps(bad)}}]})


# ── the run ─────────────────────────────────────────────────────────────────

def test_the_forest_learns_the_training_clusters_and_only_predicts_the_rest(env):
    conn, built, tmp = env
    sf = _sf()
    res = sf.run_forest(conn, _recipe(conn, built), tree_root=str(built["tree_root"]), out_dir=str(tmp / "run"))
    assert res["arm"]["label"] == "B.2 cluster labels · trace shape" and res["arm"]["k"] == K
    assert res["mapping"]["clusters"]["1"]["class"] == "interesting"
    assert res["training"]["n_train"] > 0 and set(res["training"]["cluster_sizes"]) == {"1", "2", "3"}
    d = res["diagnostic"]
    assert d["kind"] == "diagnostic" and "not a result" in d["note"]
    assert 0.0 <= d["accuracy"] <= 1.0 and d["n_held_back"] > 0
    for e in (sf.EXAM_I, sf.EXAM_II):
        ex = res["exams"][e]
        assert ex["status"] == "predicted · not yet labelled" and ex["n"] > 0
        assert sum(ex["by_cluster"].values()) == ex["n"]
        assert sum(ex["by_class"].values()) == ex["n"]
    assert res["yardstick_B"]["status"] == "not yet labelled"
    assert "raw" in res["inputs"]["rule"]
    import pandas as pd
    p = pd.read_parquet(res["predictions_path"])
    assert set(p["role"]) <= {"validation", "test", "exam"} and "train" not in set(p["role"])
    assert {"recording_id", "channel", "start", "length", "orig_start", "scale_min", "cluster", "class",
            "p_interesting"} <= set(p.columns)
    assert os.path.isfile(res["model_path"])


def test_a_run_is_recorded_and_listed(env):
    conn, built, tmp = env
    sf = _sf()
    out = sf.run_and_record(conn, _recipe(conn, built), str(tmp / "training"), tree_root=str(built["tree_root"]))
    kinds = {r[0] for r in conn.execute("SELECT kind FROM artifacts WHERE run_id = ?", (out["run_id"],))}
    assert {"other", "model"} <= kinds
    runs = sf.list_runs(conn)
    assert runs[0]["run_id"] == out["run_id"] and runs[0]["status"] == "completed"
    assert runs[0]["k"] == K and runs[0]["pool"]["id"] == built["pool_id"] and runs[0]["scored"] is False


def test_the_cut_and_mapping_freeze_once_a_run_on_the_pool_has_a_test_score(env):
    conn, built, tmp = env
    sf = _sf()
    from Working.training.store import CutFrozen
    out = sf.run_and_record(conn, _recipe(conn, built), str(tmp / "training"), tree_root=str(built["tree_root"]))
    key = built["pool"].key
    assert sf.frozen_for(conn, key) is None          # predicted, not scored: nothing frozen yet
    sf.check_frozen(conn, key, K + 1, _mapping(K + 1))
    # AH scores exam (i): from now on the cut and the mapping are fixed
    with open(out["results_path"], encoding="utf-8") as f:
        res = json.load(f)
    res["exams"][sf.EXAM_I]["status"] = "scored"
    with open(out["results_path"], "w", encoding="utf-8") as f:
        json.dump(res, f)
    fz = sf.frozen_for(conn, key)
    assert fz["run_id"] == out["run_id"] and fz["k"] == K
    sf.check_frozen(conn, key, K, _mapping(K))        # the same cut and mapping: fine
    with pytest.raises(CutFrozen, match=f"run {out['run_id']}"):
        sf.check_frozen(conn, key, K + 1, _mapping(K + 1))
    flipped = _mapping(K)
    flipped["clusters"]["2"]["class"] = "interesting"
    with pytest.raises(CutFrozen, match="mapping"):
        sf.check_frozen(conn, key, K, flipped)
    with pytest.raises(CutFrozen):
        sf.run_and_record(conn, _recipe(conn, built, k=K + 1), str(tmp / "training"), tree_root=str(built["tree_root"]))


def test_the_pool_key_rides_on_the_windows_so_analyse_can_find_the_freeze(env):
    _conn, built, _tmp = env
    from Working.training import shape as sh
    ws = sh.pool_windowset(built["pool"])
    assert sh.pool_frame(ws)["pool_key"].iloc[0] == built["pool"].key


def test_shape_forest_imports_no_ui_library():
    import ast
    import Working.training.shape_forest as m
    with open(m.__file__, encoding="utf-8") as f:
        tree = ast.parse(f.read())
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module.split(".")[0])
    assert not names & {"panel", "holoviews", "bokeh", "fastapi", "uvicorn", "matplotlib"}
