"""
test_training_pool.py
=====================
fixup-af: unlabelled window sets at three scales, and the UI-free function that
combines saved sets into a POOL with a region-first train / validation / test /
exam plan laid over it (RQ1 version 2, `docs/rq_roundA/RQ1-…` "New scope,
version 2"). The page that combines is `AG`'s; this pins the core it calls.

What is decided (the researcher, 2026-10-05) and pinned here:

* manual labels are IGNORED when a set is built: windows are cut from the
  signal, labelled or not;
* one set per recording per scale (1 / 10 / 30 minutes), on a non-overlapping
  grid at that scale, artifact spans excluded (the human `artifact` label and
  what Settings › Channels & events excludes), saved with its scale and counts
  and NO roles;
* the train / test fence belongs to the POOL: roles are assigned to stretches
  of time on a channel BEFORE any window is placed, the same stretches for
  every scale; a window belongs to a role only if it lies wholly inside one
  stretch — straddlers and windows in a gap are dropped and counted;
* blocked by time (`blocked_split`), exam channels by choice, and a
  *hold out pack* shortcut (CH1–4 A, CH5–8 B, CH9–12 C, CH13–16 D);
* default rule: within a scale no two windows overlap; across scales overlap is
  allowed but never across roles; exact duplicates removed. Second rule: no
  overlap across scales either — the SMALLER scale wins;
* a set on a recording the plan does not cover is refused with the reason;
* the held-out file is refused even with the unlock; the fs1 / fs2 pair of one
  recording never on opposite sides, now checked across every file of a pool;
* the saved pool is itself a `window_sets` row with its members, its plan and
  its key; loading it again gives the same windows and the same key.

Run from the project root:
    /c/ProgramData/anaconda3/python.exe -m pytest tests/test_training_pool.py -q
"""

import datetime as _dt
import json
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
AUG2 = "syn_aug_concat_fs2.mat"     # the same recording at 2 Hz
PLAIN = "syn_concat_fs1.mat"        # 5 h at 1 Hz, 16 channels — different data
N_AUG, N_PLAIN = 36_000, 18_000


def _pool():
    from Working.training import pool as tpool
    return tpool


def _ts():
    from Working.training import store as ts
    return ts


def _add_recording(conn, tmp, source, n, fs=1.0, channels=range(16), seed=0):
    stem = os.path.splitext(source)[0]
    d = os.path.join(tmp, "channels", stem)
    os.makedirs(d, exist_ok=True)
    ids = {}
    for ch in channels:
        rng = np.random.default_rng(seed + ch)
        npy = os.path.join(d, f"CH{ch}.npy")
        np.save(npy, 0.05 * rng.standard_normal(int(n)))
        ids[ch] = q.insert_recording(conn, source, ch, fs, int(n), 0, npy)
    conn.commit()
    return ids


def _annotate(conn, rid, a, b, verdict, deleted=False):
    now = _dt.datetime.now().isoformat(timespec="seconds")
    conn.execute("INSERT INTO annotations (recording_id, start_idx, end_idx, verdict, source, created_at, deleted_at) "
                 "VALUES (?, ?, ?, ?, 'manual_ui', ?, ?)", (rid, int(a), int(b), verdict, now, now if deleted else None))
    conn.commit()


@pytest.fixture
def store(tmp_path):
    db = str(tmp_path / "t.sqlite")
    conn = init_db(db)
    ids = {AUG: _add_recording(conn, str(tmp_path), AUG, N_AUG, seed=0),
           PLAIN: _add_recording(conn, str(tmp_path), PLAIN, N_PLAIN, seed=100)}
    yield conn, ids, tmp_path
    conn.close()


def _six(conn, tmp_path):
    """The researcher's six: two recordings × 1 / 10 / 30 minutes, saved."""
    tpool, ts = _pool(), _ts()
    out = []
    for src in (AUG, PLAIN):
        for scale in (1, 10, 30):
            u = tpool.build_unlabelled_set(conn, src, scale_min=scale)
            out.append(ts.save_window_set(conn, u, str(tmp_path / "window_sets"),
                                          f"ws_{os.path.splitext(src)[0]}_{scale}min"))
    return out


# ── schema ──────────────────────────────────────────────────────────────────

def test_the_new_tables_are_additive_and_init_db_stays_idempotent(tmp_path):
    db = str(tmp_path / "s.sqlite")
    init_db(db).close()
    conn = init_db(db)   # twice: no error, nothing duplicated
    names = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    assert {"window_sets", "window_set_members", "window_set_channels", "window_pool_members"} <= names
    cols = {r[1] for r in conn.execute("PRAGMA table_info(window_set_channels)")}
    assert {"window_set_id", "recording_id", "n_windows", "counts_json"} <= cols
    cols = {r[1] for r in conn.execute("PRAGMA table_info(window_pool_members)")}
    assert {"pool_id", "member_set_id", "position", "n_offered", "n_kept", "counts_json"} <= cols
    conn.close()


# ── an unlabelled set ───────────────────────────────────────────────────────

def test_a_set_cuts_a_non_overlapping_grid_at_its_scale_and_ignores_manual_labels(store):
    conn, ids, _ = store
    tpool = _pool()
    for scale, per_ch in ((1, 600), (10, 60), (30, 20)):
        u = tpool.build_unlabelled_set(conn, AUG, scale_min=scale)
        t = u.table
        assert len(t) == 16 * per_ch
        assert set(t["length"]) == {scale * 60}
        for _ch, g in t.groupby("channel"):
            s = np.sort(g["start"].to_numpy())
            assert (np.diff(s) >= scale * 60).all(), "no two windows of one set overlap"
        assert "role" not in t.columns and "label" not in t.columns, "a saved set is just windows: no roles, no labels"
        assert u.meta["scale_min"] == scale and u.meta["length"] == scale * 60

    # a human label changes nothing: windows are cut from the signal, labelled or not
    before = tpool.build_unlabelled_set(conn, AUG, scale_min=10)
    _annotate(conn, ids[AUG][0], 1200, 1800, "interesting")
    _annotate(conn, ids[AUG][0], 3000, 3600, "not_interesting")
    after = tpool.build_unlabelled_set(conn, AUG, scale_min=10)
    assert before.key == after.key and len(before.table) == len(after.table)


def test_artifact_spans_are_left_out_and_counted(store):
    conn, ids, _ = store
    tpool = _pool()
    from Working.registration.settings import put_settings
    # a human artifact on CH1 at 1000–1100 s: one 10-minute window (600–1200) is lost
    _annotate(conn, ids[AUG][0], 1000, 1100, "artifact")
    # a soft-deleted artifact excludes nothing
    _annotate(conn, ids[AUG][1], 1000, 1100, "artifact", deleted=True)
    # Settings › Channels & events: an excluded span on every channel, 2–3 h (6 windows per channel at 10 min),
    # and an event marked "show on plots" that excludes nothing
    stem = os.path.splitext(AUG)[0]
    put_settings(conn, "channels-events", {f"events.added.{stem}": [
        {"id": "ev-x", "recording": stem, "t0_h": 2.0, "t1_h": 3.0, "kind": "watering", "channels": "all",
         "effect": "exclude span", "note": "", "added": "5 Oct"},
        {"id": "ev-s", "recording": stem, "t0_h": 5.0, "t1_h": 6.0, "kind": "light", "channels": "all",
         "effect": "show on plots", "note": "", "added": "5 Oct"},
    ]})
    u = tpool.build_unlabelled_set(conn, AUG, scale_min=10)
    c = u.meta["counts"]
    assert c["grid_windows"] == 16 * 60
    assert c["artifact_human"] == 1
    assert c["excluded_by_settings"] == 16 * 6
    assert c["n_windows"] == 16 * 60 - 1 - 16 * 6 == len(u.table)
    ch0 = u.table[u.table["channel"] == 0]["start"].to_numpy()
    assert 600 not in ch0 and 0 in ch0 and 1200 in ch0
    assert not ((ch0 >= 7200 - 599) & (ch0 < 10800)).any()

    # the exclusion can be turned off, and then nothing is dropped for it
    off = tpool.build_unlabelled_set(conn, AUG, scale_min=10, exclude_artifacts=False)
    assert len(off.table) == 16 * 60 and off.meta["counts"]["artifact_human"] == 0


def test_a_mark_bad_event_excludes_its_channel_from_its_start_to_the_end(store):
    conn, _ids, _ = store
    tpool = _pool()
    from Working.registration.settings import put_settings
    stem = os.path.splitext(AUG)[0]
    put_settings(conn, "channels-events", {f"events.added.{stem}": [
        {"id": "ev-b", "recording": stem, "t0_h": 8.0, "t1_h": None, "kind": "electrode", "channels": "CH3",
         "effect": "exclude · mark channel bad", "note": "", "added": "5 Oct"}]})
    u = tpool.build_unlabelled_set(conn, AUG, scale_min=10)
    ch2 = u.table[u.table["channel"] == 2]["start"].to_numpy()
    assert ch2.max() + 600 <= 8 * 3600 and u.meta["counts"]["excluded_by_settings"] == 12


def test_a_large_supply_is_sampled_with_a_seed(store):
    conn, _ids, _ = store
    tpool = _pool()
    a = tpool.build_unlabelled_set(conn, AUG, scale_min=1, sample=500, seed=7)
    b = tpool.build_unlabelled_set(conn, AUG, scale_min=1, sample=500, seed=7)
    c = tpool.build_unlabelled_set(conn, AUG, scale_min=1, sample=500, seed=8)
    assert len(a.table) == 500 and a.meta["counts"]["sampled_out"] == 16 * 600 - 500
    assert a.key == b.key and a.table["start"].tolist() == b.table["start"].tolist()
    assert a.key != c.key
    assert a.meta["sample"] == 500 and a.meta["seed"] == 7


def test_the_held_out_recording_is_refused_even_with_the_unlock(store, monkeypatch):
    conn, _ids, tmp = store
    tpool = _pool()
    from Working import config
    from Working.training import windows as tw
    _add_recording(conn, str(tmp), config.HELD_OUT_RECORDING_FILE, 3600, channels=(0,))
    monkeypatch.setattr(config, "HELD_OUT_UNLOCK", True)
    with pytest.raises(tw.HeldOutRefused):
        tpool.build_unlabelled_set(conn, config.HELD_OUT_RECORDING_FILE, scale_min=10)
    with pytest.raises(tw.HeldOutRefused):
        tpool.plan_for(conn, [config.HELD_OUT_RECORDING_FILE])


def test_a_saved_set_is_a_window_sets_row_with_its_scale_and_counts_and_no_roles(store):
    conn, _ids, tmp = store
    tpool, ts = _pool(), _ts()
    u = tpool.build_unlabelled_set(conn, AUG, scale_min=30)
    ws_id = ts.save_window_set(conn, u, str(tmp / "window_sets"), "ws_aug_30min")
    row = conn.execute("SELECT * FROM window_sets WHERE id = ?", (ws_id,)).fetchone()
    assert row["recording_id"] is None and row["window_length"] == 1800 and row["stride"] == 1800
    assert row["n_windows"] == len(u.table) == 16 * 20
    assert row["recipe_hash"] == u.key
    cov = json.loads(row["coverage_json"])
    assert cov["set_kind"] == "unlabelled" and cov["scale_min"] == 30
    assert cov["counts"]["n_windows"] == 16 * 20 and "artifact_human" in cov["counts"]
    split = json.loads(row["split_json"])
    assert split["rule"] == "none" and not ({"train", "validation", "test", "exam"} & set(split))
    # its channels are named, without a role
    chans = conn.execute("SELECT * FROM window_set_channels WHERE window_set_id = ?", (ws_id,)).fetchall()
    assert len(chans) == 16 and sum(r["n_windows"] for r in chans) == 16 * 20
    # it is NOT a paired-job set: Models › Launch's member rows stay for train/exam sets
    assert conn.execute("SELECT COUNT(*) FROM window_set_members WHERE window_set_id = ?", (ws_id,)).fetchone()[0] == 0
    # read back: the same windows, the same key; a changed file is refused
    row2, back = tpool.load_set(conn, {"id": ws_id})
    assert back.key == u.key and back.table["start"].tolist() == u.table["start"].tolist()
    path = os.path.join(row["path"], "unlabelled_windows.npz")
    with np.load(path) as z:
        d = {k: z[k] for k in z.files}
    d["start"] = d["start"] + 1
    np.savez_compressed(path, **d)
    with pytest.raises(ValueError, match="key"):
        tpool.load_set(conn, {"id": ws_id})


# ── the region plan ─────────────────────────────────────────────────────────

def test_hold_out_pack_makes_the_whole_pack_the_exam_on_every_recording(store):
    conn, _ids, _ = store
    tpool = _pool()
    assert tpool.PACKS == {"A": (0, 1, 2, 3), "B": (4, 5, 6, 7), "C": (8, 9, 10, 11), "D": (12, 13, 14, 15)}
    plan = tpool.plan_for(conn, [AUG, PLAIN], hold_out_pack="D")
    for ident in plan["recordings"]:
        assert plan["recordings"][ident]["exam_channels"] == [12, 13, 14, 15]
    assert plan["hold_out_pack"] == "D"
    with pytest.raises(ValueError, match="pack"):
        tpool.plan_for(conn, [AUG], hold_out_pack="E")


def test_roles_are_stretches_of_time_blocked_as_ab_with_a_gap_the_same_for_every_scale(store):
    conn, _ids, _ = store
    tpool = _pool()
    plan = tpool.plan_for(conn, [AUG], hold_out_pack="D")   # defaults: 10 blocks, test 0.2, validation 0.1, gap 30 min
    assert plan["gap_s"] == 1800 and plan["n_blocks"] == 10
    rec = plan["recordings"][tpool.recording_identity(AUG)]
    st = [(s["role"], s["start_s"], s["end_s"]) for s in rec["stretches"]]
    assert st == [("train", 0.0, 25200.0), ("validation", 27000.0, 28800.0), ("test", 30600.0, 36000.0)]
    # one role per window: wholly inside a stretch, else dropped as in a gap or straddling a boundary
    starts = np.array([0, 24600, 24900, 25200, 27000, 28200, 30600, 35400])
    roles = tpool.assign_roles(plan, AUG, 0, starts, np.full(len(starts), 600), 1.0)
    assert roles.tolist() == ["train", "train", "straddle", "gap", "validation", "validation", "test", "test"]
    exam = tpool.assign_roles(plan, AUG, 13, starts, np.full(len(starts), 600), 1.0)
    assert set(exam.tolist()) == {"exam"}


def test_a_set_on_a_recording_the_plan_does_not_cover_is_refused_with_the_reason(store):
    conn, _ids, tmp = store
    tpool, ts = _pool(), _ts()
    sid = ts.save_window_set(conn, tpool.build_unlabelled_set(conn, PLAIN, scale_min=30), str(tmp / "ws"), "plain30")
    plan = tpool.plan_for(conn, [AUG])
    with pytest.raises(tpool.PlanRefused, match="syn_concat"):
        tpool.combine(conn, [sid], plan)


# ── combining ───────────────────────────────────────────────────────────────

def test_combining_the_six_counts_recording_by_scale_by_role_and_keeps_roles_apart(store):
    conn, _ids, tmp = store
    tpool = _pool()
    six = _six(conn, tmp)
    plan = tpool.plan_for(conn, [AUG, PLAIN], hold_out_pack="D")
    pool = tpool.combine(conn, six, plan)
    t = pool.table
    assert {"set_id", "recording_id", "source_file", "channel", "start", "length", "scale_min", "role"} <= set(t.columns)
    assert set(t["role"]) == {"train", "validation", "test", "exam"}
    # pack D is exam and nothing else; nothing on pack D is trained on
    assert set(t.loc[t["channel"].isin([12, 13, 14, 15]), "role"]) == {"exam"}
    assert "exam" not in set(t.loc[~t["channel"].isin([12, 13, 14, 15]), "role"])
    # the 30-minute AUG windows of a training channel: 14 train, 1 validation, 3 test, 2 in a gap (worked by hand)
    g = t[(t["source_file"] == AUG) & (t["channel"] == 0) & (t["scale_min"] == 30)]
    assert g["role"].value_counts().to_dict() == {"train": 14, "test": 3, "validation": 1}
    by = {(r["recording"], r["scale_min"], r["role"]): r["n"] for r in pool.meta["counts"]["by"]}
    assert by[(AUG, 30, "train")] == 12 * 14 and by[(AUG, 30, "exam")] == 4 * 20
    assert by[(AUG, 1, "test")] == 12 * 90 and by[(AUG, 1, "train")] == 12 * 420
    d = pool.meta["counts"]["dropped"]
    assert d["gap"] > 0 and d["duplicate"] == 0 and d["overlap_within_scale"] == 0
    # across scales overlap is allowed (a 1-min window inside a 30-min one), never across roles
    checks = tpool.check_pool(pool)
    assert checks["windows inside another role's stretch"] == 0
    assert checks["overlaps across roles"] == 0
    assert checks["overlaps across scales (allowed)"] > 0


def test_exact_duplicates_and_within_scale_overlaps_are_removed_and_counted(store):
    conn, _ids, tmp = store
    tpool, ts = _pool(), _ts()
    root = str(tmp / "ws")
    a = ts.save_window_set(conn, tpool.build_unlabelled_set(conn, AUG, scale_min=10, channels=[0]), root, "a10")
    # the same windows saved again under another name: every one an exact duplicate
    b = ts.save_window_set(conn, tpool.build_unlabelled_set(conn, AUG, scale_min=10, channels=[0]), root, "b10")
    # a 10-minute set on a grid shifted by 5 minutes: every window overlaps two of `a`'s
    c = ts.save_window_set(conn, tpool.build_unlabelled_set(conn, AUG, scale_min=10, channels=[0], offset=300),
                           root, "c10")
    plan = tpool.plan_for(conn, [AUG])
    only_a = tpool.combine(conn, [a], plan)
    pool = tpool.combine(conn, [a, b, c], plan)
    d = pool.meta["counts"]["dropped"]
    assert len(pool.table) == len(only_a.table), "the first set listed wins"
    assert d["duplicate"] == len(only_a.table)
    assert d["overlap_within_scale"] > 0
    members = {m["name"]: m for m in pool.meta["members"]}
    assert members["a10"]["n_kept"] == len(only_a.table) and members["b10"]["n_kept"] == 0
    assert members["c10"]["n_kept"] == 0


def test_the_strict_rule_allows_no_overlap_across_scales_and_the_smaller_scale_wins(store):
    conn, _ids, tmp = store
    tpool = _pool()
    six = _six(conn, tmp)
    plan = tpool.plan_for(conn, [AUG, PLAIN], hold_out_pack="D")
    pool = tpool.combine(conn, six, plan, rule="no_overlap", sample={1: 300}, seed=3)
    assert pool.meta["rule"] == "no_overlap"
    checks = tpool.check_pool(pool)
    assert checks["overlaps across scales (allowed)"] == 0 and checks["overlaps across roles"] == 0
    d = pool.meta["counts"]["dropped"]
    assert d["overlap_across_scales"] > 0
    # the sampled 1-minute windows all survive: the smaller scale wins
    assert (pool.table["scale_min"] == 1).sum() == 300
    assert d["sampled_out"] > 0
    assert pool.meta["sample"] == {"1": 300} and pool.meta["seed"] == 3


def test_sampling_per_scale_is_seeded_and_counted(store):
    conn, _ids, tmp = store
    tpool = _pool()
    six = _six(conn, tmp)
    plan = tpool.plan_for(conn, [AUG, PLAIN], hold_out_pack="D")
    full = tpool.combine(conn, six, plan)
    n1 = int((full.table["scale_min"] == 1).sum())
    a = tpool.combine(conn, six, plan, sample={1: 1000}, seed=11)
    b = tpool.combine(conn, six, plan, sample={1: 1000}, seed=11)
    assert int((a.table["scale_min"] == 1).sum()) == 1000
    assert a.meta["counts"]["dropped"]["sampled_out"] == n1 - 1000
    assert a.key == b.key and a.key != full.key
    assert int((a.table["scale_min"] == 30).sum()) == int((full.table["scale_min"] == 30).sum())


def test_an_artifact_labelled_after_a_set_was_saved_is_still_left_out_of_the_pool(store):
    conn, ids, tmp = store
    tpool, ts = _pool(), _ts()
    sid = ts.save_window_set(conn, tpool.build_unlabelled_set(conn, AUG, scale_min=10, channels=[0]), str(tmp / "ws"), "a")
    plan = tpool.plan_for(conn, [AUG])
    before = tpool.combine(conn, [sid], plan)
    _annotate(conn, ids[AUG][0], 1000, 1100, "artifact")
    after = tpool.combine(conn, [sid], plan)
    assert len(after.table) == len(before.table) - 1
    assert after.meta["counts"]["dropped"]["artifact"] == 1


def test_a_labelled_set_with_its_own_split_is_combined_as_plain_windows(store):
    conn, ids, tmp = store
    tpool, ts = _pool(), _ts()
    from Working.training import windows as tw
    for k, s in enumerate(range(200, 30_000, 600)):
        _annotate(conn, ids[AUG][0], s, s + 600, "interesting" if k % 3 == 0 else "not_interesting")
        _annotate(conn, ids[AUG][1], s, s + 600, "interesting" if k % 3 == 1 else "not_interesting")
    ps = tw.build_pooled_set(conn, AUG, [0], exam_channels=[1], stages=("fast_entropy",))
    sid = ts.save_window_set(conn, ps, str(tmp / "ws"), "labelled")
    plan = tpool.plan_for(conn, [AUG])
    pool = tpool.combine(conn, [sid], plan)
    assert len(pool.table) > 0 and set(pool.table["scale_min"]) == {10}
    # the pool's roles come from the plan, not from the set's own split
    for ch, g in pool.table.groupby("channel"):
        starts = g["start"].to_numpy()
        want = tpool.assign_roles(plan, AUG, int(ch), starts, np.full(len(starts), 600), 1.0)
        assert g["role"].tolist() == want.tolist()
    # channel 1 was the set's own exam channel; the plan holds out no channel, so here it is split by time
    assert set(pool.table.loc[pool.table["channel"] == 1, "role"]) <= {"train", "validation", "test"}


def test_the_fs1_fs2_pair_shares_its_stretches_and_never_sits_on_opposite_sides(store):
    conn, _ids, tmp = store
    tpool, ts = _pool(), _ts()
    _add_recording(conn, str(tmp), AUG2, 2 * N_AUG, fs=2.0, seed=0)
    root = str(tmp / "ws")
    a = ts.save_window_set(conn, tpool.build_unlabelled_set(conn, AUG, scale_min=10, channels=[0]), root, "f1")
    b = ts.save_window_set(conn, tpool.build_unlabelled_set(conn, AUG2, scale_min=10, channels=[0]), root, "f2")
    plan = tpool.plan_for(conn, [AUG, AUG2])
    assert list(plan["recordings"]) == [tpool.recording_identity(AUG)], "one recording at two rates is one plan entry"
    # the fs2 copy of a 10-minute window IS the fs1 window (one recording's time): an overlap within a scale
    same = tpool.combine(conn, [a, b], plan)
    assert set(same.table["source_file"]) == {AUG}
    assert same.meta["counts"]["dropped"]["overlap_within_scale"] > 0
    # at another scale the fs2 file's windows stay, and sit in the SAME role as the fs1 windows they overlap
    c = ts.save_window_set(conn, tpool.build_unlabelled_set(conn, AUG2, scale_min=30, channels=[0]), root, "f2_30")
    pool = tpool.combine(conn, [a, c], plan)
    t = pool.table
    m1, m2 = (t["source_file"] == AUG).to_numpy(), (t["source_file"] == AUG2).to_numpy()
    assert m1.any() and m2.any()
    for _, w in t[m2].iterrows():
        a_s, b_s = w["start"] / 2.0, (w["start"] + w["length"]) / 2.0
        inside = t[m1 & (t["start"].to_numpy() >= a_s) & (t["start"].to_numpy() + t["length"].to_numpy() <= b_s)]
        assert len(inside) == 3 and set(inside["role"]) == {w["role"]}
    checks = tpool.check_pool(pool)
    assert checks["overlaps across roles"] == 0 and checks["overlaps across scales (allowed)"] > 0
    # a pool whose rows were tampered so the pair disagrees at one time is refused
    bad = pool.table.copy()
    i = bad.index[(bad["source_file"] == AUG2) & (bad["role"] == "train")][0]
    bad.loc[i, "role"] = "test"
    from Working.training import windows as tw
    with pytest.raises(tw.LeakageRefused):
        tpool.check_pool(tpool.Pool(table=bad, meta=pool.meta))


def test_a_saved_pool_is_a_window_sets_row_with_members_plan_and_key_and_loads_back_the_same(store):
    conn, _ids, tmp = store
    tpool, ts = _pool(), _ts()
    six = _six(conn, tmp)
    plan = tpool.plan_for(conn, [AUG, PLAIN], hold_out_pack="D")
    pool = tpool.combine(conn, six, plan, sample={1: 2000}, seed=1)
    pid = ts.save_window_set(conn, pool, str(tmp / "window_sets"), "pool_six_packD")
    row = conn.execute("SELECT * FROM window_sets WHERE id = ?", (pid,)).fetchone()
    assert row["n_windows"] == len(pool.table) and row["recipe_hash"] == pool.key
    split = json.loads(row["split_json"])
    assert split["rule"] == "region_first" and split["plan"]["hold_out_pack"] == "D"
    for r in ("train", "validation", "test", "exam"):
        assert split[r] == int((pool.table["role"] == r).sum())
    cov = json.loads(row["coverage_json"])
    assert cov["set_kind"] == "pool" and cov["rule"] == "within_scale" and sorted(cov["scales_min"]) == [1, 10, 30]
    mem = conn.execute("SELECT * FROM window_pool_members WHERE pool_id = ? ORDER BY position", (pid,)).fetchall()
    assert [m["member_set_id"] for m in mem] == list(six)
    assert sum(m["n_kept"] for m in mem) == len(pool.table)
    row2, back = tpool.load_pool(conn, {"id": pid})
    assert back.key == pool.key
    pd.testing.assert_frame_equal(back.table.reset_index(drop=True), pool.table.reset_index(drop=True),
                                  check_dtype=False)


def test_every_saved_set_is_listed_for_the_pool_block_with_its_kind_and_scale(store):
    conn, _ids, tmp = store
    tpool = _pool()
    six = _six(conn, tmp)
    rows = tpool.list_sets(conn)
    got = {r["id"]: r for r in rows}
    assert set(six) <= set(got)
    for sid in six:
        assert got[sid]["kind"] == "unlabelled" and got[sid]["scale_min"] in (1, 10, 30)
        assert got[sid]["source_files"] and got[sid]["n_windows"] > 0


# ── the command line ────────────────────────────────────────────────────────

def test_the_cli_builds_the_three_scales_and_combines_with_a_pack_held_out(store, capsys):
    conn, _ids, tmp = store
    from Working.training.__main__ import main
    db = conn.execute("PRAGMA database_list").fetchone()[2]
    root = str(tmp / "cli")
    for src in (AUG, PLAIN):
        assert main(["build-sets", "--db", db, "--root", root, "--source", src, "--scales", "1,10,30"]) == 0
    out = capsys.readouterr().out
    assert "1 min" in out and "30 min" in out and "artifact" in out
    names = [r["name"] for r in conn.execute("SELECT name FROM window_sets ORDER BY id")]
    assert len(names) == 6
    assert main(["combine", "--db", db, "--root", root, "--sets", ",".join(names), "--hold-out-pack", "D",
                 "--sample", "1=3000", "--seed", "0", "--name", "pool_cli"]) == 0
    out = capsys.readouterr().out
    assert "train" in out and "exam" in out and "duplicate" in out and "overlap" in out
    assert "windows inside another role's stretch: 0" in out
    assert "key" in out
    assert main(["show-pool", "--db", db, "--root", root, "--pool", "pool_cli"]) == 0
    again = capsys.readouterr().out
    key = conn.execute("SELECT recipe_hash FROM window_sets WHERE name = 'pool_cli'").fetchone()[0]
    assert key in again


def test_nothing_under_training_imports_a_ui_library():
    import ast
    path = os.path.join(PROJECT_ROOT, "Working", "training", "pool.py")
    tree = ast.parse(open(path, encoding="utf-8").read())
    mods = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            mods |= {a.name.split(".")[0] for a in n.names}
        elif isinstance(n, ast.ImportFrom) and n.module:
            mods.add(n.module.split(".")[0])
    assert not mods & {"fastapi", "uvicorn", "panel", "holoviews", "bokeh", "starlette", "pydantic"}
