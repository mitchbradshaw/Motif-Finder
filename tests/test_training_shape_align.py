"""
test_training_shape_align.py
============================
fixup-ag, continuation (the researcher, 2026-10-05): how a grid window is LINED
UP before its shape is compared. Trace shape gains two options:

* `align`: `grid` (the window as the pool cut it) or `centre` (re-cut, the same
  length, centred on its LARGEST SWING);
* `detrend`: `off` or `linear` (the window's least-squares straight line removed
  before the Library's resample + z-normalise).

The largest swing is defined so a single-sample glitch cannot be it: the window's
straight-line trend is removed, a running median of k samples (k odd, at least 5,
about a sixtieth of the window) is taken, and the swing is the sample where that
departs furthest from its own median.

Centring respects the fence: a re-cut window stays wholly inside its own role's
stretch on its own channel, inside the recording, and touches no artifact span;
where the centre cannot be reached it is shifted as far as allowed (CLAMPED) and
counted. Two windows that centre onto the same event are near-duplicates: the
later is dropped and counted; a smaller overlap within a scale is counted.

Run from the project root:
    /c/ProgramData/anaconda3/python.exe -m pytest tests/test_training_shape_align.py -q
"""

import datetime as _dt
import os
import shutil
import sys

import numpy as np
import pandas as pd
import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for p in (PROJECT_ROOT, os.path.join(PROJECT_ROOT, "webui")):
    if p not in sys.path:
        sys.path.insert(0, p)

from Working.database import queries as q  # noqa: E402
from Working.database.schema import init_db  # noqa: E402

AUG = "syn_aug_concat_fs1.mat"
PLAIN = "syn_concat_fs1.mat"


def _sh():
    from Working.training import shape
    return shape


def _add_recording(conn, tmp, source, n, seed=0):
    d = os.path.join(tmp, "channels", os.path.splitext(source)[0])
    os.makedirs(d, exist_ok=True)
    for ch in range(16):
        rng = np.random.default_rng(seed + ch)
        t = np.arange(int(n))
        # a slow drift plus a sharp drop every 40 minutes, off the 1/10/30-minute grids
        x = 0.01 * rng.standard_normal(int(n)) + 0.3 * (t / n) - 0.5 * np.exp(-(((t - 777) % 2400) / 15.0) ** 2)
        npy = os.path.join(d, f"CH{ch}.npy")
        np.save(npy, x)
        rid = q.insert_recording(conn, source, ch, 1.0, int(n), 0, npy)
        conn.execute("UPDATE recordings SET units = 'V' WHERE id = ?", (rid,))
    conn.commit()


@pytest.fixture(scope="module")
def _built(tmp_path_factory):
    from Working.training import pool as tpool
    from Working.training import store as ts
    tmp = tmp_path_factory.mktemp("align")
    conn = init_db(str(tmp / "t.sqlite"))
    _add_recording(conn, str(tmp), AUG, 36_000, seed=0)
    _add_recording(conn, str(tmp), PLAIN, 18_000, seed=100)
    # an artifact span, labelled AFTER nothing: the pool leaves out windows touching it; a re-cut must not reach it
    rid = conn.execute("SELECT id FROM recordings WHERE source_file = ? AND channel = 0", (AUG,)).fetchone()[0]
    now = _dt.datetime.now().isoformat(timespec="seconds")
    conn.execute("INSERT INTO annotations (recording_id, start_idx, end_idx, verdict, source, created_at) "
                 "VALUES (?, 5000, 5300, 'artifact', 'manual_ui', ?)", (rid, now))
    conn.commit()
    ids = []
    for src in (AUG, PLAIN):
        for scale in (1, 10, 30):
            u = tpool.build_unlabelled_set(conn, src, scale_min=scale)
            ids.append(ts.save_window_set(conn, u, str(tmp / "window_sets"), f"ws_{os.path.splitext(src)[0]}_{scale}min"))
    plan = tpool.plan_for(conn, [AUG, PLAIN], hold_out_pack="D")
    pool = tpool.combine(conn, ids, plan, sample={1: 400, 10: 400, 30: 400}, seed=0)
    conn.close()
    return tmp / "t.sqlite", pool


@pytest.fixture
def pooled(_built, tmp_path):
    shutil.copyfile(_built[0], tmp_path / "t.sqlite")
    conn = init_db(str(tmp_path / "t.sqlite"))
    yield conn, _built[1]
    conn.close()


# ── the largest swing ───────────────────────────────────────────────────────

def test_the_largest_swing_is_not_a_single_sample_glitch_and_not_the_drift():
    sh = _sh()
    t = np.arange(600, dtype=float)
    seg = 3.0 * t / 600                                   # a drift: its largest departure from the median is an edge
    seg = seg - 1.0 * np.exp(-((t - 420) / 12.0) ** 2)    # the event
    seg[120] += 8.0                                       # a one-sample glitch, far larger than the event
    i = sh.swing_index(seg)
    assert abs(i - 420) <= 10, i
    assert sh.swing_width(60) >= 5 and sh.swing_width(60) % 2 == 1
    assert sh.swing_width(1800) % 2 == 1 and sh.swing_width(1800) >= 29
    assert "running median" in sh.SWING_RULE and "straight-line" in sh.SWING_RULE


# ── the fence ───────────────────────────────────────────────────────────────

def test_a_recut_window_is_shifted_as_far_as_its_stretch_and_the_artifacts_allow_and_counted():
    sh = _sh()
    lo, hi = sh.allowed_interval(2000, 600, stretch=(1000, 5000), n_samples=10_000, spans=[(3000, 3100), (100, 900)])
    assert (lo, hi) == (1000, 3000)
    start, clamped = sh.recut_start(2000, 600, swing=550, lo=lo, hi=hi)   # wants 2250, may go up to 2400
    assert (start, clamped) == (2250, False)
    start, clamped = sh.recut_start(2000, 600, swing=599, lo=lo, hi=hi)   # wants 2299
    assert (start, clamped) == (2299, False)
    start, clamped = sh.recut_start(2300, 600, swing=599, lo=lo, hi=hi)   # wants 2599: past 2400
    assert (start, clamped) == (2400, True)
    start, clamped = sh.recut_start(1100, 600, swing=0, lo=lo, hi=hi)     # wants 800: before the stretch
    assert (start, clamped) == (1000, True)


def test_centring_keeps_every_window_inside_its_own_stretch_channel_and_clear_of_artifacts(pooled):
    conn, pool = pooled
    sh = _sh()
    from Working.training import pool as tpool
    frame = sh.pool_frame(sh.pool_windowset(pool))
    assert {"stretch_a", "stretch_b"} <= set(frame.columns)
    out = sh.trace_shapes(conn, frame, align="centre", detrend="off", noise_floor=False)
    f = out.frame
    assert (f["start"] >= f["stretch_a"]).all() and (f["start"] + f["length"] <= f["stretch_b"]).all()
    plan = pool.meta["plan"]
    for (sf, ch), g in f.groupby(["source_file", "channel"]):
        roles = tpool.assign_roles(plan, sf, ch, g["start"].to_numpy(), g["length"].to_numpy(), float(g["fs"].iloc[0]))
        assert list(roles) == list(g["role"]), (sf, ch)
    rid0 = conn.execute("SELECT id FROM recordings WHERE source_file = ? AND channel = 0", (AUG,)).fetchone()[0]
    g0 = f[f["recording_id"] == rid0]
    assert not ((g0["start"] < 5300) & (g0["start"] + g0["length"] > 5000)).any()
    rc = out.meta["recut"]
    assert out.meta["align"] == "centre" and out.meta["detrend"] == "off"
    assert rc["n_moved"] > 0 and rc["n_clamped"] >= 0
    assert rc["n_near_duplicate"] >= 0 and rc["n_overlap_within_scale"] >= 0
    assert len(f) + rc["n_near_duplicate"] == out.meta["n_in"] - out.meta["under_floor"]["n"]
    assert (f["orig_start"] >= 0).all()
    # the 30-minute windows (three in four hold a drop) mostly sit centred on it now
    thirty = f[f["scale_min"] == 30.0]
    assert float(np.median(np.abs(thirty["peak_frac"] - 0.5))) < 0.1


def test_check_recut_refuses_a_window_outside_its_stretch(pooled):
    conn, pool = pooled
    sh = _sh()
    from Working.training.windows import LeakageRefused
    out = sh.trace_shapes(conn, sh.pool_frame(sh.pool_windowset(pool)), align="centre", noise_floor=False)
    sh.check_recut(conn, out.frame)            # the guarantee holds
    bad = out.frame.copy()
    bad.loc[0, "start"] = int(bad.loc[0, "stretch_b"]) - int(bad.loc[0, "length"]) + 1
    with pytest.raises(LeakageRefused, match="stretch"):
        sh.check_recut(conn, bad)


def test_two_windows_centred_onto_one_event_are_near_duplicates_dropped_and_counted():
    sh = _sh()
    f = pd.DataFrame({"recording_id": [1, 1, 1, 1], "scale_min": [10.0] * 4, "length": [600] * 4,
                      "start": [1000, 1100, 1400, 3000]})
    keep, n_dup, n_overlap = sh.near_duplicates(f)
    assert list(keep) == [True, False, True, True]        # 1100 overlaps 1000 by 500 of 600: a duplicate
    assert n_dup == 1 and n_overlap == 1                  # 1400 overlaps 1000 by 200: counted, kept


# ── detrend ─────────────────────────────────────────────────────────────────

def test_linear_detrend_removes_the_straight_line_before_the_librarys_resample_and_normalise(pooled):
    conn, pool = pooled
    sh = _sh()
    from scipy.signal import detrend
    from Working.library.grouping.methods import ward
    out = sh.trace_shapes(conn, sh.pool_frame(sh.pool_windowset(pool)), detrend="linear", noise_floor=False)
    rec = {int(r[0]): r[1] for r in conn.execute("SELECT id, npy_path FROM recordings")}
    row = out.frame.iloc[3]
    raw = np.load(rec[int(row["recording_id"])])[int(row["start"]):int(row["start"]) + int(row["length"])]
    want = ward.shape_vectors([detrend(raw, type="linear")], sh.RESAMPLE_LENGTH)[0]
    assert np.allclose(out.vectors[int(row["shape_row"])], want, atol=1e-4)
    # the raw range stays the raw trace's
    assert row["raw_range_mv"] == pytest.approx(float(np.ptp(raw)) * 1000.0, rel=1e-6)
    assert out.meta["detrend"] == "linear"
    ramp = sh.shape_of(np.linspace(0.0, 5.0, 600), detrend="linear")
    assert np.allclose(ramp, 0.0, atol=1e-6)


def test_each_combination_is_its_own_shape_set_and_round_trips(pooled, tmp_path):
    conn, pool = pooled
    sh = _sh()
    frame = sh.pool_frame(sh.pool_windowset(pool))
    keys = set()
    for align in ("grid", "centre"):
        for det in ("off", "linear"):
            s = sh.trace_shapes(conn, frame, align=align, detrend=det, noise_floor=False)
            keys.add(s.key)
            path = s.save(str(tmp_path / f"{align}_{det}"))
            back = sh.ShapeSet.load(path)
            assert back.key == s.key and back.meta["align"] == align and back.meta["detrend"] == det
            for c in ("orig_start", "noise_mv", "clamped"):
                assert list(back.frame[c]) == list(s.frame[c]), c
    assert len(keys) == 4


def test_the_defaults_are_named_once_and_the_block_offers_both_options():
    sh = _sh()
    from Adapters.registry import discover_adapters, get_adapter
    discover_adapters()
    p = {s.name: s for s in get_adapter("preprocessing.trace_shape").params}
    # fixup-am: peak and trough join grid and centre; the default stays centre (bit for bit)
    assert set(p["align"].choices) == {"grid", "centre", "peak", "trough"} and p["align"].default == sh.DEFAULT_ALIGN
    assert set(p["detrend"].choices) == {"off", "linear"} and p["detrend"].default == sh.DEFAULT_DETREND


# ── the noise floor per dataset, and the histogram it is chosen from ─────────

def test_the_page_ships_a_raw_range_histogram_per_recording_and_scale_with_that_recordings_floor(pooled):
    conn, pool = pooled
    sh = _sh()
    from Working.registration.settings import put_settings
    from server.serialize import to_payload
    put_settings(conn, "datasets", {"meta.syn_aug_concat_fs1.noise_floor": 0.5})
    out = sh.trace_shapes(conn, sh.pool_frame(sh.pool_windowset(pool)), align="centre", detrend="linear")
    assert out.meta["floors"][AUG] == {"floor_mv": 0.5, "from": "Settings › Datasets"}
    assert out.meta["floors"][PLAIN]["floor_mv"] == pytest.approx(0.1)
    ws = sh.frame_windowset(out.frame, "x.npz")
    p = to_payload("windowset", ws, {**out.meta, "shape_file": "x.npz", "shape_key": out.key}, {})
    s = p["shape"]
    assert s["align"] == "centre" and s["detrend"] == "linear" and "recut" in s and s["swing_rule"]
    by = s["raw_range_by"]
    assert set(by) == {AUG, PLAIN}
    assert set(by[AUG]["scales"]) == {"1", "10", "30"} and by[AUG]["floor_mv"] == 0.5
    h = by[AUG]["scales"]["10"]
    assert h["log"] is True and len(h["edges"]) == len(h["counts"]) + 1
    # the bins are shared, so the small multiples can be compared by eye
    assert by[AUG]["scales"]["1"]["edges"] == by[PLAIN]["scales"]["30"]["edges"]


# ── the proposal is cached per tree ─────────────────────────────────────────

def test_the_cut_proposal_is_cached_beside_its_tree(pooled, tmp_path):
    conn, pool = pooled
    sh = _sh()
    s = sh.trace_shapes(conn, sh.pool_frame(sh.pool_windowset(pool)))
    tree = sh.cluster_shapes(s, sample=200, seed=0)
    d = tree.save(str(tmp_path / "tree"))
    a, cached_a = sh.propose_cached(tree, s, d)
    assert cached_a is False and os.path.isfile(os.path.join(d, "propose.json"))
    b, cached_b = sh.propose_cached(tree, s, d)
    assert cached_b is True and b["suggested_k"] == a["suggested_k"]
    assert [r["silhouette"] for r in b["by_k"]] == [r["silhouette"] for r in a["by_k"]]


# ── fixup-am: peak / trough alignment and the anchor fraction ───────────────
#
# `align` gains `peak` (the window's SIGNED maximum, the top of a spike) and
# `trough` (its signed minimum, the bottom of a drop) beside `centre` (the
# largest departure either way). Both use the swing rule's guard: straight line
# removed, running median of `swing_width` samples, measured from that median's
# own median. `anchor_frac` places the chosen sample at that fraction of the
# window (0.5 = the middle, AG's centring unchanged). Defaults are unchanged:
# centre, 0.5 — every existing pool and tree key is reproduced.

def _spike_then_drop(n=600, spike_at=150, drop_at=420):
    t = np.arange(n, dtype=float)
    seg = 0.8 * t / n                                          # a drift the detrend removes
    seg = seg + 1.0 * np.exp(-((t - spike_at) / 10.0) ** 2)    # a small spike
    seg = seg - 3.0 * np.exp(-((t - drop_at) / 14.0) ** 2)     # a large drop
    seg[60] += 9.0                                             # a one-sample glitch, larger than both
    return seg


def test_peak_centres_the_spike_trough_the_drop_centre_the_drop_and_grid_nothing():
    sh = _sh()
    seg = _spike_then_drop()
    assert set(sh.ALIGNS) == {"grid", "centre", "peak", "trough"}
    assert abs(sh.anchor_index(seg, "peak") - 150) <= 6
    assert abs(sh.anchor_index(seg, "trough") - 420) <= 6
    assert abs(sh.anchor_index(seg, "centre") - 420) <= 6
    assert sh.anchor_index(seg, "centre") == sh.swing_index(seg)      # centre is the swing rule, unchanged
    # the re-cut puts the chosen sample in the middle of a 600-sample window starting at 10,000
    for align, at in (("peak", 150), ("trough", 420), ("centre", 420)):
        start, clamped = sh.recut_start(10_000, 600, sh.anchor_index(seg, align), 0, 100_000)
        assert not clamped
        assert abs((10_000 + at) - (start + 300)) <= 6, align
    with pytest.raises(ValueError, match="align"):
        sh.anchor_index(seg, "sideways")
    assert "maximum" in sh.ALIGN_RULE["peak"] and "minimum" in sh.ALIGN_RULE["trough"]
    assert "running median" in sh.ALIGN_RULE["peak"] and "running median" in sh.ALIGN_RULE["trough"]


def test_anchor_frac_places_the_extremum_at_that_fraction_and_clamps_as_centre_does():
    sh = _sh()
    lo, hi = sh.allowed_interval(2000, 600, stretch=(1000, 5000), n_samples=10_000, spans=[(3000, 3100), (100, 900)])
    assert (lo, hi) == (1000, 3000)                              # the fence does not depend on the anchor
    # a third in: the swing at window sample 550 lands at sample 200 of the re-cut
    start, clamped = sh.recut_start(2000, 600, swing=550, lo=lo, hi=hi, anchor_frac=1 / 3)
    assert (start, clamped) == (2350, False)
    start, clamped = sh.recut_start(2300, 600, swing=599, lo=lo, hi=hi, anchor_frac=1 / 3)   # wants 2699: past 2400
    assert (start, clamped) == (2400, True)
    start, clamped = sh.recut_start(1100, 600, swing=0, lo=lo, hi=hi, anchor_frac=1 / 3)     # wants 900
    assert (start, clamped) == (1000, True)
    # 0.5 is AG's centring exactly, odd lengths included
    for L in (60, 61, 63, 599, 600, 1800, 1801):
        assert sh.anchor_offset(L, 0.5) == L // 2, L
        assert sh.recut_start(5000, L, 17, 0, 100_000) == sh.recut_start(5000, L, 17, 0, 100_000, anchor_frac=0.5)
    assert sh.anchor_offset(600, 1 / 3) == 200 and sh.anchor_offset(1800, 1 / 3) == 600
    assert sh.anchor_offset(600, 1.0) == 599 and sh.anchor_offset(600, 0.0) == 0
    for bad in (-0.1, 1.5, float("nan")):
        with pytest.raises(ValueError, match="anchor_frac"):
            sh.anchor_offset(600, bad)


def test_trough_with_a_third_in_puts_the_drops_a_third_into_the_thirty_minute_windows(pooled):
    conn, pool = pooled
    sh = _sh()
    frame = sh.pool_frame(sh.pool_windowset(pool))
    out = sh.trace_shapes(conn, frame, align="trough", anchor_frac=1 / 3, detrend="off", noise_floor=False)
    f = out.frame
    assert (f["start"] >= f["stretch_a"]).all() and (f["start"] + f["length"] <= f["stretch_b"]).all()
    thirty = f[f["scale_min"] == 30.0]
    # peak_frac is where the ALIGNED sample sits (the trough here): about a third in
    assert float(np.median(np.abs(thirty["peak_frac"] - 1 / 3))) < 0.1
    assert out.meta["align"] == "trough" and out.meta["anchor_frac"] == pytest.approx(1 / 3)
    assert "33%" in out.meta["align_rule"] and "minimum" in out.meta["align_rule"]
    assert out.meta["recut"]["n_moved"] > 0
    sh.check_recut(conn, f)


def test_grid_moves_nothing_and_ignores_the_anchor(pooled):
    conn, pool = pooled
    sh = _sh()
    frame = sh.pool_frame(sh.pool_windowset(pool))
    a = sh.trace_shapes(conn, frame, align="grid", noise_floor=False)
    b = sh.trace_shapes(conn, frame, align="grid", anchor_frac=0.2, noise_floor=False)
    assert (a.frame["start"] == a.frame["orig_start"]).all()
    assert a.key == b.key and np.array_equal(a.vectors, b.vectors)
    assert a.meta["anchor_frac"] is None


@pytest.mark.parametrize("align", ["centre", "peak", "trough"])
def test_two_windows_aligned_onto_one_event_keep_one_under_every_rule(pooled, align):
    conn, pool = pooled
    sh = _sh()
    out = sh.trace_shapes(conn, sh.pool_frame(sh.pool_windowset(pool)), align=align, detrend="off", noise_floor=False)
    f, rc = out.frame, out.meta["recut"]
    assert rc["n_near_duplicate"] > 0
    assert len(f) + rc["n_near_duplicate"] == out.meta["n_in"]
    for _k, g in f.groupby(["recording_id", "scale_min"]):
        s = np.sort(g["start"].to_numpy())
        assert (np.diff(s) >= g["length"].iloc[0] / 2.0).all(), (_k, align)


def test_the_tree_key_changes_with_alignment_and_anchor_and_not_at_the_defaults(pooled, tmp_path):
    conn, pool = pooled
    sh = _sh()
    frame = sh.pool_frame(sh.pool_windowset(pool))
    centre = sh.trace_shapes(conn, frame, noise_floor=False)
    peak = sh.trace_shapes(conn, frame, align="peak", noise_floor=False)
    third = sh.trace_shapes(conn, frame, align="centre", anchor_frac=1 / 3, noise_floor=False)
    assert len({sh.tree_key(s, 200, 0) for s in (centre, peak, third)}) == 3
    # the defaults are AG's: the shape key is the pre-fixup-am formula, so every cached pool and tree still answers
    f = centre.frame
    old = sh._key({"kind": "trace_shapes", "how": {k: centre.meta.get(k) for k in
                                                   ("resample_length", "noise_floor", "floors_mv", "align", "detrend")}},
                  [f[c].to_numpy() for c in ("source_file", "channel", "start", "length", "role")])
    assert centre.key == old and centre.meta["anchor_frac"] == 0.5
    explicit = sh.trace_shapes(conn, frame, align="centre", anchor_frac=0.5, noise_floor=False)
    assert explicit.key == centre.key and np.array_equal(explicit.vectors, centre.vectors)
    # a saved set round-trips with its anchor
    back = sh.ShapeSet.load(third.save(str(tmp_path / "third")))
    assert back.key == third.key and back.meta["anchor_frac"] == pytest.approx(1 / 3)


def test_the_block_offers_the_anchor_and_ships_it_and_the_rule_to_the_page(pooled):
    conn, pool = pooled
    sh = _sh()
    from Adapters.registry import discover_adapters, get_adapter
    from server.serialize import to_payload
    discover_adapters()
    p = {s.name: s for s in get_adapter("preprocessing.trace_shape").params}
    assert p["anchor_frac"].default == sh.DEFAULT_ANCHOR_FRAC == 0.5
    assert p["anchor_frac"].min == 0.0 and p["anchor_frac"].max == 1.0
    out = sh.trace_shapes(conn, sh.pool_frame(sh.pool_windowset(pool)), align="peak", anchor_frac=0.25)
    ws = sh.frame_windowset(out.frame, "x.npz")
    s = to_payload("windowset", ws, {**out.meta, "shape_file": "x.npz", "shape_key": out.key}, {})["shape"]
    assert s["align"] == "peak" and s["anchor_frac"] == pytest.approx(0.25)
    assert "maximum" in s["align_rule"] and "25%" in s["align_rule"] and "recut" in s


def test_a_model_recipe_carries_the_anchor_so_its_tree_is_rebuilt_on_the_same_windows():
    import json
    from Working.training import shape_forest as sf
    mapping = {"k": 2, "clusters": {"1": {"name": "a", "class": "interesting"},
                                    "2": {"name": "b", "class": "not_interesting"}}}

    def recipe(shape_params):
        steps = [{"stage": "preprocessing", "algorithm": "window_pool", "params": {"pool": "1"}},
                 {"stage": "preprocessing", "algorithm": "trace_shape", "params": shape_params},
                 {"stage": "catalogue", "algorithm": "shape_cluster",
                  "params": {"sample": 200, "seed": 0, "k": 2, "mapping": json.dumps(mapping)}}]
        return sf.make_recipe({"id": 1, "name": "p", "version": 1, "key": "x"}, {"id": 7, "name": "t", "steps": steps})

    assert "anchor_frac" not in recipe({})["shape"]                        # AG's recipes are unchanged
    r = recipe({"align": "trough", "anchor_frac": 1 / 3})["shape"]
    assert r["align"] == "trough" and r["anchor_frac"] == pytest.approx(1 / 3)
