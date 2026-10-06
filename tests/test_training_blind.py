"""
test_training_blind.py
======================
fixup-AH: a BLIND interesting / not queue over a B.2 run's test and exam
windows, and the figures that compare the model with that blind human
(`Working.training.blind`; RQ1 version 2, "yardstick (B)").

Decided (the researcher, 2026-10-05), pinned here:

* the sample is drawn from the run's TEST and EXAM windows only, seeded, up to
  N (default 1,000, max 2,000), EVENLY per predicted cluster (within each exam),
  so rare clusters are not swamped; each window keeps its sampling weight
  (population / drawn) so population figures can be reweighted;
* a fraction (default 10 %) is shown TWICE, far apart, for self-agreement;
* the sample is FIXED and stored with the run (on disk, an `artifacts` row)
  before the first label, and it is the same sample for every model;
* the queue's items carry NOTHING that could tip the answer: no prediction, no
  cluster, no score, no class, no weight, no exam/role — and a second showing
  never carries the first showing's answer; the order is a seeded shuffle;
* the labels are ordinary human rows in `annotations` over the window's exact
  span, tagged with the queue (`source` + note + a link row), never a detection
  or an adjudication (rule 5); the model's calls stay in its parquet file;
* the first blind label is a score: it marks the exam scored in the run's
  results, which is what `shape_forest.frozen_for` reads (the freeze);
* "against a blind human", per exam, never pooled: confusion, macro F1 with the
  block-bootstrap CI, the model's *interesting* precision / recall / F1, Cohen's
  kappa, per-cluster rows (the check on the mapping), per scale and per
  recording, the label-shuffle null, self-agreement beside the figures;
* the manual-label models are a comparison line scored ONE ROW PER SCALE (never
  pooled), the 1- and 30-minute rows marked *outside its training scale*, the
  window fed AS IT IS (an n × n image resized to 224), contamination stated: a
  window overlapping an earlier human label is reported apart.

Run from the project root:
    /c/ProgramData/anaconda3/python.exe -m pytest tests/test_training_blind.py -q
"""

import json
import os
import shutil
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
#: what a blind queue's item may carry, and nothing else
ALLOWED_ITEM_KEYS = {"target_id", "unit", "showing", "recording_id", "channel", "start_idx", "end_idx",
                     "length", "fs", "duration_s", "judged", "verdict", "tags"}
FORBIDDEN = {"cluster", "class", "p_interesting", "score", "weight", "role", "exam", "prior_verdict",
             "first_showing", "repeat", "window", "stratum_size", "stratum_drawn", "model"}


def _bl():
    from Working.training import blind
    return blind


# ── the sample, on a synthetic prediction table (no database) ───────────────

def _preds(sizes_test=(400, 60, 8), sizes_exam=(300, 200, 5), seed=0):
    rng = np.random.default_rng(seed)
    rows = []
    for role, sizes in (("test", sizes_test), ("exam", sizes_exam)):
        for c, n in enumerate(sizes, start=1):
            for _ in range(n):
                rows.append({"recording_id": int(rng.integers(1, 9)), "source_file": AUG, "channel": int(rng.integers(0, 8)),
                             "start": int(rng.integers(0, 10 ** 6)), "length": int(rng.choice([60, 600, 1800])),
                             "fs": 1.0, "role": role, "cluster": c, "class": "interesting" if c == 2 else "not_interesting",
                             "p_interesting": float(rng.random())})
    for i in range(30):                               # validation windows are never sampled
        rows.append({**rows[i], "role": "validation"})
    df = pd.DataFrame(rows)
    df["orig_start"] = df["start"]
    df["scale_min"] = df["length"] / 60.0
    return df


def test_the_sample_is_even_per_predicted_cluster_within_each_exam_and_keeps_its_weights():
    bl = _bl()
    p = _preds()
    s = bl.draw_sample(p, n=300, repeat_frac=0.1, seed=0)
    firsts = s[~s["repeat"]]
    assert len(firsts) == 300 and firsts["window"].is_unique
    assert set(firsts["role"]) == {"test", "exam"}               # validation never sampled
    for role in ("test", "exam"):
        g = firsts[firsts["role"] == role]
        assert len(g) == 150                                      # the two exams share N equally
        counts = g["cluster"].value_counts().to_dict()
        # a cluster smaller than its share is taken whole; the rest is split evenly between the larger clusters
        if role == "test":                      # sizes 400 / 60 / 8: 8 and 60 whole, cluster 1 the rest
            assert counts == {1: 82, 2: 60, 3: 8}
        else:                                   # sizes 300 / 200 / 5: 5 whole, clusters 1 and 2 share 145
            assert counts[3] == 5 and abs(counts[1] - counts[2]) <= 1 and counts[1] + counts[2] == 145
    # weight = population of the stratum / windows drawn from it
    for (role, c), g in firsts.groupby(["role", "cluster"]):
        pop = int(((p["role"] == role) & (p["cluster"] == c)).sum())
        assert np.allclose(g["weight"], pop / len(g))
        assert (g["stratum_size"] == pop).all() and (g["stratum_drawn"] == len(g)).all()


def test_a_tenth_is_shown_twice_far_apart_and_the_order_is_a_seeded_shuffle():
    bl = _bl()
    p = _preds()
    s = bl.draw_sample(p, n=300, repeat_frac=0.1, seed=0)
    reps = s[s["repeat"]]
    assert len(reps) == 30 and len(s) == 330
    assert list(s["showing"]) == list(range(330))
    for _, r in reps.iterrows():
        first = s[(s["window"] == r["window"]) & ~s["repeat"]].iloc[0]
        assert int(r["first_showing"]) == int(first["showing"])
        assert int(r["showing"]) - int(first["showing"]) >= 30       # far apart
    # seeded: the same seed gives the same sample, another seed another order
    again = bl.draw_sample(p, n=300, repeat_frac=0.1, seed=0)
    assert list(again["start"]) == list(s["start"])
    other = bl.draw_sample(p, n=300, repeat_frac=0.1, seed=1)
    assert list(other["start"]) != list(s["start"])
    # the order does not track the model: clusters are interleaved, not blocked
    changes = int((s["cluster"].to_numpy()[1:] != s["cluster"].to_numpy()[:-1]).sum())
    assert changes > len(s) / 3


def test_the_sample_size_is_capped_at_two_thousand():
    bl = _bl()
    with pytest.raises(ValueError, match="2,000|2000"):
        bl.draw_sample(_preds(), n=2001)
    s = bl.draw_sample(_preds((5, 5, 5), (5, 5, 5)), n=1000, repeat_frac=0.0)
    assert len(s) == 30                                            # fewer windows than asked: all of them


# ── a real B.2 run on a small synthetic pool ───────────────────────────────

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


@pytest.fixture(scope="module")
def _run(tmp_path_factory):
    from Working.training import pool as tpool
    from Working.training import shape as sh
    from Working.training import shape_forest as sf
    from Working.training import store as ts
    tmp = tmp_path_factory.mktemp("blind")
    conn = init_db(str(tmp / "t.sqlite"))
    _add_recording(conn, str(tmp), AUG, 36_000, seed=0)
    _add_recording(conn, str(tmp), PLAIN, 18_000, seed=100)
    # an earlier (2025-26) human label on M2_aug CH0: blind windows over it are "not unseen" for the CNNs
    rid0 = conn.execute("SELECT id FROM recordings WHERE source_file = ? AND channel = 0", (AUG,)).fetchone()[0]
    q.insert_annotation(conn, rid0, 0, 36_000, "interesting", source="imported_10min")
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
    row, pool = tpool.load_pool(conn, pid)
    steps = [{"stage": "preprocessing", "algorithm": "window_pool", "params": {"pool": str(pid)}},
             {"stage": "preprocessing", "algorithm": "trace_shape", "params": {}},
             {"stage": "catalogue", "algorithm": "shape_cluster",
              "params": {"sample": 200, "seed": 0, "k": K, "mapping": json.dumps(_mapping())}}]
    recipe = sf.make_recipe({"id": int(row["id"]), "name": row["name"], "version": int(row["version"]), "key": pool.key},
                            {"id": 7, "name": "shape_clusters", "steps": steps}, n_estimators=30)
    out = sf.run_and_record(conn, recipe, str(tmp / "training"), tree_root=str(tmp / "trees"))
    conn.close()
    return {"db": tmp / "t.sqlite", "run_id": out["run_id"], "results_path": out["results_path"],
            "pool_key": pool.key, "recipe": recipe, "tmp": tmp}


@pytest.fixture
def env(_run, tmp_path):
    # each test gets its own database and its own copy of the run's directory
    shutil.copyfile(_run["db"], tmp_path / "t.sqlite")
    run_dir = os.path.dirname(_run["results_path"])
    copy_dir = tmp_path / "run"
    shutil.copytree(run_dir, copy_dir)
    conn = init_db(str(tmp_path / "t.sqlite"))
    for (aid, path) in conn.execute("SELECT id, path FROM artifacts WHERE run_id = ?", (_run["run_id"],)).fetchall():
        conn.execute("UPDATE artifacts SET path = ? WHERE id = ?", (os.path.join(str(copy_dir), os.path.basename(path)), aid))
    res_path = os.path.join(str(copy_dir), "results.json")
    with open(res_path, encoding="utf-8") as f:
        res = json.load(f)
    res["predictions_path"] = os.path.join(str(copy_dir), "predictions.parquet")
    with open(res_path, "w", encoding="utf-8") as f:
        json.dump(res, f)
    conn.commit()
    yield conn, _run, res_path
    conn.close()


def _queue(conn, run_id, n=60, repeat_frac=0.1, seed=0):
    return _bl().make_queue(conn, run_id, n=n, repeat_frac=repeat_frac, seed=seed)


def test_the_queue_is_a_blind_test_window_queue_writing_annotations_and_its_sample_is_stored_first(env):
    conn, run, _res = env
    from Working.review import queues as Q
    made = _queue(conn, run["run_id"])
    qrow = Q.get_queue(conn, made["queue_id"])
    assert qrow["source_kind"] == "blind-test" and qrow["unit"] == "test window"
    assert qrow["writes_to"] == "annotations" and qrow["blind"] == 1
    assert qrow["source_ref"] == str(run["run_id"])
    assert set(qrow["verdict_options"]) <= {"interesting", "not_interesting", "unsure", "artifact"}
    assert "seed" not in qrow["verdict_options"]
    # fixed and stored with the run before the first label
    assert os.path.isfile(made["sample_path"])
    paths = [r[0] for r in conn.execute("SELECT path FROM artifacts WHERE run_id = ?", (run["run_id"],))]
    assert made["sample_path"] in paths
    s = pd.read_parquet(made["sample_path"])
    assert set(s["role"]) <= {"test", "exam"} and (~s["repeat"]).sum() == 60 and s["repeat"].sum() == 6
    # the same sample for every model: asking again returns the same queue; a different N is refused
    again = _queue(conn, run["run_id"])
    assert again["queue_id"] == made["queue_id"] and again["created"] is False
    with pytest.raises(ValueError, match="fixed"):
        _queue(conn, run["run_id"], n=80)


def test_an_item_carries_nothing_that_could_tip_the_answer(env):
    conn, run, _res = env
    from Working.review import queues as Q
    made = _queue(conn, run["run_id"])
    items = Q.queue_items(conn, made["queue_id"], include_judged=True)
    assert len(items) == 66
    for it in items:
        assert set(it) <= ALLOWED_ITEM_KEYS, set(it) - ALLOWED_ITEM_KEYS
        assert not set(it) & FORBIDDEN
        assert it["unit"] == "test window" and it["end_idx"] - it["start_idx"] == it["length"]
        assert it["duration_s"] == pytest.approx(it["length"] / it["fs"])
    assert [it["target_id"] for it in items] == list(range(66))


def test_a_blind_label_is_an_ordinary_human_row_over_the_window_and_a_repeat_carries_no_earlier_answer(env):
    conn, run, _res = env
    from Working.review import queues as Q
    from Working.review import verdicts as V
    made = _queue(conn, run["run_id"])
    s = pd.read_parquet(made["sample_path"])
    rep = s[s["repeat"]].iloc[0]
    first = int(rep["first_showing"])
    n_det = conn.execute("SELECT COUNT(*) FROM detections").fetchone()[0]
    n_adj = conn.execute("SELECT COUNT(*) FROM adjudications").fetchone()[0]
    out = V.write_verdict(conn, made["queue_id"], first, "interesting")
    row = conn.execute("SELECT * FROM annotations WHERE id = ?", (out["row_id"],)).fetchone()
    w = s[s["showing"] == first].iloc[0]
    assert row["recording_id"] == int(w["recording_id"])
    assert row["start_idx"] == int(w["start"]) and row["end_idx"] == int(w["start"]) + int(w["length"])
    assert row["verdict"] == "interesting" and row["source"] == "blind_test_review"
    assert f"queue {made['queue_id']}" in row["note"]
    # rule 5: nothing machine-side was written, nothing human-side holds the model's call
    assert conn.execute("SELECT COUNT(*) FROM detections").fetchone()[0] == n_det
    assert conn.execute("SELECT COUNT(*) FROM adjudications").fetchone()[0] == n_adj
    assert "cluster" not in (row["note"] or "") and "p_interesting" not in (row["note"] or "")
    items = {it["target_id"]: it for it in Q.queue_items(conn, made["queue_id"], include_judged=True)}
    assert items[first]["judged"] and items[first]["verdict"] == "interesting"
    # the second showing of the SAME window is unjudged and carries no verdict
    assert items[int(rep["showing"])]["judged"] is False and items[int(rep["showing"])]["verdict"] is None
    # answering it writes its own row: two human observations of one span
    out2 = V.write_verdict(conn, made["queue_id"], int(rep["showing"]), "not_interesting")
    assert out2["row_id"] != out["row_id"]
    assert "second showing" in conn.execute("SELECT note FROM annotations WHERE id = ?", (out2["row_id"],)).fetchone()[0]
    # progress and resume
    c = Q.queue_counts(conn, made["queue_id"])
    assert c == {"total": 66, "judged": 2, "remaining": 64}
    assert len(Q.queue_items(conn, made["queue_id"])) == 64
    # undo withdraws the row (soft), the showing reads unjudged again, and it can be answered again
    V.undo_last(conn, made["queue_id"])
    assert conn.execute("SELECT deleted_at FROM annotations WHERE id = ?", (out2["row_id"],)).fetchone()[0]
    items = {it["target_id"]: it for it in Q.queue_items(conn, made["queue_id"], include_judged=True)}
    assert items[int(rep["showing"])]["judged"] is False
    out3 = V.write_verdict(conn, made["queue_id"], int(rep["showing"]), "unsure")
    assert out3["row_id"] not in (out["row_id"], out2["row_id"])
    # seed is not one of this queue's words
    with pytest.raises(ValueError):
        V.write_verdict(conn, made["queue_id"], 3, "seed")


def test_the_first_blind_label_is_a_score_and_freezes_the_cut_and_the_mapping(env):
    conn, run, res_path = env
    from Working.review import verdicts as V
    from Working.training import shape_forest as sf
    from Working.training.store import CutFrozen
    made = _queue(conn, run["run_id"])
    assert sf.frozen_for(conn, run["pool_key"]) is None
    s = pd.read_parquet(made["sample_path"])
    first_exam_i = int(s[(s["role"] == "test") & ~s["repeat"]]["showing"].iloc[0])
    V.write_verdict(conn, made["queue_id"], first_exam_i, "not_interesting")
    with open(res_path, encoding="utf-8") as f:
        res = json.load(f)
    assert res["exams"][sf.EXAM_I]["status"] == "scored"           # what the freeze reads
    fz = sf.frozen_for(conn, run["pool_key"])
    assert fz and fz["run_id"] == run["run_id"] and fz["k"] == K
    with pytest.raises(CutFrozen, match=f"run {run['run_id']}"):
        sf.check_frozen(conn, run["pool_key"], K + 1, _mapping(K + 1))


def _label_all(conn, queue_id, sample, rule):
    from Working.review import verdicts as V
    for _, r in sample.iterrows():
        V.write_verdict(conn, queue_id, int(r["showing"]), rule(r))


def test_against_a_blind_human_per_exam_never_pooled(env):
    conn, run, _res = env
    bl = _bl()
    from Working.training import metrics as tm
    made = _queue(conn, run["run_id"], n=80, repeat_frac=0.1)
    s = pd.read_parquet(made["sample_path"])

    # the human agrees with the model except on every 4th first showing; repeats agree with the first answer except one
    flip = set(s[~s["repeat"]]["window"].iloc[::4])
    repeated = set(s[s["repeat"]]["window"])
    unsure_window = int(next(w for w in s[~s["repeat"]]["window"] if int(w) not in repeated))
    odd_repeat = int(s[s["repeat"]]["window"].iloc[0])

    def rule(r):
        c = r["class"]
        if int(r["window"]) in flip:
            c = "interesting" if c == "not_interesting" else "not_interesting"
        if r["repeat"] and int(r["window"]) == odd_repeat:
            c = "interesting" if c == "not_interesting" else "not_interesting"
        if int(r["window"]) == unsure_window:
            return "unsure"
        return c
    _label_all(conn, made["queue_id"], s, rule)

    sc = bl.score(conn, run["run_id"], n_boot=200, n_null=200, seed=0)
    assert set(sc["exams"]) == {"i_later_block", "ii_unseen_channels"}
    for ek, role in (("i_later_block", "test"), ("ii_unseen_channels", "exam")):
        ex = sc["exams"][ek]
        firsts = s[(~s["repeat"]) & (s["role"] == role)].copy()
        firsts["human"] = [rule(r) for _, r in firsts.iterrows()]
        scored = firsts[firsts["human"].isin(["interesting", "not_interesting"])]
        assert ex["n_scored"] == len(scored)
        assert ex["excluded"]["unsure"] == int((firsts["human"] == "unsure").sum())
        want = tm.classification_scores(scored["human"], scored["class"], ("interesting", "not_interesting"))
        assert ex["macro_f1"] == pytest.approx(want["macro_f1"])
        assert ex["confusion"] == want["confusion"]                    # rows: the human · columns: the model
        lo, hi = ex["macro_f1_ci"]
        assert lo is not None and lo <= ex["macro_f1"] + 1e-9 and hi >= ex["macro_f1"] - 1e-9
        assert ex["kappa"] == pytest.approx(tm.cohen_kappa(scored["human"], scored["class"], ("interesting", "not_interesting")))
        assert set(ex["interesting"]) >= {"precision", "recall", "f1", "f1_ci"}
        # per cluster: how many of each cluster the human called interesting — the check on the mapping
        pc = {r["cluster"]: r for r in ex["per_cluster"]}
        for c, g in scored.groupby("cluster"):
            assert pc[int(c)]["n"] == len(g)
            assert pc[int(c)]["human_interesting"] == int((g["human"] == "interesting").sum())
            assert pc[int(c)]["class"] == _mapping()["clusters"][str(int(c))]["class"]
        assert {r["scale_min"] for r in ex["per_scale"]} == {float(x) for x in scored["scale_min"].unique()}
        assert {r["recording"] for r in ex["per_recording"]} == set(scored["source_file"])
        nl = ex["null"]
        assert nl["n"] == 200 and 0 < nl["p"] <= 1 and nl["mean"] is not None
        assert "self_agreement" in ex                                   # beside every figure
        assert "reweighted" in ex and ex["reweighted"]["note"]
    sa = sc["self_agreement"]
    assert sa["n_pairs"] == 8 and sa["n_scored_pairs"] >= 6
    assert sa["agree"] == sa["n_scored_pairs"] - 1                      # the one repeat answered differently


def test_cohen_kappa_is_the_textbook_value():
    from Working.training import metrics as tm
    # 50 windows: both yes 20, both no 15, a-yes b-no 5, a-no b-yes 10 → po 0.70, pe 0.50, kappa 0.40
    a = ["y"] * 20 + ["n"] * 15 + ["y"] * 5 + ["n"] * 10
    b = ["y"] * 20 + ["n"] * 15 + ["n"] * 5 + ["y"] * 10
    assert tm.cohen_kappa(a, b, ("y", "n")) == pytest.approx(0.4)
    assert tm.cohen_kappa(["y", "y"], ["y", "y"], ("y", "n")) == pytest.approx(1.0)


def test_the_disagreements_are_listed_both_ways_with_the_model_call_beside_the_human(env):
    conn, run, _res = env
    bl = _bl()
    made = _queue(conn, run["run_id"], n=40, repeat_frac=0.0)
    s = pd.read_parquet(made["sample_path"])
    _label_all(conn, made["queue_id"], s, lambda r: "interesting" if r["class"] == "not_interesting" else "not_interesting")
    yes_no = bl.disagreements(conn, run["run_id"], "i_later_block", "model_yes_human_no")
    no_yes = bl.disagreements(conn, run["run_id"], "i_later_block", "model_no_human_yes")
    t = s[(s["role"] == "test") & ~s["repeat"]]
    assert len(yes_no) == int((t["class"] == "interesting").sum())
    assert len(no_yes) == int((t["class"] == "not_interesting").sum())
    for d in yes_no:
        assert d["model_class"] == "interesting" and d["human"] == "not_interesting"
        assert {"showing", "recording_id", "start", "length", "cluster", "p_interesting"} <= set(d)


# ── the comparison line: the manual-label models, one row per scale ────────

def test_a_window_is_fed_to_the_reference_models_as_it_is_an_n_by_n_image_resized_to_224():
    bl = _bl()
    x = np.sin(np.linspace(0, 6, 1800))
    for kind in ("GASF", "GADF", "fusion"):
        img = bl.reference_image(x, kind)
        assert img.size == (1800, 1800)                                  # nothing resampled before the image
    rec = bl.reference_image(x[:60], "recurrence")
    assert rec.size == (60 - 2 * 4, 60 - 2 * 4)                          # m = 3, tau = 4 samples: fixed in samples
    t = bl.reference_tensor(x[:60], "GASF")
    assert tuple(t.shape[-2:]) == (224, 224)


def test_the_reference_line_is_one_row_per_model_per_scale_never_pooled_with_contamination_stated(env):
    conn, run, _res = env
    bl = _bl()
    made = _queue(conn, run["run_id"], n=60, repeat_frac=0.0)
    s = pd.read_parquet(made["sample_path"])
    _label_all(conn, made["queue_id"], s, lambda r: r["class"])
    lab = bl.labels(conn, made["queue_id"])
    # contamination: windows over the earlier label on M2_aug CH0 are flagged, M2 windows never are
    flags = bl.contaminated(conn, lab)
    rid0 = conn.execute("SELECT id FROM recordings WHERE source_file = ? AND channel = 0", (AUG,)).fetchone()[0]
    assert flags[(lab["recording_id"] == rid0).to_numpy()].all()
    assert not flags[(lab["source_file"] == PLAIN).to_numpy()].any()
    # injected probabilities stand in for the networks: one that agrees with the human, one constant
    rng = np.random.default_rng(0)
    good = np.where(lab["class"] == "interesting", 0.9, 0.1) + rng.normal(0, 0.01, len(lab))
    probs = pd.DataFrame({"GASF_cnn": good, "fusion_cnn": np.ones(len(lab))})
    meta = {"GASF_cnn": {"file": "MODELS/GASF_cnn.pth", "image": "GASF"},
            "fusion_cnn": {"file": "MODELS/fusion_cnn.pth", "image": "fusion"}}
    rows = bl.score_reference(lab, probs, meta, contaminated=flags)
    gasf = [r for r in rows if r["model"] == "GASF_cnn"]
    assert sorted(r["scale_min"] for r in gasf) == sorted({float(x) for x in lab["scale_min"].unique()})
    for r in gasf:
        assert r["outside_training_scale"] is (r["scale_min"] != 10.0)
        assert "as it is" in r["how_fed"] and "224" in r["how_fed"]
        assert "contamination" in r and r["contamination"]
        for ek in ("i_later_block", "ii_unseen_channels"):
            e = r["exams"][ek]
            assert set(e) >= {"all", "no_earlier_label"}
            if e["all"]["n"]:      # a slice holding one class says so rather than printing half a score
                assert e["all"]["macro_f1"] is not None or e["all"]["one_class"]
                assert e["all"]["agreement"] is not None
    fus = [r for r in rows if r["model"] == "fusion_cnn"]
    assert fus and all(r["status"] == "not scored" and "constant" in r["reason"] for r in fus)
    rec_rows = bl.score_reference(lab, pd.DataFrame({"recurrence_cnn": good}),
                                  {"recurrence_cnn": {"file": "MODELS/recurrence_cnn.pth", "image": "recurrence"}},
                                  contaminated=flags)
    assert all("not scale-free" in r["embedding"] for r in rec_rows)


def test_the_reference_checkpoints_name_the_fusion_problem():
    bl = _bl()
    names = [m["model"] for m in bl.REFERENCE_MODELS]
    assert {"GASF_cnn", "GADF_cnn", "recurrence_cnn", "fusion_cnn", "catch22_rf_prelabeled"} <= set(names)


def test_blind_imports_no_ui_library():
    import ast
    import Working.training.blind as m
    with open(m.__file__, encoding="utf-8") as f:
        tree = ast.parse(f.read())
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module.split(".")[0])
    assert not names & {"panel", "holoviews", "bokeh", "fastapi", "uvicorn", "matplotlib"}


# ── fixup-smoke2 (AI's question 2, option (a)): one blind sample per pool ───
#
# The researcher's blind labels for the forest's run also score a later run on the
# same pool (a CNN): the sample is drawn ONCE per pool from the test / exam windows,
# a later run's scores use the labels already written, its per-cluster rows use ITS
# OWN predicted clusters, and the sampling weights are unchanged.

def _later_run(conn, run, tmp):
    """A second B.2 run on the same pool, as the CNN arm's would be: the same windows, its own calls (every
    window's cluster moved on by one, its class through the same frozen mapping)."""
    from Working.database import runs as R
    from Working.training import shape_forest as sf
    _p, res = sf._results_of(conn, run["run_id"])
    recipe = {**run["recipe"], "kind": "shape_cluster_cnn", "model": {"name": "cnn", "image": "fusion"}}
    config_id, _h = R.get_or_create_config(conn, recipe)
    rec = conn.execute("SELECT recording_id, span_start, span_end FROM runs WHERE id = ?", (run["run_id"],)).fetchone()
    rid = R.insert_run(conn, config_id, rec[0], rec[1], rec[2], status="completed", name="B.2 CNN (later)")
    d = os.path.join(str(tmp), "later_run")
    os.makedirs(d, exist_ok=True)
    preds = pd.read_parquet(res["predictions_path"])
    preds["cluster"] = (preds["cluster"].astype(int) % K) + 1
    preds["class"] = [_mapping()["clusters"][str(int(c))]["class"] for c in preds["cluster"]]
    preds["p_interesting"] = (preds["class"] == "interesting").astype(float)
    pred_path = os.path.join(d, "predictions.parquet")
    preds.to_parquet(pred_path, index=False)
    res2 = {**res, "predictions_path": pred_path,
            "exams": {ek: {**v, "status": sf.PREDICTED} for ek, v in res["exams"].items()}}
    with open(os.path.join(d, "results.json"), "w", encoding="utf-8") as fh:
        json.dump(res2, fh)
    R.insert_artifact(conn, rid, "other", os.path.join(d, "results.json"))
    conn.commit()
    return rid, preds


def test_a_later_run_on_the_same_pool_is_served_the_pools_one_blind_sample(env, tmp_path):
    conn, run, _res = env
    bl = _bl()
    made = _queue(conn, run["run_id"])
    later, _preds = _later_run(conn, run, tmp_path)
    again = _queue(conn, later)
    assert again["queue_id"] == made["queue_id"] and again["created"] is False
    assert again["sample_path"] == made["sample_path"] and again["shared_with"] == run["run_id"]
    assert bl.queue_for_run(conn, later)["id"] == made["queue_id"]
    # drawn once per pool: no second queue, no second sample beside the later run
    assert conn.execute("SELECT COUNT(*) FROM review_queues WHERE source_kind = 'blind-test'").fetchone()[0] == 1
    assert not os.path.exists(os.path.join(str(tmp_path), "later_run", bl.SAMPLE_FILE))
    # still fixed: the later run cannot ask the pool for a different sample
    with pytest.raises(bl.SampleFixed):
        _queue(conn, later, n=80)


def test_a_later_runs_scores_use_the_labels_already_written_and_its_own_clusters(env, tmp_path):
    conn, run, _res = env
    bl = _bl()
    from Working.training import metrics as tm
    made = _queue(conn, run["run_id"], n=80, repeat_frac=0.1)
    s = pd.read_parquet(made["sample_path"])
    # the human agrees with the FIRST run everywhere
    _label_all(conn, made["queue_id"], s, lambda r: str(r["class"]))
    n_labels = conn.execute("SELECT COUNT(*) FROM annotations WHERE source = 'blind_test_review'").fetchone()[0]
    later, preds = _later_run(conn, run, tmp_path)

    first = bl.score(conn, run["run_id"], n_boot=50, n_null=50, seed=0)
    sc = bl.score(conn, later, n_boot=50, n_null=50, seed=0)
    # no new label was asked for or written: the later run reads the same answers
    assert conn.execute("SELECT COUNT(*) FROM annotations WHERE source = 'blind_test_review'").fetchone()[0] == n_labels
    assert sc["queue_id"] == made["queue_id"] and sc["shared"]["owner_run_id"] == run["run_id"]
    key = ["recording_id", "start", "length"]
    own = s.drop(columns=["cluster", "class", "p_interesting"]).merge(preds[key + ["cluster", "class"]], on=key, how="left")
    for ek, role in (("i_later_block", "test"), ("ii_unseen_channels", "exam")):
        ex, ex1 = sc["exams"][ek], first["exams"][ek]
        assert ex["n_labelled"] == ex1["n_labelled"] and ex["n_scored"] == ex1["n_scored"]
        assert ex1["macro_f1"] == pytest.approx(1.0)                   # the human agreed with the first run
        f = own[(~own["repeat"]) & (own["role"] == role)]
        human = s.set_index("showing").loc[f["showing"], "class"].to_numpy(dtype=object)   # what was answered
        want = tm.classification_scores(human, f["class"].to_numpy(dtype=object), ("interesting", "not_interesting"))
        assert ex["confusion"] == want["confusion"]                    # the human against the LATER run's calls
        assert ex["macro_f1"] == pytest.approx(want["macro_f1"])
        # per cluster: the later run's own predicted clusters
        pc = {r["cluster"]: r for r in ex["per_cluster"]}
        for c, g in f.groupby("cluster"):
            assert pc[int(c)]["n_sample"] == len(g)
            assert pc[int(c)]["population"] == int(((preds["role"] == role) & (preds["cluster"] == c)).sum())
        # the weights are the sample's own, unchanged
        assert ex["reweighted"]["accuracy"] is not None
    # the first run's figures are untouched by the later one
    assert bl.score(conn, run["run_id"], n_boot=50, n_null=50, seed=0)["exams"]["i_later_block"]["confusion"] == \
        first["exams"]["i_later_block"]["confusion"]
    # and the disagreements are the later run's calls against the same answers
    for d in bl.disagreements(conn, later, "i_later_block", "model_yes_human_no"):
        row = own[own["showing"] == d["showing"]].iloc[0]
        assert d["model_class"] == row["class"] == "interesting" and d["human"] == "not_interesting"
        assert d["cluster"] == int(row["cluster"])
