"""
test_shape_chain.py
===================
fixup-ag: the RQ1 version-2 workflow as Analyse chain blocks —
*Window pool* → *Trace shape* → *Shape clustering* (ticket
`docs/prompts/fixup/AG-…`, "What to build" 1–3).

* *Window pool* is a chain SOURCE: a chain may start from saved window sets in
  place of a span (`AA`'s "§6.9 frame 0b — a validator change"). It may only be
  step 01, and the validator says so. It combines through `AF`'s
  `Working.training.pool.combine` — no second implementation — with an EQUAL
  number of windows per scale by default (the researcher: 20,000 each), and the
  pool it built is a saved `window_sets` row, re-used (not duplicated) when the
  same pool is built again, and re-openable as the source;
* *Trace shape*: WindowSet → WindowSet, the Library's resample + z-normalise,
  windows under the noise floor left out by default and counted; the vectors on
  disk by path (rule 4);
* *Shape clustering*: WindowSet → Grouping, the Library's Ward on a seeded sample
  of training windows, the rest assigned, the tree kept as an artifact; windows
  that are not training windows carry no cluster (-1).

Run from the project root:
    /c/ProgramData/anaconda3/python.exe -m pytest tests/test_shape_chain.py -q
"""

import json
import os
import sys

import numpy as np
import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from Adapters.registry import discover_adapters, get_adapter  # noqa: E402
from Working.database import queries as q  # noqa: E402
from Working.database.schema import init_db  # noqa: E402

AUG = "syn_aug_concat_fs1.mat"
PLAIN = "syn_concat_fs1.mat"

POOL = {"stage": "preprocessing", "algorithm": "window_pool"}
SHAPE = {"stage": "preprocessing", "algorithm": "trace_shape"}
CLUSTER = {"stage": "catalogue", "algorithm": "shape_cluster"}


def _add_recording(conn, tmp, source, n, seed=0):
    d = os.path.join(tmp, "channels", os.path.splitext(source)[0])
    os.makedirs(d, exist_ok=True)
    for ch in range(16):
        x = 0.05 * np.random.default_rng(seed + ch).standard_normal(int(n))
        npy = os.path.join(d, f"CH{ch}.npy")
        np.save(npy, x)
        rid = q.insert_recording(conn, source, ch, 1.0, int(n), 0, npy)
        conn.execute("UPDATE recordings SET units = 'V' WHERE id = ?", (rid,))
    conn.commit()


@pytest.fixture
def chain_store(tmp_path, monkeypatch):
    db = str(tmp_path / "t.sqlite")
    conn = init_db(db)
    _add_recording(conn, str(tmp_path), AUG, 36_000, seed=0)
    _add_recording(conn, str(tmp_path), PLAIN, 18_000, seed=100)
    from Working.training import pool as tpool
    from Working.training import store as ts
    ids = []
    for src in (AUG, PLAIN):
        for scale in (1, 10, 30):
            u = tpool.build_unlabelled_set(conn, src, scale_min=scale)
            ids.append(ts.save_window_set(conn, u, str(tmp_path / "window_sets"),
                                          f"ws_{os.path.splitext(src)[0]}_{scale}min"))
    rid = conn.execute("SELECT id FROM recordings WHERE source_file = ? AND channel = 0", (AUG,)).fetchone()[0]
    conn.close()
    # every path the three blocks write is redirected into the test's own directory
    import Working.config as cfg
    import Adapters.preprocessing_window_pool as wp
    import Adapters.preprocessing_trace_shape as tsh
    import Adapters.catalogue_shape_cluster as csc
    monkeypatch.setattr(cfg, "STEP_CACHE_ROOT", str(tmp_path / "step_cache"))
    monkeypatch.setattr(wp, "POOL_ROOT", str(tmp_path / "pools"))
    monkeypatch.setattr(tsh, "RESULTS_DIR", str(tmp_path / "shapes"))
    monkeypatch.setattr(csc, "RESULTS_DIR", str(tmp_path / "trees"))
    return db, ids, rid, tmp_path


def _recipe(rid, steps):
    from Working.recipes import make_recipe
    return make_recipe(rid, steps, span=(0, 1))


def _steps(sets, per_scale=200, sample=150, k=3):
    return [dict(POOL, params={"window_sets": ",".join(str(i) for i in sets), "per_scale": per_scale}),
            dict(SHAPE, params={}),
            dict(CLUSTER, params={"sample": sample, "k": k})]


# ── the blocks ──────────────────────────────────────────────────────────────

def test_the_three_blocks_are_registered_with_their_signatures():
    discover_adapters()
    pool, shape, clus = (get_adapter("preprocessing.window_pool"), get_adapter("preprocessing.trace_shape"),
                         get_adapter("catalogue.shape_cluster"))
    assert (pool.input_kind, pool.output_kind, pool.source) == ("signal", "windowset", True)
    assert (shape.input_kind, shape.output_kind, shape.source) == ("windowset", "windowset", False)
    assert (clus.input_kind, clus.output_kind, clus.source) == ("windowset", "grouping", False)
    p = {s.name: s for s in pool.params}
    # the researcher's mix (2026-10-05): an equal number of windows per scale, 20,000 each, one seeded setting
    assert p["per_scale"].default == 20000 and p["seed"].default == 0
    assert p["rule"].default == "within_scale" and set(p["rule"].choices) == {"within_scale", "no_overlap"}
    from Working.library.grouping.methods import ward
    assert {s.name: s for s in shape.params}["resample_length"].default == ward.RESAMPLE_LENGTH
    assert {s.name: s for s in shape.params}["noise_floor"].default is True
    assert {s.name: s for s in clus.params}["sample"].default == 20000


def test_a_source_block_may_only_be_step_01_and_the_validator_says_so():
    from Working.chain_validation import validate_recipe_steps
    ok, _ = validate_recipe_steps([POOL, SHAPE, CLUSTER])
    assert ok
    ok, reason = validate_recipe_steps([{"stage": "preprocessing", "algorithm": "detrend"}, POOL])
    assert not ok and "source" in reason and "01" in reason


def test_the_chain_runs_from_saved_window_sets_through_shape_to_a_kept_tree(chain_store):
    from Working.execution import execute_recipe
    db, ids, rid, tmp = chain_store
    seen = {}
    out = execute_recipe(_recipe(rid, _steps(ids)), db_path=db, force=True,
                         on_step_result=lambda i, r: seen.__setitem__(i, r))
    pool_r, shape_r, clus_r = seen[0], seen[1], seen[2]
    # the pool: AF's combine, an equal number per scale, saved as a window_sets row
    pm = pool_r.meta["pool"]
    assert pm["by_scale"] == {"1": 200, "10": 200, "30": 200}
    assert pm["window_set_id"] and pm["saved"] in ("saved", "reused")
    conn = init_db(db)
    try:
        row = conn.execute("SELECT * FROM window_sets WHERE id = ?", (pm["window_set_id"],)).fetchone()
        assert json.loads(row["coverage_json"])["set_kind"] == "pool"
        assert row["recipe_hash"] == pm["key"]
        n_rows = conn.execute("SELECT COUNT(*) FROM window_sets").fetchone()[0]
    finally:
        conn.close()
    # the shape step: the Library's length, the floor counted (nothing is under it here)
    assert shape_r.meta["under_floor"]["n"] == 0 and shape_r.meta["noise_floor"] is True
    assert os.path.isfile(shape_r.meta["shape_file"])
    # the cluster step: training windows only, clustered N + assigned M, tree on disk
    labels = np.asarray(clus_r.value.labels)
    roles = shape_r.value.features["pool_role"].to_numpy()
    assert (labels[roles != "train"] == -1).all() and (labels[roles == "train"] >= 1).all()
    tm = clus_r.meta["tree"]
    assert tm["n_clustered"] == 150 and tm["n_clustered"] + tm["n_assigned"] == int((roles == "train").sum())
    assert os.path.isfile(os.path.join(tm["dir"], "tree.npz"))
    assert tm["k"] == 3 and len(tm["dendrogram"]["leaves"]) >= 3
    assert out["run_id"]
    # a second run of the same chain re-uses the saved pool and the kept tree: no new row, no new tree
    seen.clear()
    execute_recipe(_recipe(rid, _steps(ids)), db_path=db, force=True, on_step_result=lambda i, r: seen.__setitem__(i, r))
    assert seen[0].meta["pool"]["saved"] == "reused" and seen[0].meta["pool"]["window_set_id"] == pm["window_set_id"]
    assert seen[2].meta["tree"]["reused"] is True and seen[2].meta["tree"]["key"] == tm["key"]
    conn = init_db(db)
    try:
        assert conn.execute("SELECT COUNT(*) FROM window_sets").fetchone()[0] == n_rows
    finally:
        conn.close()


def test_a_saved_pool_reopens_as_the_source(chain_store):
    from Working.execution import execute_recipe
    db, ids, rid, _tmp = chain_store
    seen = {}
    execute_recipe(_recipe(rid, _steps(ids)[:1]), db_path=db, force=True, on_step_result=lambda i, r: seen.__setitem__(i, r))
    pid = seen[0].meta["pool"]["window_set_id"]
    seen.clear()
    execute_recipe(_recipe(rid, [dict(POOL, params={"pool": str(pid)})]), db_path=db, force=True,
                   on_step_result=lambda i, r: seen.__setitem__(i, r))
    assert seen[0].meta["pool"]["saved"] == "re-opened" and seen[0].meta["pool"]["window_set_id"] == pid
    assert seen[0].value.n_windows == 600


def test_the_pool_block_refuses_with_the_reason_when_no_set_is_ticked(chain_store):
    from Working.execution import RecipeExecutionError, execute_recipe
    db, _ids, rid, _tmp = chain_store
    with pytest.raises(RecipeExecutionError, match="tick at least one"):
        execute_recipe(_recipe(rid, [dict(POOL, params={"window_sets": ""})]), db_path=db, force=True)


def test_the_cluster_block_loads_a_tree_made_elsewhere_through_the_same_reader(chain_store):
    from Working.execution import execute_recipe
    db, ids, rid, tmp = chain_store
    seen = {}
    execute_recipe(_recipe(rid, _steps(ids, sample=10 ** 6)), db_path=db, force=True,
                   on_step_result=lambda i, r: seen.__setitem__(i, r))
    full = seen[2].meta["tree"]
    assert full["n_assigned"] == 0
    seen.clear()
    steps = _steps(ids)
    steps[2]["params"]["tree_path"] = full["dir"]
    execute_recipe(_recipe(rid, steps), db_path=db, force=True, on_step_result=lambda i, r: seen.__setitem__(i, r))
    got = seen[2].meta["tree"]
    assert got["loaded_from"] == full["dir"] and got["n_assigned"] == 0 and got["n_clustered"] == full["n_clustered"]
