"""
test_training_paired.py
========================
fixup-ab, seam (i): the paired training job in the core (`Working/training/`),
UI-free, with a CLI — what makes RQ1 ("do cluster-derived labels produce a
classifier that generalises better than manually-derived labels?") answerable.

What is decided (QUESTIONS.md Q42 and Round 10, 2026-10-03) and pinned here:

* two arms trained IDENTICALLY, only the label source differs — arm A the human
  labels (`catalogue.manual_labels`' rule), arm B a dendrogram clustering at a
  chosen cut; a random forest for both;
* ONE clustering over the pooled TRAINING windows of every training channel —
  test windows take no part in forming the clusters;
* the cut and the cluster->human translation table are fixed in the recipe, and
  once a test score exists the cut cannot be changed on the same exam;
* windows: the labels' 600/200 grid, labelled-first non-overlap (`AA`); a
  blocked split by time WITHIN each channel with a gap of at least one window;
* yardstick (A): both arms scored on windows neither saw, against the human
  verdicts, arm B through its translation table — and the page says once that
  this is marked in arm A's own language;
* three exams, never pooled: (i) a later time block on the training channels,
  (ii) channels never trained on, (iii) the held-out recording — a slot that
  stays LOCKED; nothing here may read `M4_aug_concat_fs1.mat`;
* yardstick (B) is not this job's: a row that says "not yet labelled";
* `M2_aug_concat_fs1` and `_fs2` (one recording at two rates) never on opposite
  sides of a split.

Run from the project root:
    /c/ProgramData/anaconda3/python.exe -m pytest tests/test_training_paired.py -q
"""

import datetime as _dt
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

from Working.database import queries as q  # noqa: E402
from Working.database.schema import init_db  # noqa: E402

FS = 1.0
N = 36_000           # ten hours per channel at 1 Hz
L, GRID = 600, 200   # the labels' grid (`AA`)
SOURCE = "syn_aug_concat_fs1.mat"
TRAIN_CH = (0, 1, 2, 3)
EXAM_CH = (4,)
STAGES = ("fast_entropy",)   # four columns: fast enough for a test, enough to separate a drop


def _tw():
    from Working.training import windows as tw
    return tw


def _tp():
    from Working.training import paired as tp
    return tp


def _ts():
    from Working.training import store as ts
    return ts


def _signal(rng, interesting_starts):
    """Noise everywhere; a sharp drop and slow recovery inside every window the
    human called interesting, so a classifier has something real to learn."""
    x = 0.05 * rng.standard_normal(N)
    for s in interesting_starts:
        c = s + 250
        x[c:c + 250] -= np.linspace(3.0, 0.0, 250)
    return x


def _labels_for(ch):
    """Labels on the 600/200 grid, phase 200: one in three interesting, every
    fourth left unlabelled (time nobody looked at)."""
    out = []
    j = 0
    for s in range(200, N - L, L):
        if j % 4 != 3:
            out.append((s, s + L, "interesting" if (j + ch) % 3 == 0 else "not_interesting"))
        j += 1
    return out


def _make_store(tmp, source=SOURCE, channels=TRAIN_CH + EXAM_CH, deleted_one=False):
    db = os.path.join(tmp, "t.sqlite")
    conn = init_db(db)
    now = _dt.datetime.now().isoformat(timespec="seconds")
    for ch in channels:
        labels = _labels_for(ch)
        rng = np.random.default_rng(100 + ch)
        npy = os.path.join(tmp, f"{os.path.splitext(source)[0]}_CH{ch}.npy")
        np.save(npy, _signal(rng, [s for s, _, v in labels if v == "interesting"]))
        rid = q.insert_recording(conn, source, ch, FS, N, 0, npy)
        for s, e, v in labels:
            conn.execute(
                "INSERT INTO annotations (recording_id, start_idx, end_idx, verdict, source, created_at) "
                "VALUES (?, ?, ?, ?, 'imported_10min', ?)", (rid, s, e, v, now))
    if deleted_one:
        # a soft-deleted label must label nothing
        rid = conn.execute("SELECT id FROM recordings WHERE channel = 0").fetchone()[0]
        conn.execute(
            "INSERT INTO annotations (recording_id, start_idx, end_idx, verdict, source, created_at, deleted_at) "
            "VALUES (?, 2000 - 1800, 2000 - 1200, 'interesting', 'manual_ui', ?, ?)", (rid, now, now))
    conn.commit()
    return db, conn


@pytest.fixture
def tmp():
    d = tempfile.mkdtemp(prefix="ab_train_")
    yield d
    shutil.rmtree(d, ignore_errors=True)


@pytest.fixture
def store(tmp):
    db, conn = _make_store(tmp)
    yield tmp, db, conn
    conn.close()


def _split():
    return {"rule": "blocked_by_time", "n_blocks": 10, "test_frac": 0.2, "validation_frac": 0.1, "gap_windows": 1}


def _pooled(conn, **kw):
    tw = _tw()
    args = dict(length=L, grid=GRID, split=_split(), stages=STAGES)
    args.update(kw)
    return tw.build_pooled_set(conn, SOURCE, TRAIN_CH, exam_channels=EXAM_CH, **args)


def _recipe(ws_ref, k=3, translation=None, **kw):
    tp = _tp()
    args = dict(window_set=ws_ref, k=k, translation=translation,
                n_estimators=60, rf_shuffles=8, full_shuffles=0, bootstrap_n=200)
    args.update(kw)
    return tp.make_recipe(**args)


# ── the split: blocked by time within each channel, gap >= one window ───────

def test_the_grid_is_the_labels_grid():
    tw = _tw()
    starts = tw.grid_starts(3000, length=600, grid=200)
    assert starts[0] == 0 and np.all(np.diff(starts) == 200)
    assert starts[-1] + 600 <= 3000 < starts[-1] + 600 + 200


def test_the_split_is_blocked_by_time_and_the_last_blocks_are_test():
    tw = _tw()
    starts = np.arange(0, N - L + 1, L)
    sp = tw.blocked_split(starts, L, N, n_blocks=10, test_frac=0.2, validation_frac=0.1, gap_windows=1)
    roles = list(sp.roles)
    first_test = roles.index("test")
    # time order: train ... validation ... test, whole blocks, nothing shuffled
    order = {"train": 0, "validation": 1, "test": 2}
    seen = [order[r] for r in roles if r in order]
    assert seen == sorted(seen)
    assert all(r in ("test", "gap") for r in roles[first_test:])
    assert starts[first_test] >= 0.8 * N - L


def test_the_gap_between_roles_is_at_least_one_window():
    tw = _tw()
    starts = np.arange(0, N - L + 1, GRID)[::3]   # touching windows, stride 600
    sp = tw.blocked_split(starts, L, N, n_blocks=10, test_frac=0.2, validation_frac=0.1, gap_windows=1)
    kept = [(int(s), r) for s, r in zip(starts, sp.roles) if r != "gap"]
    for (s0, r0), (s1, r1) in zip(kept, kept[1:]):
        if r0 != r1:
            assert s1 - (s0 + L) >= L, f"{r0}@{s0} and {r1}@{s1} are closer than one window"
    assert (np.asarray(sp.roles) == "gap").sum() > 0, "touching windows across a boundary must be dropped, and counted"


def test_a_gap_shorter_than_one_window_is_refused():
    tw = _tw()
    with pytest.raises(ValueError, match="one window"):
        tw.blocked_split(np.arange(0, N - L + 1, L), L, N, n_blocks=10, test_frac=0.2, gap_windows=0)


def test_a_random_split_is_refused():
    tw = _tw()
    with pytest.raises(ValueError, match="random"):
        tw.check_split({"rule": "random", "test_frac": 0.2})


# ── the pooled window set across channels ───────────────────────────────────

def test_the_pooled_set_holds_every_labelled_window_of_every_channel(store):
    tmp, db, conn = store
    ps = _pooled(conn)
    t = ps.table
    assert set(t["channel"]) == set(TRAIN_CH + EXAM_CH)
    # every window carries a human label by AA's containment rule: 1 or 0, never -1
    assert set(t["label"].unique()) <= {0, 1}
    per_ch = t.groupby("channel").size()
    expected = sum(1 for _ in _labels_for(0))
    # every labelled window is in the set, or was dropped to keep the gap — and counted
    gap = {c["channel"]: c["dropped_for_gap"] for c in ps.meta["per_channel"]}
    assert all(per_ch[ch] + gap[ch] == expected for ch in per_ch.index)
    assert all(gap[ch] > 0 for ch in TRAIN_CH) and all(gap[ch] == 0 for ch in EXAM_CH)
    # the exam channels are never trained on
    assert set(t.loc[t["channel"].isin(EXAM_CH), "role"]) == {"exam"}
    assert {"train", "validation", "test"} <= set(t.loc[t["channel"].isin(TRAIN_CH), "role"])
    assert len(ps.features) == len(t)
    assert list(ps.features.columns) and "split" not in ps.features.columns


def test_a_soft_deleted_label_labels_nothing(tmp):
    db, conn = _make_store(tmp, deleted_one=True)
    from Adapters.catalogue_manual_labels import human_spans
    rid = conn.execute("SELECT id FROM recordings WHERE channel = 0").fetchone()[0]
    spans = human_spans(conn, rid)
    assert all(s[3] != "manual_ui" for s in spans), "a deleted annotation must not reach the labels"
    conn.close()


def test_the_held_out_recording_is_refused_even_when_unlocked(tmp, monkeypatch):
    import Working.config as cfg
    monkeypatch.setattr(cfg, "HELD_OUT_UNLOCK", True)
    db, conn = _make_store(tmp, source=cfg.HELD_OUT_RECORDING_FILE, channels=(0, 1))
    tw = _tw()
    with pytest.raises(tw.HeldOutRefused):
        tw.build_pooled_set(conn, cfg.HELD_OUT_RECORDING_FILE, (0,), exam_channels=(1,),
                            length=L, grid=GRID, split=_split(), stages=STAGES)
    conn.close()


def test_the_two_rates_of_one_recording_are_never_split_across_train_and_test():
    tw = _tw()
    with pytest.raises(tw.LeakageRefused, match="same recording"):
        tw.check_leakage(["M2_aug_concat_fs1.mat"], ["M2_aug_concat_fs2.mat"])
    tw.check_leakage(["M2_aug_concat_fs1.mat"], ["M2_aug_concat_fs1.mat"])   # same file both sides: fine


def test_the_pooled_set_round_trips_and_its_key_is_its_content(store):
    tmp, db, conn = store
    ps = _pooled(conn)
    d = os.path.join(tmp, "set")
    ps.save(d)
    back = _tw().PooledSet.load(d)
    assert back.key == ps.key
    assert back.table.equals(ps.table)
    assert np.allclose(back.features.to_numpy(), ps.features.to_numpy(), equal_nan=True)
    ps2 = _pooled(conn)
    assert ps2.key == ps.key, "the same labels, windows and split give the same key"


def test_saving_writes_one_window_sets_row_and_a_member_per_channel(store):
    tmp, db, conn = store
    ts = _ts()
    ps = _pooled(conn)
    ws_id = ts.save_window_set(conn, ps, os.path.join(tmp, "window_sets"), "ws_pooled")
    row = conn.execute("SELECT * FROM window_sets WHERE id = ?", (ws_id,)).fetchone()
    assert row["n_windows"] == len(ps.table)
    assert row["recipe_hash"] == ps.key
    split = json.loads(row["split_json"])
    assert split["rule"] == "blocked_by_time" and split["gap_windows"] == 1
    cov = json.loads(row["coverage_json"])
    assert cov["by_role"]["test"]["interesting"] + cov["by_role"]["test"]["not_interesting"] > 0
    members = conn.execute("SELECT * FROM window_set_members WHERE window_set_id = ? ORDER BY channel", (ws_id,)).fetchall()
    assert [m["channel"] for m in members] == list(TRAIN_CH + EXAM_CH)
    assert {m["role"] for m in members} == {"train", "exam"}
    assert sum(m["n_windows"] for m in members) == len(ps.table)
    # additive and idempotent
    init_db(db).close()
    assert conn.execute("SELECT COUNT(*) FROM window_set_members").fetchone()[0] == len(members)


# ── arm B: one clustering, training windows only ────────────────────────────

def test_propose_clusters_the_training_windows_only(store):
    tmp, db, conn = store
    tp = _tp()
    ps = _pooled(conn)
    a = tp.propose(ps, k_range=(2, 4))
    train_n = int((ps.table["role"] == "train").sum())
    assert a["n_windows_clustered"] == train_n
    # test and exam windows take no part: changing their features changes nothing
    ps.features.loc[ps.table["role"].isin(["test", "exam", "validation"]).to_numpy()] = 999.0
    b = tp.propose(ps, k_range=(2, 4))
    assert [r["sizes"] for r in a["by_k"]] == [r["sizes"] for r in b["by_k"]]
    for r in a["by_k"]:
        assert set(r) >= {"k", "silhouette", "sizes", "contingency", "translation", "purity"}
        assert sum(r["sizes"].values()) == train_n
        assert set(r["translation"].values()) <= {"interesting", "not_interesting"}
    assert a["suggested_k"] in (2, 3, 4)


def test_the_draft_cut_ignores_a_cut_whose_second_cluster_is_an_outlier_speck(store):
    # measured on M2_aug (2026-10-03): Ward splits off single-window outliers
    # first, and k = 2 (5,266 + 1) scored silhouette 0.95 — a perfect score for
    # a cut that separates nothing
    tmp, db, conn = store
    tp = _tp()
    ps = _pooled(conn)
    first_train = int(np.flatnonzero(ps.table["role"].to_numpy() == "train")[0])
    ps.features.iloc[first_train] = 1e6
    a = tp.propose(ps, k_range=(2, 4))
    k2 = a["by_k"][0]
    assert k2["k"] == 2 and k2["effective_k"] == 1 and k2["small_clusters"]
    assert a["suggested_k"] != 2


def test_a_recipe_translation_table_is_what_scores_arm_b(store):
    tmp, db, conn = store
    tp = _tp()
    ps = _pooled(conn)
    ref = {"name": "ws", "key": ps.key}
    everything_interesting = {str(c): "interesting" for c in (1, 2, 3)}
    res = tp.run_paired(_recipe(ref, k=3, translation=everything_interesting), ps)
    b = res["exams"]["i_later_block"]["arms"]["B"]
    # every test window predicted interesting: recall 1 for interesting, 0 for not_interesting
    assert b["per_class"]["interesting"]["recall"] == 1.0
    assert b["per_class"]["not_interesting"]["recall"] == 0.0
    assert res["cluster"]["translation_source"] == "recipe"


# ── the paired job ──────────────────────────────────────────────────────────

def test_both_arms_train_on_the_same_windows_and_differ_only_in_labels(store):
    tmp, db, conn = store
    tp = _tp()
    ps = _pooled(conn)
    res = tp.run_paired(_recipe({"name": "ws", "key": ps.key}), ps)
    arms = res["training"]
    assert arms["A"]["n_train"] == arms["B"]["n_train"] == int((ps.table["role"] == "train").sum())
    assert arms["A"]["window_ids"] == arms["B"]["window_ids"]
    assert arms["A"]["classifier"] == arms["B"]["classifier"]
    assert arms["A"]["label_source"] == "manual" and arms["B"]["label_source"] == "cluster"


def test_the_results_carry_every_number_the_pages_draw(store):
    tmp, db, conn = store
    tp = _tp()
    ps = _pooled(conn)
    res = tp.run_paired(_recipe({"name": "ws", "key": ps.key}), ps)
    ex = res["exams"]["i_later_block"]
    n_test = int((ps.table["role"] == "test").sum())
    assert ex["n_windows"] == n_test
    for arm in ("A", "B"):
        a = ex["arms"][arm]
        assert 0.0 <= a["macro_f1"] <= 1.0
        lo, hi = a["macro_f1_ci"]
        assert lo <= a["macro_f1"] <= hi
        assert "balanced_accuracy" in a
        assert np.asarray(a["confusion"]).sum() == n_test
        for cls in ("interesting", "not_interesting"):
            assert set(a["per_class"][cls]) >= {"precision", "recall", "f1", "n"}
        nul = a["null"]
        assert len(nul["draws"]) == 8 and 0.0 < nul["p"] <= 1.0
    p = ex["paired"]
    assert set(p) >= {"delta_f1", "delta_f1_ci", "mcnemar", "agreement", "per_class_delta"}
    ag = p["agreement"]
    assert ag["both_right"] + ag["only_a"] + ag["only_b"] + ag["both_wrong"] == n_test
    assert set(p["mcnemar"]) >= {"b", "c", "p"}
    assert {r["channel"] for r in ex["per_channel"]} == set(TRAIN_CH)
    # exam (ii): channels never trained on, reported separately
    ex2 = res["exams"]["ii_unseen_channels"]
    assert ex2["n_windows"] == int((ps.table["role"] == "exam").sum())
    assert {r["channel"] for r in ex2["per_channel"]} == set(EXAM_CH)
    # exam (iii): a slot that stays locked
    ex3 = res["exams"]["iii_held_out"]
    assert ex3["status"] == "locked" and "Settings" in ex3["reason"]
    # yardstick (B) is the Review prompt's
    assert res["yardstick_b"]["status"] == "not yet labelled"
    # the tilt is said once
    assert any("arm A's own language" in n for n in res["notes"])
    assert set(res["cluster"]) >= {"k", "linkage", "contingency", "purity", "translation", "sizes"}


def test_a_learnable_signal_beats_its_label_shuffle_null(store):
    tmp, db, conn = store
    tp = _tp()
    ps = _pooled(conn)
    res = tp.run_paired(_recipe({"name": "ws", "key": ps.key}, rf_shuffles=20), ps)
    a = res["exams"]["i_later_block"]["arms"]["A"]
    assert a["macro_f1"] > 0.8
    assert a["macro_f1"] > max(a["null"]["draws"])
    assert a["null"]["p"] <= 1.0 / 21 + 1e-9


def test_the_test_block_is_never_seen_in_training(store):
    tmp, db, conn = store
    tp = _tp()
    ps = _pooled(conn)
    res = tp.run_paired(_recipe({"name": "ws", "key": ps.key}), ps)
    train_ids = set(res["training"]["A"]["window_ids"])
    test_ids = set(np.flatnonzero(ps.table["role"].to_numpy() == "test").tolist())
    exam_ids = set(np.flatnonzero(ps.table["role"].to_numpy() == "exam").tolist())
    assert not (train_ids & test_ids) and not (train_ids & exam_ids)


def test_validate_names_each_before_launch_check(store):
    tmp, db, conn = store
    tp = _tp()
    ps = _pooled(conn)
    checks = {c["name"]: c for c in tp.validate(_recipe({"name": "ws", "key": ps.key}), ps)}
    for name in ("test block unseen", "gap >= window", "label-derived features off", "arms paired", "class counts"):
        assert name in checks, name
    assert checks["gap >= window"]["ok"] and checks["arms paired"]["ok"]
    # the test set here is far below 50 windows per class: warned, not refused
    assert checks["class counts"]["level"] == "warn"


def test_label_derived_features_are_refused(store):
    tmp, db, conn = store
    tw = _tw()
    with pytest.raises(ValueError, match="label"):
        tw.check_stages(("catch22", "rf"))


def test_the_estimate_routes_local_under_two_hours(store):
    tmp, db, conn = store
    tp = _tp()
    ps = _pooled(conn)
    est = tp.estimate(_recipe({"name": "ws", "key": ps.key}), ps)
    assert est["seconds"] > 0 and est["where"] == "local"
    big = tp.estimate(_recipe({"name": "ws", "key": ps.key}, rf_shuffles=10_000_000), ps)
    assert big["where"] == "slurm"


# ── recorded, reproducible, the cut frozen ──────────────────────────────────

def test_a_run_is_recorded_with_its_recipe_results_and_models(store):
    tmp, db, conn = store
    ts = _ts()
    ps = _pooled(conn)
    root = os.path.join(tmp, "training")
    ws_id = ts.save_window_set(conn, ps, os.path.join(tmp, "window_sets"), "ws_pooled")
    out = ts.run_and_record(conn, _recipe({"id": ws_id, "name": "ws_pooled", "key": ps.key}), root)
    run = conn.execute("SELECT r.*, c.config_json, c.config_hash FROM runs r JOIN configs c ON c.id = r.config_id "
                       "WHERE r.id = ?", (out["run_id"],)).fetchone()
    assert run["status"] == "completed"
    assert json.loads(run["config_json"])["kind"] == "paired_training"
    kinds = sorted(a["kind"] for a in conn.execute("SELECT kind FROM artifacts WHERE run_id = ?", (out["run_id"],)))
    assert kinds == ["model", "model", "other"]
    with open(out["results_path"], encoding="utf-8") as f:
        on_disk = json.load(f)
    assert on_disk["recipe_hash"] == run["config_hash"]
    listed = ts.list_runs(conn)
    assert [r["run_id"] for r in listed] == [out["run_id"]]
    got = ts.get_run(conn, out["run_id"])
    assert got["results"]["exams"]["i_later_block"]["arms"]["A"]["macro_f1"] == \
        on_disk["exams"]["i_later_block"]["arms"]["A"]["macro_f1"]


def test_the_same_recipe_reproduces_the_same_numbers(store):
    tmp, db, conn = store
    tp = _tp()
    ps = _pooled(conn)
    r = _recipe({"name": "ws", "key": ps.key})
    a = tp.run_paired(r, ps)
    b = tp.run_paired(r, ps)
    ea, eb = a["exams"]["i_later_block"], b["exams"]["i_later_block"]
    assert ea["arms"]["A"]["macro_f1"] == eb["arms"]["A"]["macro_f1"]
    assert ea["arms"]["B"]["null"]["draws"] == eb["arms"]["B"]["null"]["draws"]
    assert ea["paired"]["delta_f1_ci"] == eb["paired"]["delta_f1_ci"]


def test_once_a_test_score_exists_the_cut_cannot_change(store):
    tmp, db, conn = store
    ts = _ts()
    ps = _pooled(conn)
    root = os.path.join(tmp, "training")
    ws_id = ts.save_window_set(conn, ps, os.path.join(tmp, "window_sets"), "ws_pooled")
    ref = {"id": ws_id, "name": "ws_pooled", "key": ps.key}
    ts.run_and_record(conn, _recipe(ref, k=3), root)
    with pytest.raises(ts.CutFrozen, match="k = 3"):
        ts.run_and_record(conn, _recipe(ref, k=4), root)
    # the same cut may run again (a different seed, more shuffles)
    ts.run_and_record(conn, _recipe(ref, k=3, rf_shuffles=9), root)


def test_a_recipe_naming_a_different_set_than_the_one_on_disk_is_refused(store):
    tmp, db, conn = store
    ts = _ts()
    ps = _pooled(conn)
    ws_id = ts.save_window_set(conn, ps, os.path.join(tmp, "window_sets"), "ws_pooled")
    with pytest.raises(ValueError, match="key"):
        ts.run_and_record(conn, _recipe({"id": ws_id, "name": "ws_pooled", "key": "deadbeef"}), os.path.join(tmp, "tr"))


# ── metrics ─────────────────────────────────────────────────────────────────

def test_macro_f1_and_balanced_accuracy_match_sklearn():
    from sklearn.metrics import balanced_accuracy_score, f1_score
    from Working.training import metrics as tm
    rng = np.random.default_rng(0)
    y = rng.integers(0, 2, 200)
    p = np.where(rng.random(200) < 0.7, y, 1 - y)
    s = tm.classification_scores(y, p, classes=(0, 1), names=("not_interesting", "interesting"))
    assert s["macro_f1"] == pytest.approx(f1_score(y, p, average="macro"))
    assert s["balanced_accuracy"] == pytest.approx(balanced_accuracy_score(y, p))


def test_mcnemar_is_exact_on_the_discordant_pairs():
    from scipy.stats import binomtest
    from Working.training import metrics as tm
    a = np.array([1] * 30 + [0] * 5 + [1] * 50 + [0] * 15, dtype=bool)
    b = np.array([0] * 30 + [1] * 5 + [1] * 50 + [0] * 15, dtype=bool)
    m = tm.mcnemar(a, b)
    assert (m["b"], m["c"]) == (30, 5)
    assert m["p"] == pytest.approx(binomtest(5, 35, 0.5).pvalue)


# ── the command line answers Q1 before the pages exist ──────────────────────

def test_the_cli_saves_proposes_and_runs(store, capsys):
    tmp, db, conn = store
    from Working.training.__main__ import main
    root = os.path.join(tmp, "train_root")
    common = ["--db", db, "--root", root]
    assert main(["save-set", *common, "--source", SOURCE, "--channels", "0-3", "--exam-channels", "4",
                 "--stages", "fast_entropy", "--name", "ws_cli"]) == 0
    recipe_path = os.path.join(tmp, "recipe.json")
    assert main(["propose", *common, "--set", "ws_cli", "--k-range", "2-4", "--out", recipe_path]) == 0
    with open(recipe_path, encoding="utf-8") as f:
        draft = json.load(f)
    assert draft["kind"] == "paired_training" and draft["arms"]["B"]["translation"]
    draft["null"]["rf_shuffles"] = 5
    draft["classifier"]["n_estimators"] = 40
    with open(recipe_path, "w", encoding="utf-8") as f:
        json.dump(draft, f)
    assert main(["run", *common, "--recipe", recipe_path]) == 0
    out = capsys.readouterr().out
    assert "macro F1" in out and "arm A" in out and "arm B" in out and "ΔF1" in out


def test_nothing_under_working_training_imports_a_ui_library_or_fastapi():
    import ast
    banned = ("panel", "holoviews", "bokeh", "fastapi", "uvicorn", "starlette", "UI")
    root = os.path.join(PROJECT_ROOT, "Working", "training")
    files = [os.path.join(root, f) for f in os.listdir(root) if f.endswith(".py")]
    assert files
    for path in files:
        with open(path, encoding="utf-8") as f:
            tree = ast.parse(f.read())
        for node in ast.walk(tree):
            names = [a.name for a in node.names] if isinstance(node, ast.Import) else \
                [node.module] if isinstance(node, ast.ImportFrom) and node.module else []
            for n in names:
                assert n.split(".")[0] not in banned, f"{path} imports {n}"
