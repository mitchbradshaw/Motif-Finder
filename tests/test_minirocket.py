"""
test_minirocket.py
==================
w2-c: the core of `catalogue.minirocket` (`Working/Catalogue/minirocket.py`) —
a MiniRocket shape fingerprint per window (Dempster, Schmidt & Webb 2021,
aeon 1.4's `MiniRocket` transform).

What is pinned:

* the three shape classes of `_minirocket_synthetic` (same mean and variance,
  different shape) are learnable from the fingerprint by the site's forest on
  every coloured background — and the same forest on the windows' Catch22
  features is measured beside it on the same split (printed, not asserted:
  see the module's report);
* with the labels shuffled the holdout accuracy is at chance — a fingerprint
  that "learns" shuffled labels means leakage;
* the fit is on the training windows only: changing only the test windows
  leaves every training window's features unchanged (same seed), and changing
  the training windows does change the test windows' features;
* deterministic for a fixed seed; the feature count is what aeon returns
  (rounded down to a multiple of 84);
* `normalise` makes the fingerprint about shape, not level or scale;
* the pool path reads the Trace shape vectors from `shape_file` by `shape_row`
  and never slices `x`; a pool without `shape_file` is refused in words;
* NaN gaps up to 5 % of a window are interpolated (counted), longer ones leave
  the window out (counted, upstream columns kept on the rest); short windows and
  an over-`max_cells` table are refused in words.

Runnable standalone:  python -m pytest tests/test_minirocket.py -q
"""

import os
import shutil
import sys
import tempfile

import numpy as np
import pandas as pd
import pytest

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
while not os.path.isdir(os.path.join(PROJECT_ROOT, "Working")) \
        and os.path.dirname(PROJECT_ROOT) != PROJECT_ROOT:
    PROJECT_ROOT = os.path.dirname(PROJECT_ROOT)
for p in (PROJECT_ROOT, os.path.join(PROJECT_ROOT, "tests")):
    if p not in sys.path:
        sys.path.insert(0, p)

import _minirocket_synthetic as syn  # noqa: E402
from Working.Catalogue import minirocket as MR  # noqa: E402
from Working.types import WindowSet  # noqa: E402

L, FS = syn.L, syn.FS
SMALL = 840          # 10 features per kernel: fast, and still a multiple of 84


def tiling(n_windows, length=L, offset=0, split=None, extra=None):
    """A WindowSet of `n_windows` back-to-back windows, channel-absolute from `offset`."""
    feats = {}
    if split is not None:
        feats["split"] = np.asarray(split, dtype=np.int64)
    if extra:
        feats.update(extra)
    return WindowSet(starts=offset + np.arange(n_windows, dtype=np.int64) * length, length=length, fs=FS,
                     features=pd.DataFrame(feats) if feats else None)


def span_t(x, offset=0):
    return (offset + np.arange(len(x), dtype=float)) / FS


def blocked_split(n, train_frac=0.75):
    split = np.full(n, 2, dtype=np.int64)
    split[: int(round(n * train_frac))] = 0
    return split


def mr_columns(frame):
    return [c for c in frame.columns if c.startswith(MR.FEATURE_PREFIX)]


def run(x, ws, offset=0, **kw):
    kw.setdefault("n_features", SMALL)
    return MR.fingerprint(ws, x, span_t(x, offset) if x is not None else None, FS, **kw)


def forest_accuracy(F_train, y_train, F_test, y_test, seed=42):
    """The site's estimator shape (`catalogue.classifier`): variance pruning into a balanced forest."""
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.feature_selection import VarianceThreshold
    from sklearn.pipeline import make_pipeline
    clf = make_pipeline(VarianceThreshold(1e-6),
                        RandomForestClassifier(n_estimators=300, class_weight="balanced", random_state=seed,
                                               n_jobs=-1))
    clf.fit(F_train, y_train)
    return float((clf.predict(F_test) == y_test).mean())


# ── the feature count, the names, determinism ───────────────────────────────

@pytest.mark.parametrize("asked,real", [(10_000, 9_996), (1_000, 924), (840, 840), (50, 84)])
def test_the_feature_count_is_rounded_down_to_a_multiple_of_84(asked, real):
    assert MR.real_feature_count(asked) == real


def test_the_reported_count_is_what_aeon_really_returned():
    x, _ = syn.recording(n_per_class=4, seed=3)
    out = run(x, tiling(12, split=blocked_split(12)), n_features=1_000)
    cols = mr_columns(out.windows.features)
    assert out.meta["n_features"] == len(cols) == 924
    assert out.meta["n_features_asked"] == 1_000
    assert cols[0] == "mr_0000" and cols[-1] == "mr_0923"
    assert all(out.windows.features[c].dtype == np.float32 for c in cols[:5])


def test_deterministic_for_a_fixed_seed_and_not_across_seeds():
    x, _ = syn.recording(n_per_class=4, seed=3)
    ws = tiling(12, split=blocked_split(12))
    a = run(x, ws, seed=7).windows.features
    b = run(x, ws, seed=7).windows.features
    c = run(x, ws, seed=8).windows.features
    cols = mr_columns(a)
    assert np.array_equal(a[cols].to_numpy(), b[cols].to_numpy())
    assert not np.array_equal(a[cols].to_numpy(), c[cols].to_numpy())


def test_the_global_numpy_random_state_is_left_as_it_was():
    """aeon seeds numpy's global generator inside `fit`; the block must not leave it reseeded."""
    x, _ = syn.recording(n_per_class=2, seed=3)
    np.random.seed(123)
    expected = np.random.random(3)
    np.random.seed(123)
    run(x, tiling(6, split=blocked_split(6)), seed=0)
    assert np.allclose(np.random.random(3), expected)


# ── the leakage rule: fit on the training windows only ──────────────────────

def test_fit_on_train_changing_only_the_test_windows_leaves_the_train_features_alone():
    n = 16
    x, _ = syn.recording(n_per_class=6, seed=4)
    x = x[: n * L]
    split = blocked_split(n)
    ws = tiling(n, split=split)
    a = run(x, ws, seed=0)
    x2 = x.copy()
    test_rows = np.flatnonzero(split == 2)
    rng = np.random.default_rng(11)
    for i in test_rows:                          # brand-new content in every test window
        x2[i * L:(i + 1) * L] = syn.background("random_walk", L, rng) * 3.0
    b = run(x2, ws, seed=0)
    cols = mr_columns(a.windows.features)
    fa, fb = a.windows.features[cols].to_numpy(), b.windows.features[cols].to_numpy()
    train = split == 0
    assert np.array_equal(fa[train], fb[train]), "a test window leaked into the fit"
    assert not np.array_equal(fa[~train], fb[~train])
    assert a.meta["fit_on"] == "train" and a.meta["n_fit_windows"] == int(train.sum())


def test_changing_the_train_windows_changes_the_test_windows_features():
    """The converse: the biases really come from the training windows."""
    n = 16
    x, _ = syn.recording(n_per_class=6, seed=4)
    x = x[: n * L]
    split = blocked_split(n)
    ws = tiling(n, split=split)
    a = run(x, ws, seed=0)
    x2 = x.copy()
    rng = np.random.default_rng(12)
    for i in np.flatnonzero(split == 0):
        x2[i * L:(i + 1) * L] = syn.background("ar1", L, rng)
    b = run(x2, ws, seed=0)
    cols = mr_columns(a.windows.features)
    test = split == 2
    assert not np.array_equal(a.windows.features[cols].to_numpy()[test], b.windows.features[cols].to_numpy()[test])


def test_without_a_split_it_fits_on_every_window_and_warns_that_a_holdout_is_optimistic():
    x, _ = syn.recording(n_per_class=3, seed=5)
    out = run(x, tiling(9))
    assert out.meta["fit_on"] == "all" and out.meta["n_fit_windows"] == 9
    warn = " ".join(out.meta["warnings"]).lower()
    assert "optimistic" in warn and "split" in warn


def test_a_string_split_and_a_pool_role_are_read_as_the_split_too():
    x, _ = syn.recording(n_per_class=3, seed=5)
    roles = np.array(["train"] * 6 + ["test"] * 3)
    a = run(x, tiling(9, extra={"split": roles}))
    assert a.meta["fit_on"] == "train" and a.meta["n_fit_windows"] == 6


def test_a_split_with_no_training_window_is_refused_in_words():
    x, _ = syn.recording(n_per_class=3, seed=5)
    with pytest.raises(ValueError, match="(?i)no training window"):
        run(x, tiling(9, split=np.full(9, 2)))


# ── the three shape classes, the forest, Catch22 beside it ──────────────────

def _classes(background_kind, n_per_class=60, noise=1.0, seed=1):
    x, y = syn.recording(n_per_class=n_per_class, background_kind=background_kind, noise=noise, seed=seed)
    n = len(y)
    split = blocked_split(n)
    out = MR.fingerprint(tiling(n, split=split), x, span_t(x), FS)          # the defaults: the paper's 10,000
    F = out.windows.features[mr_columns(out.windows.features)].to_numpy()
    return x, y, split, F, out


RESULTS = {}


@pytest.mark.parametrize("background_kind", syn.BACKGROUNDS)
def test_three_shape_classes_are_learnable_from_the_fingerprint(background_kind):
    x, y, split, F, out = _classes(background_kind)
    tr, te = split == 0, split == 2
    acc = forest_accuracy(F[tr], y[tr], F[te], y[te])
    RESULTS[("minirocket", background_kind)] = acc
    print(f"\n[{background_kind}] forest on MiniRocket ({out.meta['n_features']} features): holdout {acc:.3f}")
    assert out.meta["n_features"] == 9_996
    assert acc >= 0.8, f"{background_kind}: holdout accuracy {acc:.3f} on three shape classes"


def test_catch22_is_measured_beside_it_on_the_same_split():
    """Acceptance: the forest on MiniRocket against the forest on Catch22, same windows, same split. Measured
    on this set, Catch22 does NOT lose (see the report): the assertion is only that both learn the classes,
    and the numbers are printed so the comparison is on record."""
    from Working.Detection.aeon_features.transformations import catch22_features
    x, y, split, F, _ = _classes("ar1")
    W = x[: len(y) * L].reshape(len(y), L)
    C = np.nan_to_num(np.asarray([catch22_features(w) for w in W], dtype=float))
    tr, te = split == 0, split == 2
    acc_mr = forest_accuracy(F[tr], y[tr], F[te], y[te])
    acc_c22 = forest_accuracy(C[tr], y[tr], C[te], y[te])
    print(f"\n[ar1] forest holdout: MiniRocket {acc_mr:.3f} · Catch22 {acc_c22:.3f}")
    assert acc_mr >= 0.8 and acc_c22 >= 0.8


def test_shuffled_labels_fall_to_chance():
    """The no-structure check: shuffled labels must not be learnable. One-sided: above chance by more than
    three binomial standard deviations would mean the fingerprint carries the label (leakage)."""
    x, y, split, F, _ = _classes("ar1")
    tr, te = split == 0, split == 2
    n_test = int(te.sum())
    sd = np.sqrt((1 / 3) * (2 / 3) / n_test)
    accs = []
    for s in range(3):
        ys = np.random.default_rng(100 + s).permutation(y)
        accs.append(forest_accuracy(F[tr], ys[tr], F[te], ys[te], seed=s))
    print(f"\nshuffled-label holdout accuracies {np.round(accs, 3).tolist()} (chance 0.333, sd {sd:.3f})")
    assert max(accs) < 1 / 3 + 3 * sd
    assert np.mean(accs) < 1 / 3 + 2 * sd


# ── normalise ────────────────────────────────────────────────────────────────

def test_normalise_makes_the_fingerprint_about_shape_not_level_or_scale():
    W, _ = syn.windows(n_per_class=3, seed=6)
    x = W.ravel()
    gains = np.repeat(np.linspace(0.2, 40.0, len(W)), L)
    levels = np.repeat(np.linspace(-5.0, 9.0, len(W)), L)
    x2 = x * gains + levels
    ws = tiling(len(W), split=blocked_split(len(W)))
    a = run(x, ws, normalise=True).windows.features
    b = run(x2, ws, normalise=True).windows.features
    cols = mr_columns(a)
    assert np.allclose(a[cols].to_numpy(), b[cols].to_numpy(), atol=1e-6)
    c = run(x, ws, normalise=False).windows.features
    d = run(x2, ws, normalise=False).windows.features
    assert not np.allclose(c[cols].to_numpy(), d[cols].to_numpy())


def test_a_flat_window_is_kept_and_counted_not_divided_by_zero():
    x, _ = syn.recording(n_per_class=3, seed=6)
    x = x.copy()
    x[2 * L:3 * L] = 4.2
    out = run(x, tiling(9, split=blocked_split(9)))
    assert out.windows.n_windows == 9
    assert out.meta["n_flat"] == 1
    F = out.windows.features[mr_columns(out.windows.features)].to_numpy()
    assert np.all(np.isfinite(F))


# ── the window sources: x, or the Trace shape file ──────────────────────────

def test_windows_are_sliced_at_channel_absolute_starts_minus_the_span_offset():
    """A span that starts 5,000 samples into the channel: starts are channel-absolute."""
    offset = 5_000
    x, _ = syn.recording(n_per_class=3, seed=7)
    ws_abs = tiling(9, offset=offset, split=blocked_split(9))
    a = run(x, ws_abs, offset=offset)
    b = run(x, tiling(9, offset=0, split=blocked_split(9)), offset=0)
    cols = mr_columns(a.windows.features)
    assert np.array_equal(a.windows.features[cols].to_numpy(), b.windows.features[cols].to_numpy())
    assert np.array_equal(a.windows.starts, ws_abs.starts)
    assert a.meta["source"] == "x"


def test_a_window_outside_the_span_is_refused_in_words():
    x, _ = syn.recording(n_per_class=3, seed=7)
    ws = tiling(10, split=blocked_split(10))          # one window more than the span holds
    with pytest.raises(ValueError, match="(?i)past the span|outside"):
        run(x, ws)


def _tiny_pool(tmp, n=9, length=120, seed=8):
    """A pool WindowSet written exactly as Trace shape writes one: a ShapeSet on disk, `shape_file`/`shape_row`
    on every window. Windows sit on two channels of two recordings, so they cannot be sliced from one `x`."""
    from Working.training import shape as tshape
    rng = np.random.default_rng(seed)
    vectors = np.asarray([syn.shape(k % 3, rng, length) + 0.3 * syn.background("ar1", length, rng)
                          for k in range(n)], dtype=np.float32)
    frame = pd.DataFrame({
        "recording_id": np.array([1, 2] * n)[:n].astype(np.int64),
        "source_file": np.array(["a.mat", "b.mat"] * n)[:n],
        "channel": np.array([0, 3] * n)[:n].astype(np.int64),
        "start": (np.arange(n) * 1_000).astype(np.int64),
        "length": np.full(n, 600, dtype=np.int64),
        "fs": np.ones(n),
        "scale_min": np.full(n, 10.0),
        "role": np.array(["train"] * (n - 3) + ["test"] * 3),
        "set_id": np.ones(n, dtype=np.int64),
        "raw_range_mv": np.ones(n),
        "peak_frac": np.full(n, 0.5),
        # stored in reverse, so reading by row (not by position) is what is tested
        "shape_row": np.arange(n, dtype=np.int64)[::-1].copy(),
    })
    stored = np.empty_like(vectors)
    stored[frame["shape_row"].to_numpy()] = vectors
    shapes = tshape.ShapeSet(frame=frame, vectors=stored, meta={"resample_length": length})
    path = shapes.save(os.path.join(tmp, "shapes"))
    return tshape.frame_windowset(frame, os.path.abspath(path)), vectors


@pytest.fixture
def tmp():
    d = tempfile.mkdtemp(prefix="w2c_mr_")
    try:
        yield d
    finally:
        shutil.rmtree(d, ignore_errors=True)


def test_a_pool_is_read_from_the_trace_shape_file_by_shape_row_never_sliced_from_x(tmp):
    ws, vectors = _tiny_pool(tmp)
    poison = np.full(50, np.nan)                       # slicing this would fail or give NaN
    out = MR.fingerprint(ws, poison, span_t(poison), FS, n_features=SMALL)
    assert out.meta["source"] == "shape_file"
    assert out.meta["fit_on"] == "train" and out.meta["n_fit_windows"] == 6       # from pool_role
    direct = MR.fingerprint_matrix(vectors.astype(float), fit_mask=np.arange(9) < 6, n_features=SMALL, seed=0)
    cols = mr_columns(out.windows.features)
    assert np.array_equal(out.windows.features[cols].to_numpy(), direct)
    # every upstream pool column rides along
    assert "pool_recording_id" in out.windows.features.columns and "shape_file" in out.windows.features.columns


def test_a_pool_without_a_shape_file_is_refused_naming_trace_shape(tmp):
    ws, _ = _tiny_pool(tmp)
    bare = WindowSet(starts=ws.starts, length=ws.length, fs=ws.fs,
                     features=ws.features.drop(columns=["shape_file", "shape_row"]))
    with pytest.raises(ValueError, match="Trace shape"):
        MR.fingerprint(bare, np.zeros(10), span_t(np.zeros(10)), FS, n_features=SMALL)


def test_a_missing_shape_file_is_refused_in_words(tmp):
    ws, _ = _tiny_pool(tmp)
    feats = ws.features.copy()
    feats["shape_file"] = os.path.join(tmp, "nowhere", "shapes.npz")
    gone = WindowSet(starts=ws.starts, length=ws.length, fs=ws.fs, features=feats)
    with pytest.raises(ValueError, match="(?i)not on disk|re-run"):
        MR.fingerprint(gone, None, None, FS, n_features=SMALL)


# ── NaN, short windows, the size guard ──────────────────────────────────────

def test_short_nan_gaps_are_interpolated_and_long_ones_leave_the_window_out_counted():
    x, _ = syn.recording(n_per_class=4, seed=9)
    x = x.copy()
    x[1 * L + 100: 1 * L + 112] = np.nan          # 12 of 600 = 2 %: interpolated
    x[4 * L + 50: 4 * L + 56] = np.nan            # 1 %: interpolated
    x[7 * L + 10: 7 * L + 70] = np.nan            # 10 %: left out
    tags = np.arange(12) * 10
    out = run(x, tiling(12, split=blocked_split(12), extra={"tag": tags}))
    assert out.meta["n_interpolated"] == 2
    assert out.meta["n_left_out"] == {"gaps_over_5pct": 1}
    assert out.windows.n_windows == 11
    assert 7 * L not in set(out.windows.starts.tolist())
    assert out.windows.features["tag"].tolist() == [t for i, t in enumerate(tags) if i != 7]
    assert "split" in out.windows.features.columns
    assert "1 of 12" in out.meta["summary"] and "5 %" in out.meta["summary"]
    F = out.windows.features[mr_columns(out.windows.features)].to_numpy()
    assert np.all(np.isfinite(F))


def test_every_window_left_out_is_refused_in_words_not_a_blank():
    x, _ = syn.recording(n_per_class=1, seed=9)
    x = x.copy()
    x[::10] = np.nan                               # 10 % of every window
    with pytest.raises(ValueError, match="(?i)every window.*5 %"):
        run(x, tiling(3, split=blocked_split(3)))


def test_windows_shorter_than_nine_samples_are_refused_in_words():
    x = np.random.default_rng(0).standard_normal(80)
    ws = tiling(10, length=8, split=blocked_split(10))
    with pytest.raises(ValueError, match="9 samples"):
        run(x, ws)


def test_an_oversized_table_is_refused_naming_n_features():
    x, _ = syn.recording(n_per_class=4, seed=9)
    ws = tiling(12, split=blocked_split(12))
    with pytest.raises(ValueError, match="n_features") as e:
        run(x, ws, n_features=10_000, max_cells=100_000)
    assert "12" in str(e.value) and "9,996" in str(e.value)


def test_an_empty_window_set_is_refused_in_words():
    with pytest.raises(ValueError, match="(?i)no window"):
        MR.fingerprint(WindowSet(starts=np.zeros(0, dtype=np.int64), length=L, fs=FS), np.zeros(10),
                       span_t(np.zeros(10)), FS)


def test_the_rules_say_what_the_block_did():
    x, _ = syn.recording(n_per_class=3, seed=10)
    out = run(x, tiling(9, split=blocked_split(9)))
    names = {r["name"] for r in out.meta["rules"]}
    assert {"fingerprint", "fit on", "normalise", "gaps", "feature count"} <= names
    for k in ("n_features", "n_fit_windows", "fit_on", "n_left_out", "seed", "seconds", "rules", "n_windows_in",
              "n_kept", "max_dilations", "normalise", "source", "summary"):
        assert k in out.meta, k


# ── fix round 1: keep_upstream_features (critic finding 3) ─────────────────

def test_keep_upstream_features_false_keeps_only_the_fingerprint_and_the_bookkeeping():
    """So RQ1's two arms differ only in features: Window matrix's Catch22 must not ride through to the classifier."""
    x, _ = syn.recording(n_per_class=3, seed=12)
    extra = {"catch22_DN_HistogramMode_5": np.arange(9.0), "fast_entropy_shannon": np.ones(9),
             "pool_role": np.array(["train"] * 9), "pool_channel": np.zeros(9, dtype=np.int64),
             "shape_raw_range_mv": np.ones(9)}
    ws = tiling(9, split=blocked_split(9), extra=extra)
    kept = run(x, ws).windows.features.columns
    assert "catch22_DN_HistogramMode_5" in kept, "the default is today's behaviour"
    out = run(x, ws, keep_upstream_features=False)
    cols = list(out.windows.features.columns)
    assert "catch22_DN_HistogramMode_5" not in cols and "fast_entropy_shannon" not in cols
    assert "shape_raw_range_mv" not in cols, "a measure, not bookkeeping"
    assert {"split", "pool_role", "pool_channel"} <= set(cols)
    assert out.meta["upstream_dropped"] == 3
    assert any(r["name"] == "upstream features" for r in out.meta["rules"])


# ── fix round 1: thread safety, the max_cells wording, temporal leakage (critic 5-7) ─

def test_the_aeon_fit_and_transform_run_under_a_module_lock():
    """Two bridge jobs must not interleave aeon's global np.random.seed with this module's save/restore."""
    import threading
    assert isinstance(MR._AEON_LOCK, type(threading.Lock()))
    M = np.random.default_rng(0).standard_normal((6, 64))
    done = threading.Event()

    def work():
        MR.fingerprint_matrix(M, n_features=84)
        done.set()

    MR._AEON_LOCK.acquire()
    try:
        th = threading.Thread(target=work)
        th.start()
        assert not done.wait(2.0), "the fit ran while another holder had the lock"
    finally:
        MR._AEON_LOCK.release()
    th.join(120)
    assert done.is_set()


def test_over_max_cells_even_at_84_features_says_use_fewer_windows():
    x, _ = syn.recording(n_per_class=4, seed=9)
    with pytest.raises(ValueError) as e:
        run(x, tiling(12, split=blocked_split(12)), n_features=10_000, max_cells=500)
    msg = str(e.value)
    assert "fewer windows" in msg and "e.g." not in msg, msg


def test_persistent_labels_with_no_shape_difference_score_at_chance_on_the_blocked_split():
    """Critic finding 4/7: labels that persist for ~2 h runs, no shape difference, a background whose texture
    drifts slowly — a fingerprint that learned *time* would score above chance here. Scored on the blocked split
    (train on the first 75 %, test on the last), balanced accuracy must be at chance."""
    from sklearn.metrics import balanced_accuracy_score
    from sklearn.ensemble import RandomForestClassifier
    rng = np.random.default_rng(41)
    n = 240
    phis = np.linspace(0.90, 0.995, n)
    W = np.asarray([syn.ar1(L, phi, rng) for phi in phis])
    W += 0.3 * np.sin(2 * np.pi * np.arange(n * L).reshape(n, L) / rng.uniform(150, 300))
    y = (np.arange(n) // 12) % 2                              # runs of 12 ten-minute windows: 2 h
    x = W.ravel()
    split = blocked_split(n)
    out = MR.fingerprint(tiling(n, split=split), x, span_t(x), FS, n_features=SMALL)
    F = out.windows.features[mr_columns(out.windows.features)].to_numpy()
    tr, te = split == 0, split == 2
    accs = []
    for s in range(3):
        clf = RandomForestClassifier(300, class_weight="balanced", random_state=s, n_jobs=-1).fit(F[tr], y[tr])
        accs.append(balanced_accuracy_score(y[te], clf.predict(F[te])))
    sd = np.sqrt(0.25 / int(te.sum()))
    print(f"\npersistent labels, blocked split: balanced accuracy {np.round(accs, 3).tolist()} (sd {sd:.3f})")
    assert np.mean(accs) < 0.5 + 3 * sd


def test_runs_when_numba_is_capped_at_one_thread():
    """A machine (or a cluster node) that caps numba at one thread (NUMBA_NUM_THREADS=1) must still fingerprint:
    aeon's n_jobs=-1 asks numba for every CPU and failed "The number of threads must be between 1 and 1" (found by
    the detrend-NaN session's gate, 2026-10-14). Run in a fresh process, since the cap is read at numba import."""
    import subprocess
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    code = ("import numpy as np; from Working.Catalogue import minirocket as MR; "
            "M = np.random.default_rng(0).standard_normal((20, 64)); "
            "F = MR.fingerprint_matrix(M, n_features=84); print('shape', F.shape)")
    env = dict(os.environ, NUMBA_NUM_THREADS="1", PYTHONIOENCODING="utf-8")
    p = subprocess.run([sys.executable, "-c", code], cwd=root, env=env, capture_output=True, text=True, timeout=900)
    assert p.returncode == 0, p.stderr[-2000:]
    assert "shape (20, 84)" in p.stdout
