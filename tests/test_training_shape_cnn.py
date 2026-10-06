"""
test_training_shape_cnn.py
==========================
fixup-AI: the CNN arm of B.2 (RQ1 version 2) — every pool window encoded as an
image of its RAW samples, a CNN trained on the cluster categories of the same
frozen cut and mapping as the forest, predictions on the test and exam windows,
results in the forest's shape — exported as a self-contained job directory the
cluster runs without the database, and brought back by ONE import function
(`Working.training.hpc_import.import_results`, the CLI's `import-results`, and
what Jobs › Manifest inbox will call).

Pinned here:

* the recipe: same pool, template, shape, cluster, arm (k, mapping) and inputs
  rule as the forest's; the image rule says the n × n image of the raw n samples
  is resized as an IMAGE to the network's input (never the signal resampled);
  fusion first; an unknown encoding is refused;
* the job directory: every window's raw bounds, role and cluster (training rows
  only), the forest's diagnostic hold-back (same seed → the same windows), the
  channel arrays it needs (repo-relative) and their size, the recipe hash; the
  core imports no UI library and does not import torch until a job runs;
* the job (torch only): encoding cached on disk by path and skipped when cached,
  a checkpoint per epoch, a deadline that stops cleanly and resumes, a status;
* the import: validates the returned results against the recipe hash and the
  windows, refuses a changed cut once scored, records configs / runs /
  artifacts, writes the forest's results JSON + predictions parquet shape —
  so `shape_forest.list_runs`, `frozen_for` and AH's blind queue and scores read
  a CNN run unchanged;
* the full-pool Ward: a job directory with the shape vectors, the same Ward over
  EVERY training window, the same tree artifact; imported by the same function
  it lands where the Shape clustering block (sample = every window) finds it;
  refused once the pool has a test score.

Run from the project root:
    /c/ProgramData/anaconda3/python.exe -m pytest tests/test_training_shape_cnn.py -q
"""

import json
import os
import shutil
import subprocess
import sys

import numpy as np
import pandas as pd
import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from Working.database import queries as q  # noqa: E402
from Working.database.schema import init_db  # noqa: E402

AUG = "syn_aug_concat_fs1.mat"
PLAIN = "syn_concat_fs1.mat"
K = 3
#: tiny so a CPU test is seconds: 32-pixel images, an untrained backbone, one epoch
TINY = {"img_size": 32, "pretrained": False, "epochs": 1, "batch_size": 8}
SMOKE = {"n_train": 30, "n_predict": 12}


def _cnn():
    from Working.training import shape_cnn
    return shape_cnn


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


def _mapping(k=K):
    return {"k": k, "clusters": {str(c): {"name": f"p{c}", "class": "interesting" if c == 1 else "not_interesting"}
                                 for c in range(1, k + 1)}}


def _steps(pid, k=K, mapping=None):
    return [{"stage": "preprocessing", "algorithm": "window_pool", "params": {"pool": str(pid)}},
            {"stage": "preprocessing", "algorithm": "trace_shape", "params": {}},
            {"stage": "catalogue", "algorithm": "shape_cluster",
             "params": {"sample": 200, "seed": 0, "k": k, "mapping": json.dumps(mapping or _mapping(k))}}]


@pytest.fixture(scope="module")
def world(tmp_path_factory):
    """A small pool over two synthetic recordings, its kept tree, and a forest run on it (the comparison)."""
    from Working.training import pool as tpool
    from Working.training import shape as sh
    from Working.training import shape_forest as sf
    from Working.training import store as ts
    tmp = tmp_path_factory.mktemp("cnn")
    conn = init_db(str(tmp / "t.sqlite"))
    _add_recording(conn, str(tmp), AUG, 36_000, seed=0)
    _add_recording(conn, str(tmp), PLAIN, 18_000, seed=100)
    ids = []
    for src in (AUG, PLAIN):
        for scale in (1, 10, 30):
            u = tpool.build_unlabelled_set(conn, src, scale_min=scale)
            ids.append(ts.save_window_set(conn, u, str(tmp / "window_sets"), f"ws_{os.path.splitext(src)[0]}_{scale}min"))
    plan = tpool.plan_for(conn, [AUG, PLAIN], hold_out_pack="D")
    pool = tpool.combine(conn, ids, plan, sample={1: 200, 10: 200, 30: 200}, seed=0)
    pid = tpool.save_pool(conn, pool, str(tmp / "window_sets"), "pool_test")
    shapes = sh.trace_shapes(conn, sh.pool_frame(sh.pool_windowset(pool)))
    tree = sh.cluster_shapes(shapes, sample=200, seed=0)
    tree.save(str(tmp / "trees" / tree.meta["key"]))
    row, pool = tpool.load_pool(conn, pid)
    ref = {"id": int(row["id"]), "name": row["name"], "version": int(row["version"]), "key": pool.key}
    template = {"id": 7, "name": "shape_clusters", "steps": _steps(pid)}
    forest = sf.run_and_record(conn, sf.make_recipe(ref, template, n_estimators=20), str(tmp / "training"),
                               tree_root=str(tmp / "trees"))
    conn.close()
    return {"tmp": tmp, "db": tmp / "t.sqlite", "pool_ref": ref, "pool_id": pid, "template": template,
            "forest_run": forest["run_id"], "forest_results": forest["results"], "pool_key": pool.key}


@pytest.fixture
def conn(world, tmp_path):
    shutil.copyfile(world["db"], tmp_path / "t.sqlite")
    c = init_db(str(tmp_path / "t.sqlite"))
    yield c
    c.close()


# ── the recipe ──────────────────────────────────────────────────────────────

def test_the_cnn_recipe_is_the_forests_recipe_with_only_the_model_changed(world):
    from Working.training import shape_forest as sf
    cnn = _cnn()
    forest = sf.make_recipe(world["pool_ref"], world["template"])
    r = cnn.make_recipe(world["pool_ref"], world["template"])
    assert r["kind"] == cnn.RECIPE_KIND != sf.RECIPE_KIND
    for key in ("pool", "template", "shape", "cluster", "arm", "exams"):
        assert r[key] == forest[key], key                      # same windows, same cut, same mapping
    assert "forest" not in r
    assert r["inputs"]["encoding"] == "fusion" == cnn.DEFAULT_ENCODING
    assert r["inputs"]["rule"] == sf.INPUTS_RULE                 # raw samples at the re-cut bounds
    img = r["inputs"]["images"].lower()
    assert "raw" in img and "n × n" in img and "224" in img and "never" in img and "resampled" in img
    assert r["cnn"]["img_size"] == 224 and r["cnn"]["epochs"] >= 1 and r["cnn"]["class_weight"] == "balanced"
    assert r["diagnostic"]["holdback_frac"] == forest["diagnostic"]["holdback_frac"]
    assert r["diagnostic"]["seed"] == forest["forest"]["random_state"]
    assert r.get("smoke") is None
    for enc in ("GASF", "GADF", "recurrence"):
        assert cnn.make_recipe(world["pool_ref"], world["template"], encoding=enc)["inputs"]["encoding"] == enc
    with pytest.raises(ValueError, match="encoding"):
        cnn.make_recipe(world["pool_ref"], world["template"], encoding="spectrogram")


def test_an_unmapped_cut_is_refused_as_the_forest_refuses_it(world):
    cnn = _cnn()
    bad = {**world["template"], "steps": _steps(world["pool_id"], mapping={"k": K, "clusters": {"1": {"class": "interesting"}}})}
    with pytest.raises(ValueError, match="map every cluster"):
        cnn.make_recipe(world["pool_ref"], bad)


def test_the_core_imports_no_ui_library_and_no_torch_until_a_job_runs():
    code = ("import sys; import Working.training.shape_cnn, Working.training.hpc_import, Working.training.full_ward, "
            "Working.hpc.job_export; bad = [m for m in ('torch', 'torchvision', 'fastapi', 'uvicorn', 'panel', "
            "'holoviews', 'bokeh', 'starlette') if m in sys.modules]; print(','.join(bad))")
    out = subprocess.run([sys.executable, "-c", code], cwd=PROJECT_ROOT, capture_output=True, text=True, timeout=180)
    assert out.returncode == 0, out.stderr
    assert out.stdout.strip() == "", f"imported at module level: {out.stdout.strip()}"


# ── the job directory (no torch) ────────────────────────────────────────────

def _export(conn, world, job_dir, **kw):
    cnn = _cnn()
    recipe = cnn.make_recipe(world["pool_ref"], world["template"], cnn=dict(TINY), **kw)
    return cnn.export_job(conn, recipe, str(job_dir), tree_root=str(world["tmp"] / "trees"))


def test_the_job_directory_holds_the_windows_their_cut_and_what_to_copy(conn, world, tmp_path):
    from Working.recipes import short_hash
    from Working.training import shape as sh
    from Working.training import shape_forest as sf
    cnn = _cnn()
    job = _export(conn, world, tmp_path / "job")
    d = job["job_dir"]
    for f in ("recipe.json", "job.json", "windows.npz"):
        assert os.path.isfile(os.path.join(d, f)), f
    with open(os.path.join(d, "recipe.json"), encoding="utf-8") as fh:
        recipe = json.load(fh)
    assert job["recipe_hash"] == short_hash(recipe)
    with open(os.path.join(d, "job.json"), encoding="utf-8") as fh:
        meta = json.load(fh)
    assert meta["recipe_hash"] == job["recipe_hash"] and meta["kind"] == cnn.RECIPE_KIND
    w = cnn.load_windows(d)
    # every pool window after Trace shape: training rows carry their cluster at the cut, the others -1
    row, pool, shapes, tree, _tree_dir = sf._load(conn, recipe, str(world["tmp"] / "trees"))
    lab = sh.labels_at(tree, shapes, K)
    assert len(w["row"]) == len(shapes.frame)
    roles = np.asarray(w["role"]).astype(str)
    assert (np.asarray(w["label"])[roles == "train"] == lab.labels[np.asarray(w["row"])][roles == "train"]).all()
    assert (np.asarray(w["label"])[roles != "train"] == -1).all()
    # the raw bounds: re-cut start and length, as the forest's predictions name them
    f = shapes.frame.reset_index(drop=True)
    assert (np.asarray(w["start"]) == f["start"].to_numpy()[np.asarray(w["row"])]).all()
    assert (np.asarray(w["length"]) == f["length"].to_numpy()[np.asarray(w["row"])]).all()
    # the diagnostic hold-back is the forest's: the same seeded 20 % of the training windows
    train = np.flatnonzero(roles == "train")
    rng = np.random.default_rng(42)
    held = np.zeros(len(train), dtype=bool)
    held[rng.choice(len(train), size=max(1, int(round(0.2 * len(train)))), replace=False)] = True
    assert (np.asarray(w["holdback"])[train] == held).all()
    assert recipe["bundle"]["windows_key"] == cnn.windows_key(w)
    # what must be copied to the cluster: the job directory and each channel array, repo-relative where possible, sized
    kinds = {c["what"] for c in job["copy"]}
    assert {"job directory", "channel array"} <= kinds
    chans = [c for c in job["copy"] if c["what"] == "channel array"]
    assert len(chans) == len({(s, c) for s, c in zip(np.asarray(w["source_file"]), np.asarray(w["channel"]))})
    assert all(c["bytes"] > 0 for c in job["copy"])
    assert job["total_bytes"] == sum(c["bytes"] for c in job["copy"])
    assert job["n_train"] == len(train) and job["n_predict"] == int((roles != "train").sum())


def test_a_smoke_job_takes_a_few_seeded_windows_and_is_a_different_recipe(conn, world, tmp_path):
    cnn = _cnn()
    full = _export(conn, world, tmp_path / "full")
    smoke = _export(conn, world, tmp_path / "smoke", smoke=dict(SMOKE))
    assert smoke["recipe_hash"] != full["recipe_hash"]
    w = cnn.load_windows(smoke["job_dir"])
    roles = np.asarray(w["role"]).astype(str)
    assert int((roles == "train").sum()) == SMOKE["n_train"]
    assert int((roles == "test").sum()) <= SMOKE["n_predict"] and int((roles == "exam").sum()) <= SMOKE["n_predict"]
    assert int((roles == "validation").sum()) == 0
    again = _export(conn, world, tmp_path / "smoke2", smoke=dict(SMOKE))
    assert again["recipe_hash"] == smoke["recipe_hash"]               # seeded: the same windows again


# ── the job itself (torch) ──────────────────────────────────────────────────

def _torch():
    return pytest.importorskip("torch")


def test_a_window_becomes_the_image_the_manual_label_cnns_were_fed(world):
    _torch()
    cnn = _cnn()
    from Working.Catalogue.cnn.apply_cnn import _window_to_pil
    from torchvision import transforms
    x = np.sin(np.linspace(0, 9, 600)) + np.linspace(0, 1, 600)
    for enc in ("fusion", "GASF"):
        img = cnn.encode_window(x, enc, 64)
        want = np.asarray(transforms.Resize((64, 64))(_window_to_pil(x, enc)))
        if want.ndim == 3 and enc != "fusion":
            want = want[..., :1]
        assert img.dtype == np.uint8 and img.shape == (64, 64, 3 if enc == "fusion" else 1)
        assert np.array_equal(img, want.reshape(img.shape))


def test_the_job_runs_without_the_database_checkpoints_and_resumes_after_a_deadline(conn, world, tmp_path):
    _torch()
    cnn = _cnn()
    job = _export(conn, world, tmp_path / "job", smoke=dict(SMOKE))
    d = job["job_dir"]
    code, _text = cnn.job_status(d)
    assert code == 1
    # a deadline already spent: the job stops cleanly, incomplete, having encoded at most one chunk
    first = cnn.run_job(d, device="cpu", deadline_s=0.0)
    assert first["status"] == "incomplete"
    assert cnn.job_status(d)[0] == 1
    done = cnn.run_job(d, device="cpu")
    assert done["status"] == "complete", done
    assert cnn.job_status(d)[0] == 0
    out = os.path.join(d, "out")
    for f in ("done.json", "model.pt", "predictions.npz", "history.json", "diagnostic.json"):
        assert os.path.isfile(os.path.join(out, f)), f
    # images are bulk arrays: on disk, by path, in the job's cache (not in out/, which is what comes back)
    cache = [p for p in os.listdir(os.path.join(d, "cache")) if p.startswith("images_")]
    assert cache, "the encoding cache is on disk"
    with open(os.path.join(out, "history.json"), encoding="utf-8") as fh:
        hist = json.load(fh)
    assert len(hist["diagnostic"]) == TINY["epochs"] and len(hist["final"]) == TINY["epochs"]
    # a second run of a complete job does nothing (encoding skipped when cached; no epoch re-run)
    again = cnn.run_job(d, device="cpu")
    assert again["status"] == "complete" and again.get("skipped") is True
    with open(os.path.join(out, "done.json"), encoding="utf-8") as fh:
        doneinfo = json.load(fh)
    assert doneinfo["recipe_hash"] == job["recipe_hash"]
    assert set(doneinfo["timings"]) >= {"encode", "diagnostic", "final", "predict"}
    assert doneinfo["measured"]["encode_ms_by_scale"]


# ── the import (one function: the CLI and Jobs › Manifest inbox call it) ────

@pytest.fixture(scope="module")
def ran_job(world, tmp_path_factory):
    pytest.importorskip("torch")
    cnn = _cnn()
    tmp = tmp_path_factory.mktemp("ran")
    shutil.copyfile(world["db"], tmp / "t.sqlite")
    c = init_db(str(tmp / "t.sqlite"))
    try:
        job = _export(c, world, tmp / "job", smoke=dict(SMOKE))
    finally:
        c.close()
    assert cnn.run_job(job["job_dir"], device="cpu")["status"] == "complete"
    return job


def _job_copy(ran_job, tmp_path):
    d = str(tmp_path / "returned")
    shutil.copytree(ran_job["job_dir"], d)
    return d


def test_import_records_the_run_in_the_forests_shape(conn, world, ran_job, tmp_path):
    from Working.training import hpc_import as hi
    from Working.training import shape_forest as sf
    cnn = _cnn()
    d = _job_copy(ran_job, tmp_path)
    got = hi.import_results(conn, d, root=str(tmp_path / "training"), tree_root=str(world["tmp"] / "trees"))
    assert got["kind"] == cnn.RECIPE_KIND and got["created"] is True
    assert got["config_hash"] == ran_job["recipe_hash"]
    rid = got["run_id"]
    row = conn.execute("SELECT r.status, c.config_hash FROM runs r JOIN configs c ON c.id = r.config_id WHERE r.id = ?",
                       (rid,)).fetchone()
    assert row["status"] == "completed" and row["config_hash"] == ran_job["recipe_hash"]
    kinds = {r[0] for r in conn.execute("SELECT kind FROM artifacts WHERE run_id = ?", (rid,))}
    assert {"other", "model"} <= kinds
    with open(got["results_path"], encoding="utf-8") as fh:
        res = json.load(fh)
    forest = world["forest_results"]
    # the forest's top-level shape, so Results and the blind view need no second reader
    for key in ("kind", "arm", "pool", "template", "shape", "inputs", "mapping", "tree", "training", "diagnostic",
                "exams", "predictions_path", "model_path", "yardstick_A", "yardstick_B", "timings", "run_id"):
        assert key in res, key
    assert res["kind"] == cnn.RECIPE_KIND and res["arm"]["k"] == forest["arm"]["k"] == K
    assert res["mapping"] == forest["mapping"] and res["pool"]["key"] == forest["pool"]["key"]
    assert res["tree"]["key"] == forest["tree"]["key"]                       # the same tree, the same cut
    assert set(res["exams"]) == {sf.EXAM_I, sf.EXAM_II}
    for ek, role in ((sf.EXAM_I, "test"), (sf.EXAM_II, "exam")):
        assert res["exams"][ek]["status"] == sf.PREDICTED and res["exams"][ek]["role"] == role
    assert res["diagnostic"]["kind"] == "diagnostic" and "not a result" in res["diagnostic"]["note"]
    assert res["smoke"] and res["where"] in ("local", "local smoke", "HPC")
    p = pd.read_parquet(res["predictions_path"])
    fp = pd.read_parquet(forest["predictions_path"])
    assert list(p.columns) == list(fp.columns)                               # the same parquet shape
    assert set(p["role"]) <= {"test", "exam", "validation"} and p["cluster"].between(1, K).all()
    assert set(p["class"]) <= {"interesting", "not_interesting"}
    assert p["p_interesting"].between(0, 1).all()
    # each predicted window is one of the forest's windows (same bounds), and its class is its cluster's mapped class
    key = ["source_file", "channel", "start", "length"]
    assert len(p.merge(fp[key], on=key)) == len(p)
    assert all(p["class"] == [forest["mapping"]["clusters"][str(c)]["class"] for c in p["cluster"]])
    # listed beside the forest run, model named
    listed = {r["run_id"]: r for r in sf.list_runs(conn)}
    assert rid in listed and world["forest_run"] in listed
    assert "CNN" in listed[rid]["model"] and "fusion" in listed[rid]["model"]
    assert "forest" in listed[world["forest_run"]]["model"]
    # importing the same returned directory again is a no-op
    again = hi.import_results(conn, d, root=str(tmp_path / "training"), tree_root=str(world["tmp"] / "trees"))
    assert again["run_id"] == rid and again["created"] is False


def test_a_cnn_run_is_read_by_the_blind_queue_and_scores_unchanged_and_freezes_the_pool(conn, world, ran_job, tmp_path):
    from Working.review import verdicts as V
    from Working.training import blind
    from Working.training import hpc_import as hi
    from Working.training import shape_forest as sf
    from Working.training.store import CutFrozen
    d = _job_copy(ran_job, tmp_path)
    rid = hi.import_results(conn, d, root=str(tmp_path / "training"))["run_id"]
    made = blind.make_queue(conn, rid, n=12, repeat_frac=0.0, seed=0)
    s = pd.read_parquet(made["sample_path"])
    assert len(s) == 12 and set(s["role"]) <= {"test", "exam"}
    for _, r in s.iterrows():
        V.write_verdict(conn, made["queue_id"], int(r["showing"]), r["class"])
    sc = blind.score(conn, rid, n_boot=50, n_null=50, seed=0)
    assert set(sc["exams"]) == {"i_later_block", "ii_unseen_channels"}
    scored = [e for e in sc["exams"].values() if e.get("n_scored")]
    assert scored and all(e["macro_f1"] == pytest.approx(1.0) for e in scored if e.get("macro_f1") is not None)
    # a blind label on the CNN run is a score: the pool's cut and mapping are frozen for the forest too
    fz = sf.frozen_for(conn, world["pool_key"])
    assert fz and fz["run_id"] == rid
    with pytest.raises(CutFrozen):
        sf.check_frozen(conn, world["pool_key"], K + 1, _mapping(K + 1))


def test_import_refuses_a_changed_recipe_other_windows_or_a_changed_cut(conn, world, ran_job, tmp_path):
    from Working.training import hpc_import as hi
    root = str(tmp_path / "training")
    # 1. the recipe edited after export
    d1 = _job_copy(ran_job, tmp_path / "a")
    p = os.path.join(d1, "recipe.json")
    with open(p, encoding="utf-8") as fh:
        r = json.load(fh)
    r["cnn"]["epochs"] = 99
    with open(p, "w", encoding="utf-8") as fh:
        json.dump(r, fh)
    with pytest.raises(hi.ImportRefused, match="recipe"):
        hi.import_results(conn, d1, root=root)
    # 2. the windows changed under the recipe
    d2 = _job_copy(ran_job, tmp_path / "b")
    wp = os.path.join(d2, "windows.npz")
    with np.load(wp, allow_pickle=False) as z:
        arrs = {k: z[k] for k in z.files}
    arrs["start"] = arrs["start"] + 1
    np.savez(wp, **arrs)
    with pytest.raises(hi.ImportRefused, match="windows"):
        hi.import_results(conn, d2, root=root)
    # 3. no results yet (the job did not finish)
    d3 = _job_copy(ran_job, tmp_path / "c")
    os.remove(os.path.join(d3, "out", "done.json"))
    with pytest.raises(hi.ImportRefused, match="not finished|no results"):
        hi.import_results(conn, d3, root=root)
    # 4. a pool not in this database
    d4 = _job_copy(ran_job, tmp_path / "d")
    conn.execute("UPDATE window_sets SET recipe_hash = 'zzzz' WHERE recipe_hash = ?", (world["pool_key"],))
    conn.commit()
    with pytest.raises(hi.ImportRefused, match="pool"):
        hi.import_results(conn, d4, root=root)


def test_import_refuses_a_different_cut_once_the_pool_has_a_test_score(conn, world, ran_job, tmp_path):
    """A forest run on the pool, scored at a different mapping, freezes it: the CNN job's mapping is refused."""
    from Working.training import hpc_import as hi
    from Working.training import shape_forest as sf
    from Working.training.store import CutFrozen
    other = {**world["template"], "steps": _steps(world["pool_id"], mapping={"k": K, "clusters": {
        str(c): {"name": "", "class": "interesting" if c == 2 else "not_interesting"} for c in range(1, K + 1)}})}
    run = sf.run_and_record(conn, sf.make_recipe(world["pool_ref"], other, n_estimators=10), str(tmp_path / "tr"),
                            tree_root=str(world["tmp"] / "trees"))
    with open(run["results_path"], encoding="utf-8") as fh:
        res = json.load(fh)
    res["exams"][sf.EXAM_I]["status"] = "scored"
    with open(run["results_path"], "w", encoding="utf-8") as fh:
        json.dump(res, fh)
    d = _job_copy(ran_job, tmp_path)
    with pytest.raises((CutFrozen, hi.ImportRefused), match="frozen"):
        hi.import_results(conn, d, root=str(tmp_path / "training"))


def test_the_cli_import_results_calls_the_same_function(conn, world, ran_job, tmp_path):
    db = conn.execute("PRAGMA database_list").fetchone()[2]
    conn.close()
    d = _job_copy(ran_job, tmp_path)
    out = subprocess.run([sys.executable, "-m", "Working.training", "import-results", d, "--db", db,
                          "--root", str(tmp_path / "training")], cwd=PROJECT_ROOT, capture_output=True, text=True,
                         timeout=300, env={**os.environ, "PYTHONIOENCODING": "utf-8"})
    assert out.returncode == 0, out.stderr + out.stdout
    assert "imported" in out.stdout and "run" in out.stdout
    c = init_db(db)
    try:
        n = c.execute("SELECT COUNT(*) FROM configs WHERE config_hash = ?", (ran_job["recipe_hash"],)).fetchone()[0]
        assert n == 1
    finally:
        c.close()


# ── the full-pool Ward ──────────────────────────────────────────────────────

def test_the_full_pool_ward_round_trip_lands_where_the_cluster_block_reads_it(conn, world, tmp_path):
    import Adapters.catalogue_shape_cluster as csc
    from Working.training import full_ward as fw
    from Working.training import hpc_import as hi
    from Working.training import shape as sh
    from Working.training import shape_forest as sf
    recipe = _cnn().make_recipe(world["pool_ref"], world["template"])
    _row, _pool, shapes, _tree, _d = sf._load(conn, recipe, str(world["tmp"] / "trees"))
    sp = shapes.save(str(tmp_path / "shapes"))
    job = fw.export_job(sp, str(tmp_path / "ward"), seed=0)
    n_train = int((shapes.frame["role"].astype(str) == "train").sum())
    assert job["n"] == n_train
    # memory: two copies of the condensed float64 distances (scipy copies them) + the vectors, with a margin
    assert job["memory"]["bytes_distances"] == 8 * n_train * (n_train - 1) // 2
    assert job["memory"]["request_gb"] >= 2 * job["memory"]["bytes_distances"] / 2 ** 30
    assert fw.memory_estimate(60_000)["bytes_distances"] / 1e9 == pytest.approx(14.4, rel=0.01)   # the ticket's 14 GB
    assert fw.job_status(job["job_dir"])[0] == 1
    fw.run_job(job["job_dir"])
    assert fw.job_status(job["job_dir"])[0] == 0
    trees = str(tmp_path / "trees")
    got = hi.import_results(conn, job["job_dir"], root=str(tmp_path / "training"), tree_root=trees)
    assert got["kind"] == fw.RECIPE_KIND
    want = os.path.join(trees, sh.tree_key(shapes, None, 0))
    assert os.path.normcase(os.path.abspath(got["tree_dir"])) == os.path.normcase(os.path.abspath(want))
    tree = sh.load_tree_for(want, shapes)                                  # the same reader AG's block uses
    assert len(tree.leaf_rows) == n_train and tree.meta["sample"] is None
    old = csc.RESULTS_DIR
    try:
        csc.RESULTS_DIR = trees
        t2, d2, reused, _src = csc.tree_for(shapes, 0, 0)                   # sample = 0: every training window
        assert reused is True and os.path.normcase(os.path.abspath(d2)) == os.path.normcase(os.path.abspath(want))
    finally:
        csc.RESULTS_DIR = old


def test_the_full_pool_ward_is_refused_once_the_pool_has_a_test_score(conn, world, tmp_path):
    from Working.training import full_ward as fw
    from Working.training import hpc_import as hi
    from Working.training import shape_forest as sf
    recipe = _cnn().make_recipe(world["pool_ref"], world["template"])
    _row, _pool, shapes, _tree, _d = sf._load(conn, recipe, str(world["tmp"] / "trees"))
    job = fw.export_job(shapes.save(str(tmp_path / "shapes")), str(tmp_path / "ward"), seed=0)
    fw.run_job(job["job_dir"])
    path, res = sf._results_of(conn, world["forest_run"])
    res["exams"][sf.EXAM_I]["status"] = "scored"
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(res, fh)
    try:
        with pytest.raises((hi.ImportRefused, ValueError), match="score"):
            hi.import_results(conn, job["job_dir"], root=str(tmp_path / "training"), tree_root=str(tmp_path / "trees"))
    finally:
        res["exams"][sf.EXAM_I]["status"] = sf.PREDICTED
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(res, fh)
