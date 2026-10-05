"""
test_training_shape.py
======================
fixup-ag: cluster a window POOL on trace shape (RQ1 version 2, `docs/rq_roundA/
RQ1-…` "New scope, version 2"; ticket `docs/prompts/fixup/AG-…`). The pool is
`AF`'s (`Working.training.pool.combine`); this pins the UI-free core the three
Analyse blocks call (`Working.training.shape`).

What is decided (the researcher, 2026-10-05) and pinned here:

* the clustering is the LIBRARY's: Ward linkage on resampled, z-normalised
  vectors under the scale-invariant distance (`Working.library.grouping.methods.
  ward`, built on `Working.distances.resample_to_length` and `z_normalize`) — at
  the Library's own resample length, never a second implementation;
* every window, whatever its scale, goes through that resample-and-normalise, so
  windows are compared by shape; the scale is kept on every window;
* windows under the dataset's noise floor (Settings › Datasets, 0.1 mV where
  empty) are LEFT OUT by default and counted per recording and scale; each
  window's raw range is kept beside it; the switch can be turned off;
* Ward on a seeded sample (default 20,000) of TRAINING windows only, stratified
  by recording × scale; every other training window is assigned to the nearest
  cluster centre; validation, test and exam windows never touch the tree;
* the linkage is kept as an artifact, and a tree made elsewhere (an HPC Ward over
  every window) loads in its place through the same reader;
* a cluster is shown by its medoid (a real window), a seeded handful of random
  members, its scale mix and its raw amplitude range.

Run from the project root:
    /c/ProgramData/anaconda3/python.exe -m pytest tests/test_training_shape.py -q
"""

import os
import sys

import numpy as np
import pandas as pd
import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from Working.database import queries as q  # noqa: E402
from Working.database.schema import init_db  # noqa: E402

AUG = "syn_aug_concat_fs1.mat"      # 10 h at 1 Hz, 16 channels
PLAIN = "syn_concat_fs1.mat"        # 5 h at 1 Hz, 16 channels
N_AUG, N_PLAIN = 36_000, 18_000
QUIET = 1                           # PLAIN's CH2 (pack A, a training channel) sits under the 0.1 mV floor


def _shape():
    from Working.training import shape
    return shape


def _pool():
    from Working.training import pool as tpool
    return tpool


def _add_recording(conn, tmp, source, n, quiet=(), seed=0, units="V"):
    stem = os.path.splitext(source)[0]
    d = os.path.join(tmp, "channels", stem)
    os.makedirs(d, exist_ok=True)
    for ch in range(16):
        rng = np.random.default_rng(seed + ch)
        x = rng.standard_normal(int(n))
        # a slow ramp-and-drop every 40 minutes, so there is structure to cluster
        t = np.arange(int(n))
        x = 0.05 * x + 0.2 * ((t % 2400) / 2400.0) ** 3
        if ch in quiet:
            x = 1e-6 * rng.standard_normal(int(n))      # 0.001 mV: under any floor
        npy = os.path.join(d, f"CH{ch}.npy")
        np.save(npy, x)
        rid = q.insert_recording(conn, source, ch, 1.0, int(n), 0, npy)
        conn.execute("UPDATE recordings SET units = ? WHERE id = ?", (units, rid))
    conn.commit()


@pytest.fixture
def store(tmp_path):
    conn = init_db(str(tmp_path / "t.sqlite"))
    _add_recording(conn, str(tmp_path), AUG, N_AUG, seed=0)
    _add_recording(conn, str(tmp_path), PLAIN, N_PLAIN, quiet=(QUIET,), seed=100)
    yield conn, tmp_path
    conn.close()


def _six_and_pool(conn, tmp_path, per_scale=300, seed=0):
    tpool = _pool()
    from Working.training import store as ts
    ids = []
    for src in (AUG, PLAIN):
        for scale in (1, 10, 30):
            u = tpool.build_unlabelled_set(conn, src, scale_min=scale)
            ids.append(ts.save_window_set(conn, u, str(tmp_path / "window_sets"),
                                          f"ws_{os.path.splitext(src)[0]}_{scale}min"))
    plan = tpool.plan_for(conn, [AUG, PLAIN], hold_out_pack="D")
    pool = tpool.combine(conn, ids, plan, sample={1: per_scale, 10: per_scale, 30: per_scale}, seed=seed)
    return ids, pool


@pytest.fixture
def pooled(store):
    conn, tmp_path = store
    _ids, pool = _six_and_pool(conn, tmp_path)
    return conn, tmp_path, pool


# ── the pool travels as a WindowSet ─────────────────────────────────────────

def test_a_pool_travels_as_a_windowset_and_comes_back_the_same(pooled, tmp_path):
    conn, _tmp, pool = pooled
    sh = _shape()
    ws = sh.pool_windowset(pool)
    assert ws.n_windows == len(pool.table)
    frame = sh.pool_frame(ws)
    for c in ("recording_id", "source_file", "channel", "start", "length", "fs", "scale_min", "role"):
        assert list(frame[c]) == list(pool.table[c]), c
    # through the step cache's own serialiser and back
    from Working.types import WindowSet
    ws.to_path(str(tmp_path / "ws"))
    back = sh.pool_frame(WindowSet.from_path(str(tmp_path / "ws")))
    assert list(back["role"]) == list(pool.table["role"])
    assert list(back["start"]) == list(pool.table["start"])


def test_a_windowset_that_is_not_a_pool_is_refused_with_the_reason():
    from Working.types import WindowSet
    sh = _shape()
    with pytest.raises(ValueError, match="Window pool"):
        sh.pool_frame(WindowSet(starts=np.arange(3), length=10, fs=1.0))


# ── the shape vectors ───────────────────────────────────────────────────────

def test_shapes_are_the_librarys_resample_and_z_normalise_at_the_librarys_length(pooled):
    conn, _tmp, pool = pooled
    sh = _shape()
    from Working.distances import resample_to_length, z_normalize
    from Working.library.grouping.methods import ward
    assert sh.RESAMPLE_LENGTH == ward.RESAMPLE_LENGTH
    out = sh.trace_shapes(conn, sh.pool_frame(sh.pool_windowset(pool)))
    assert out.vectors.shape == (len(out.frame), ward.RESAMPLE_LENGTH)
    rec = {int(r[0]): r[1] for r in conn.execute("SELECT id, npy_path FROM recordings")}
    for i in (0, len(out.frame) // 2, len(out.frame) - 1):
        row = out.frame.iloc[i]
        raw = np.load(rec[int(row["recording_id"])])[int(row["start"]):int(row["start"]) + int(row["length"])]
        want = z_normalize(resample_to_length(raw, ward.RESAMPLE_LENGTH))
        assert np.allclose(out.vectors[int(row["shape_row"])], want, atol=1e-5)
        # the raw range is kept beside the window, in mV (the recording is in volts)
        assert row["raw_range_mv"] == pytest.approx(float(np.ptp(raw)) * 1000.0, rel=1e-6)
        assert 0.0 <= row["peak_frac"] <= 1.0
    # every scale goes through the same length: windows are compared by shape, not duration
    assert set(out.frame["scale_min"]) == {1.0, 10.0, 30.0}


def test_windows_under_the_noise_floor_are_left_out_by_default_and_counted_per_recording_and_scale(pooled):
    conn, _tmp, pool = pooled
    sh = _shape()
    frame = sh.pool_frame(sh.pool_windowset(pool))
    quiet_rid = conn.execute("SELECT id FROM recordings WHERE source_file = ? AND channel = ?", (PLAIN, QUIET)).fetchone()[0]
    n_quiet = int((frame["recording_id"] == quiet_rid).sum())
    assert n_quiet > 0, "the fixture must put some quiet windows in the pool"
    out = sh.trace_shapes(conn, frame)
    assert not (out.frame["recording_id"] == quiet_rid).any()
    assert len(out.frame) == len(frame) - n_quiet
    removed = out.meta["under_floor"]
    assert removed["n"] == n_quiet
    by = {(r["recording"], r["scale_min"]): r["n"] for r in removed["by"]}
    assert sum(by.values()) == n_quiet
    assert set(k[0] for k in by) == {PLAIN}
    # the floor is the dataset's: 0.1 mV where Settings › Datasets is empty, said so
    assert out.meta["floors"][PLAIN]["floor_mv"] == pytest.approx(0.1)
    assert out.meta["noise_floor"] is True


def test_the_floor_is_read_from_settings_datasets_and_the_switch_turns_it_off(pooled):
    conn, _tmp, pool = pooled
    sh = _shape()
    from Working.registration.settings import put_settings
    frame = sh.pool_frame(sh.pool_windowset(pool))
    # a floor above every window of AUG: every AUG window goes
    put_settings(conn, "datasets", {"meta.syn_aug_concat_fs1.noise_floor": 1e9})
    out = sh.trace_shapes(conn, frame)
    assert not (out.frame["source_file"] == AUG).any()
    assert out.meta["floors"][AUG]["floor_mv"] == pytest.approx(1e9)
    off = sh.trace_shapes(conn, frame, noise_floor=False)
    assert len(off.frame) == len(frame) and off.meta["under_floor"]["n"] == 0
    assert off.meta["noise_floor"] is False


def test_a_recording_with_no_declared_unit_is_unmeasured_kept_and_counted(pooled):
    conn, _tmp, pool = pooled
    sh = _shape()
    conn.execute("UPDATE recordings SET units = NULL WHERE source_file = ?", (AUG,))
    conn.commit()
    frame = sh.pool_frame(sh.pool_windowset(pool))
    out = sh.trace_shapes(conn, frame)
    n_aug = int((frame["source_file"] == AUG).sum())
    assert int((out.frame["source_file"] == AUG).sum()) == n_aug
    assert out.meta["unmeasured"]["n"] == n_aug
    assert out.frame.loc[out.frame["source_file"] == AUG, "raw_range_mv"].isna().all()


def test_the_vectors_are_bulk_arrays_on_disk_by_path_and_load_back(pooled, tmp_path):
    conn, _tmp, pool = pooled
    sh = _shape()
    out = sh.trace_shapes(conn, sh.pool_frame(sh.pool_windowset(pool)))
    path = out.save(str(tmp_path / "shapes"))
    assert os.path.isfile(path)
    back = sh.ShapeSet.load(path)
    assert np.allclose(back.vectors, out.vectors)
    assert list(back.frame["start"]) == list(out.frame["start"])
    assert back.key == out.key


# ── clustering ──────────────────────────────────────────────────────────────

@pytest.fixture
def shaped(pooled):
    conn, tmp_path, pool = pooled
    sh = _shape()
    return conn, tmp_path, sh.trace_shapes(conn, sh.pool_frame(sh.pool_windowset(pool)))


def test_only_training_windows_are_clustered_from_a_seeded_sample_stratified_by_recording_and_scale(shaped):
    _conn, _tmp, s = shaped
    sh = _shape()
    tree = sh.cluster_shapes(s, sample=200, seed=3)
    roles = s.frame["role"].to_numpy()
    assert (roles[tree.leaf_rows] == "train").all()
    assert len(tree.leaf_rows) == 200
    assert set(tree.train_rows) == set(np.flatnonzero(roles == "train"))
    assert np.array_equal(tree.leaf_rows, sh.cluster_shapes(s, sample=200, seed=3).leaf_rows)
    assert not np.array_equal(tree.leaf_rows, sh.cluster_shapes(s, sample=200, seed=4).leaf_rows)
    # proportional to each recording x scale stratum of the training windows (within one window)
    tr = s.frame.iloc[tree.train_rows]
    lf = s.frame.iloc[tree.leaf_rows]
    for key, n in tr.groupby(["source_file", "scale_min"]).size().items():
        got = int(((lf["source_file"] == key[0]) & (lf["scale_min"] == key[1])).sum())
        assert abs(got - 200 * n / len(tr)) <= 1.0, (key, got, n)


def test_the_tree_is_the_librarys_ward_on_the_librarys_vectors(shaped):
    _conn, _tmp, s = shaped
    sh = _shape()
    from Working.library.grouping.methods import ward
    tree = sh.cluster_shapes(s, sample=120, seed=0)
    fit = ward.WardMethod().fit(list(s.vectors[tree.leaf_rows]), params={"resample_length": sh.RESAMPLE_LENGTH})
    assert np.allclose(tree.Z, fit.payload["linkage"])
    assert tree.meta["distance_scale"] == pytest.approx(fit.payload["distance_scale"])


def test_every_other_training_window_goes_to_the_nearest_centre_and_no_test_window_touches_the_tree(shaped):
    _conn, _tmp, s = shaped
    sh = _shape()
    tree = sh.cluster_shapes(s, sample=150, seed=0)
    lab = sh.labels_at(tree, s, 4)
    roles = s.frame["role"].to_numpy()
    assert (lab.labels[roles != "train"] == -1).all()
    assert (lab.labels[roles == "train"] >= 1).all()
    assert lab.n_clustered == 150 and lab.n_assigned == int((roles == "train").sum()) - 150
    leaf = tree.leaf_rows
    centres = np.vstack([s.vectors[leaf][lab.labels[leaf] == c].mean(axis=0) for c in range(1, 5)])
    rest = np.setdiff1d(tree.train_rows, leaf)
    d = ((s.vectors[rest][:, None, :] - centres[None, :, :]) ** 2).sum(axis=2)
    assert np.array_equal(lab.labels[rest], np.argmin(d, axis=1) + 1)
    # scrambling every non-training window changes no label
    s2 = sh.ShapeSet(frame=s.frame, vectors=s.vectors.copy(), meta=s.meta)
    s2.vectors[roles != "train"] = np.random.default_rng(9).standard_normal(s2.vectors[roles != "train"].shape)
    tree2 = sh.cluster_shapes(s2, sample=150, seed=0)
    assert np.allclose(tree2.Z, tree.Z)
    assert np.array_equal(sh.labels_at(tree2, s2, 4).labels, lab.labels)


def test_the_kept_tree_saves_and_a_tree_made_elsewhere_loads_in_its_place(shaped, tmp_path):
    _conn, _tmp, s = shaped
    sh = _shape()
    tree = sh.cluster_shapes(s, sample=150, seed=0)
    d = tree.save(str(tmp_path / "tree_local"))
    back = sh.ShapeTree.load(d)
    assert np.allclose(back.Z, tree.Z) and np.array_equal(back.leaf_rows, tree.leaf_rows)
    assert back.meta["shape_key"] == s.key
    # "elsewhere": a Ward over EVERY training window, written by the same writer, read by the same reader
    full = sh.cluster_shapes(s, sample=None, seed=0)
    d2 = full.save(str(tmp_path / "tree_hpc"))
    loaded = sh.load_tree_for(d2, s)
    assert len(loaded.leaf_rows) == len(loaded.train_rows)
    lab = sh.labels_at(loaded, s, 3)
    assert lab.n_assigned == 0 and lab.n_clustered == len(loaded.train_rows)
    # a tree made on other windows is refused, with the reason
    other = sh.ShapeSet(frame=s.frame.iloc[:-5].reset_index(drop=True), vectors=s.vectors[:-5], meta=s.meta)
    with pytest.raises(ValueError, match="other windows"):
        sh.load_tree_for(d2, other)


def test_propose_gives_sizes_specks_and_silhouette_per_k_and_suggests_by_the_baselines_rule(shaped):
    _conn, _tmp, s = shaped
    sh = _shape()
    from Working.training.paired import SMALL_CLUSTER_MIN
    tree = sh.cluster_shapes(s, sample=150, seed=0)
    p = sh.propose(tree, s, k_range=(2, 6))
    assert [r["k"] for r in p["by_k"]] == [2, 3, 4, 5, 6]
    n_train = len(tree.train_rows)
    assert p["small_below"] == max(SMALL_CLUSTER_MIN, int(np.ceil(0.005 * n_train)))
    for r in p["by_k"]:
        assert sum(r["sizes"].values()) == n_train
        assert r["effective_k"] == r["k"] - len(r["small_clusters"])
        assert r["silhouette"] is None or -1.0 <= r["silhouette"] <= 1.0
    ok = [r for r in p["by_k"] if r["silhouette"] is not None and r["effective_k"] >= 2]
    if ok:
        assert p["suggested_k"] == max(ok, key=lambda r: (round(r["silhouette"], 3), r["effective_k"]))["k"]


def test_the_dendrogram_is_truncated_and_the_cut_line_follows_k(shaped):
    _conn, _tmp, s = shaped
    sh = _shape()
    tree = sh.cluster_shapes(s, sample=150, seed=0)
    dg = sh.dendrogram(tree, leaves=12)
    assert len(dg["leaves"]) == 12
    assert len(dg["icoord"]) == len(dg["dcoord"]) == 11
    h = np.sort(tree.Z[:, 2])
    for k in (2, 3, 5):
        cut = sh.cut_height(tree, k)
        assert h[-k] <= cut <= h[-(k - 1)]
        assert sh.k_at_height(tree, cut) == k


def test_a_cluster_shows_its_medoid_seeded_members_mean_shape_scale_mix_and_amplitude_range(shaped):
    _conn, _tmp, s = shaped
    sh = _shape()
    tree = sh.cluster_shapes(s, sample=150, seed=0)
    lab = sh.labels_at(tree, s, 3)
    big = int(np.bincount(lab.labels[lab.labels > 0]).argmax())
    det = sh.cluster_detail(tree, s, lab, big, seed=0)
    members = set(np.flatnonzero(lab.labels == big))
    assert det["n"] == len(members)
    assert det["medoid"]["row"] in members
    assert len(det["members"]) == min(sh.DEFAULT_MEMBERS, len(members)) == 12
    assert {m["row"] for m in det["members"]} <= members
    assert [m["row"] for m in det["members"]] == [m["row"] for m in sh.cluster_detail(tree, s, lab, big, seed=0)["members"]]
    assert sum(r["n"] for r in det["scales"]) == det["n"]
    assert sum(r["n"] for r in det["recordings"]) == det["n"]
    a = det["amplitude_mv"]
    assert a["min"] <= a["median"] <= a["max"]
    assert len(det["mean"]) == len(det["sd"]) == sh.RESAMPLE_LENGTH
    for m in [det["medoid"], *det["members"]]:
        assert len(m["shape"]) == sh.RESAMPLE_LENGTH
        assert {"source_file", "channel", "start", "length", "scale_min", "raw_range_mv"} <= set(m)
    with pytest.raises(ValueError, match="no cluster"):
        sh.cluster_detail(tree, s, lab, 99)


def test_shapes_of_one_kind_at_different_scales_share_a_cluster():
    """Two shapes — a slow rise and a sharp drop — each drawn at 1, 10 and 30 minutes: compared by
    shape, the three durations of one shape fall together and the two shapes apart."""
    sh = _shape()
    from Working.library.grouping.methods import ward
    rng = np.random.default_rng(0)
    rows, segs = [], []
    for kind in ("rise", "drop"):
        for scale, length in ((1.0, 60), (10.0, 600), (30.0, 1800)):
            for i in range(30):
                u = np.linspace(0, 1, length)
                y = u ** 2 if kind == "rise" else np.where(u < 0.5, 1.0, -1.0)
                segs.append(y + 0.05 * rng.standard_normal(length))
                rows.append({"recording_id": 1, "source_file": "s.mat", "channel": 0, "start": len(rows) * 2000,
                             "length": length, "fs": 1.0, "scale_min": scale, "role": "train", "set_id": 1,
                             "raw_range_mv": 1.0, "peak_frac": 0.5, "kind": kind})
    frame = pd.DataFrame(rows)
    frame["shape_row"] = np.arange(len(frame))
    s = sh.ShapeSet(frame=frame.drop(columns=["kind"]), vectors=ward.shape_vectors(segs, sh.RESAMPLE_LENGTH).astype(np.float32),
                    meta={})
    tree = sh.cluster_shapes(s, sample=None)
    lab = sh.labels_at(tree, s, 2).labels
    for kind in ("rise", "drop"):
        assert len(set(lab[frame["kind"] == kind])) == 1
    assert lab[frame["kind"] == "rise"][0] != lab[frame["kind"] == "drop"][0]


def test_shape_imports_no_ui_library():
    import ast
    import Working.training.shape as m
    with open(m.__file__, encoding="utf-8") as f:
        tree = ast.parse(f.read())
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module.split(".")[0])
    assert not names & {"panel", "holoviews", "bokeh", "fastapi", "uvicorn", "react", "matplotlib"}
