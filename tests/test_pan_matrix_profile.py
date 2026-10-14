"""
test_pan_matrix_profile.py
============================
The core of `detection.pan_matrix_profile`
(`Working/Detection/matrix_profiling/pan.py`): the pan matrix profile over a
geometric ladder of window lengths, the image's layout, and the per-length
verdict against phase-randomised copies of the span.

What is pinned:
* a planted 90 s motif (12 times) and a 20 min motif (6 times) on an AR(1)
  phi 0.97 background: bright at both lengths where they sit, both lengths
  clear the null, and the 90 s motif does not light the 20 min-and-longer
  rows away from the long motif;
* no structure (random walk, AR(1) 0.95 and 0.99, pink noise) -> "no length
  stands out", on a 2 h span at 1 Hz (the fewest distinct windows: the
  margin's hardest case) and an 8 h span decimated to 0.5 Hz (the manager's
  chain spans, at the cost of a 4 h one);
* the image holds distances, not stumpy's binarised `PAN_`;
* rows long first, start alignment, the NaN tail of each row;
* gaps: short ones bridged, long ones left out and counted;
* approximate (scrump) runs: never brighter than exact, reproducible, and the
  global numpy RNG left as it was;
* cancel between lengths raises the executor's `RecipeCancelled`, and
  `on_progress` fires per profile.

Runnable standalone:  python tests/test_pan_matrix_profile.py
"""

import os
import sys

import numpy as np
import pytest

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
while not os.path.isdir(os.path.join(PROJECT_ROOT, "Working")) \
        and os.path.dirname(PROJECT_ROOT) != PROJECT_ROOT:
    PROJECT_ROOT = os.path.dirname(PROJECT_ROOT)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import stumpy  # noqa: E402

from tests import _pan_synthetic as syn  # noqa: E402
from Working.Detection.matrix_profiling import pan as P  # noqa: E402

FS = syn.FS


def _decimate(x, k):
    return x[: (len(x) // k) * k].reshape(-1, k).mean(axis=1)


@pytest.fixture(scope="module")
def planted():
    x, short_starts, long_starts = syn.planted(4 * 3600, seed=0)
    out = P.pan_matrix_profile(x, FS)                    # the defaults: 30 s - 1 h, 12 lengths, exact, 1 draw
    return x, short_starts, long_starts, out


def _row_near(out, seconds):
    ls = np.asarray(out["lengths_s"])
    return int(np.argmin(np.abs(np.log(ls / seconds))))


# ── the planted motifs ──────────────────────────────────────────────────────

def test_both_planted_lengths_clear_the_null(planted):
    _, _, _, out = planted
    by_len = {d["length_s"]: d for d in out["per_length"]}
    short = [d for s, d in by_len.items() if 60 <= s <= 135]
    long_ = [d for s, d in by_len.items() if 900 <= s <= 1600]
    assert short and long_, sorted(by_len)
    assert any(d["clears"] for d in short), [(d["length_s"], d["gap"], d["reason"]) for d in short]
    assert any(d["clears"] for d in long_), [(d["length_s"], d["gap"], d["reason"]) for d in long_]
    assert out["suggested_window_s"] is not None
    assert "stands out" not in out["verdict"]


def test_the_planted_motifs_are_bright_where_they_sit(planted):
    _, short_starts, long_starts, out = planted
    img = out["image"]
    rs = _row_near(out, syn.SHORT_M)
    row = img[rs]
    # the window starting at each planted short motif is among the brightest of its row
    assert np.all(row[short_starts] >= np.nanpercentile(row, 99)), row[short_starts]
    rl = _row_near(out, syn.LONG_M)
    row = img[rl]
    m = out["lengths_samples"][rl]
    starts = [s for s in long_starts if s + m <= len(row)]
    assert np.all(row[starts] >= np.nanpercentile(row, 95)), row[starts]


def test_the_short_motif_does_not_light_the_long_rows_away_from_the_long_motif(planted):
    x, short_starts, long_starts, out = planted
    img = out["image"]
    n = len(x)
    inside_long = np.zeros(n, dtype=bool)
    for s in long_starts:
        inside_long[s:s + syn.LONG_M] = True
    for r, m in enumerate(out["lengths_samples"]):
        if m < syn.LONG_M:
            continue
        row = img[r]
        # windows that hold a short motif and touch no long motif
        cols = []
        for s in short_starts:
            for c in range(max(0, s + syn.SHORT_M - m), s + 1, 30):
                if c + m <= n and not inside_long[c:c + m].any():
                    cols.append(c)
        if not cols:
            continue
        plain = np.ones(n, dtype=bool)
        for c in range(n - m + 1):
            pass
        clean = np.array([not inside_long[c:c + m].any() for c in range(0, n - m + 1, 30)])
        clean_cols = np.arange(0, n - m + 1, 30)[clean]
        free = np.setdiff1d(clean_cols, cols)
        if len(free) < 10:
            continue
        # holding a short motif does not make a long window brighter than the plain background's 90th percentile
        assert np.median(row[cols]) <= np.nanpercentile(row[free], 90), (m, np.median(row[cols]))


# ── no structure: no length stands out ──────────────────────────────────────

SPANS = {
    "2h_1Hz": (2 * 3600, 1, 1.0),       # n = 7200: the fewest distinct windows per length
    "8h_0.5Hz": (8 * 3600, 2, 0.5),     # n = 14400: the manager's 8 h chain spans, decimated
}


@pytest.mark.parametrize("span", sorted(SPANS))
@pytest.mark.parametrize("kind", ["random_walk", "ar95", "ar99", "pink"])
def test_no_structure_means_no_length_stands_out(kind, span):
    n1, dec, fs = SPANS[span]
    x = syn.no_structure(kind, n1, seed=7)
    if dec > 1:
        x = _decimate(x, dec)
    out = P.pan_matrix_profile(x, fs)
    assert out["suggested_window_s"] is None, [(d["length_s"], d["gap"]) for d in out["per_length"]]
    assert out["verdict"].startswith("no length stands out"), out["verdict"]
    # judged lengths really were compared (the verdict is not "nothing could be judged")
    assert sum(d["judged"] for d in out["per_length"]) >= 6


def test_the_shortest_length_is_never_a_fallback():
    x = syn.no_structure("ar97", 2 * 3600, seed=3)
    out = P.pan_matrix_profile(x, FS, min_window_s=30, max_window_s=600, n_lengths=5)
    assert out["suggested_window_s"] is None
    assert out["suggested_row"] is None


def test_without_a_null_nothing_is_judged():
    x, _, _ = syn.planted(2 * 3600, seed=1)
    out = P.pan_matrix_profile(x, FS, max_window_s=600, n_lengths=4, null_draws=0)
    assert out["suggested_window_s"] is None
    assert not any(d["judged"] for d in out["per_length"])
    assert "null_draws = 0" in out["verdict"]


def test_a_length_with_too_few_windows_is_not_judged(planted):
    _, _, _, out = planted
    longest = out["per_length"][0]
    assert longest["length_s"] == pytest.approx(3600)
    assert not longest["judged"] and not longest["clears"]
    assert "too long to judge" in longest["reason"]


# ── what the image holds, and where ─────────────────────────────────────────

def _small():
    return syn.no_structure("ar97", 3000, seed=2)


def test_rows_long_first_start_aligned_with_a_nan_tail():
    x = _small()
    out = P.pan_matrix_profile(x, FS, min_window_s=20, max_window_s=200, n_lengths=4, null_draws=0)
    img = out["image"]
    ms = out["lengths_samples"]
    assert img.shape == (len(ms), len(x))
    assert img.dtype == np.float32
    assert ms == sorted(ms, reverse=True)                     # row 0 = the longest window
    assert out["lengths_s"] == [m / FS for m in ms]
    for r, m in enumerate(ms):
        assert np.all(np.isfinite(img[r, :len(x) - m + 1]))
        assert np.all(np.isnan(img[r, len(x) - m + 1:]))       # no window starts in the last m - 1 samples
        # column i is the window that STARTS at i: compare with stumpy directly
        ref = 1.0 - np.minimum(stumpy.stump(x, m)[:, 0].astype(float) / (2 * np.sqrt(m)), 1.0)
        np.testing.assert_allclose(img[r, :len(x) - m + 1], ref, rtol=1e-5, atol=1e-6)


def test_the_image_holds_distances_not_the_binarised_pan():
    """stumpy.stimp's PAN_ is thresholded at 0.2 by default: a 0/1 picture. The image here is continuous and
    equals 1 - the normalised distance; a binarised read would hold two values."""
    x = _small()
    out = P.pan_matrix_profile(x, FS, min_window_s=20, max_window_s=200, n_lengths=3, null_draws=0)
    for r in range(out["image"].shape[0]):
        vals = out["image"][r][np.isfinite(out["image"][r])]
        assert len(np.unique(np.round(vals, 4))) > 100
        assert 0.0 <= vals.min() and vals.max() <= 1.0
        assert 0.3 < np.median(vals) < 0.99                    # neither 0/1 nor clipped flat
    st = stumpy.stimp(x, min_m=20, max_m=21, step=1, percentage=1.0, pre_scrump=False)
    st.update()
    binarised = st.PAN_[st.PAN_ == st.PAN_]
    assert set(np.unique(binarised)) <= {0.0, 1.0}             # what a read of PAN_ would have given


def test_per_length_statistics_are_of_the_normalised_profile():
    x = _small()
    out = P.pan_matrix_profile(x, FS, min_window_s=40, max_window_s=40, n_lengths=1, null_draws=0)
    d = out["per_length"][0]
    prof = np.minimum(stumpy.stump(x, 40)[:, 0].astype(float) / (2 * np.sqrt(40)), 1.0)
    assert d["best"] == pytest.approx(prof.min(), rel=1e-6)
    assert d["best_idx"] == int(np.argmin(prof))
    assert d["p05"] == pytest.approx(np.percentile(prof, 5), rel=1e-6)
    assert d["median"] == pytest.approx(np.median(prof), rel=1e-6)


def test_lengths_are_geometric_deduplicated_and_dropped_when_they_cannot_fit():
    kept, dropped = P.window_lengths(1000, 1.0, 1.0, 900.0, 8)
    assert dropped and all(m < 3 or m > 500 for m in dropped)
    assert kept == sorted(set(kept))
    ratios = np.diff(np.log(kept))
    assert np.allclose(ratios, ratios[0], atol=0.2)
    with pytest.raises(ValueError, match="no window length fits"):
        P.pan_matrix_profile(np.random.default_rng(0).standard_normal(100), 1.0, min_window_s=60,
                             max_window_s=90, n_lengths=2, null_draws=0)


# ── gaps ────────────────────────────────────────────────────────────────────

def test_short_gaps_are_bridged_and_long_gaps_left_out_and_counted():
    x = _small().copy()
    x[500:503] = np.nan                                       # 3 s: bridged (max_fill_s 5)
    x[1500:1600] = np.nan                                     # 100 s: left out
    out = P.pan_matrix_profile(x, FS, min_window_s=20, max_window_s=50, n_lengths=2, null_draws=1)
    assert out["n_filled"] == 3 and out["n_long_gap"] == 100
    for r, m in enumerate(out["lengths_samples"]):
        row = out["image"][r]
        assert np.all(np.isfinite(row[480:510]))                       # across the bridged gap
        assert np.all(np.isnan(row[1500 - m + 1:1600]))                 # every window touching the long gap
        assert np.isfinite(row[1500 - m]) and np.isfinite(row[1600])
        d = out["per_length"][r]
        assert d["n_windows_nan"] == (1600 - (1500 - m + 1))
    assert all(d["judged"] for d in out["per_length"])


def test_an_all_nan_span_is_refused_in_words():
    with pytest.raises(ValueError, match="NaN|finite"):
        P.pan_matrix_profile(np.full(1000, np.nan), 1.0, min_window_s=10, max_window_s=20, n_lengths=2)


# ── approximate ─────────────────────────────────────────────────────────────

def test_approximate_is_never_brighter_than_exact_and_is_reproducible():
    x = _small()
    kw = dict(min_window_s=30, max_window_s=60, n_lengths=2, null_draws=0)
    exact = P.pan_matrix_profile(x, FS, **kw)["image"]
    before = np.random.get_state()
    a = P.pan_matrix_profile(x, FS, percentage=0.2, seed=4, **kw)["image"]
    after = np.random.get_state()
    b = P.pan_matrix_profile(x, FS, percentage=0.2, seed=4, **kw)["image"]
    ok = np.isfinite(exact)
    assert np.all(a[ok] <= exact[ok] + 1e-5)
    np.testing.assert_array_equal(a, b)
    assert before[0] == after[0] and np.array_equal(before[1], after[1]) and before[2] == after[2]


def test_scrump_cost_factor():
    assert P.scrump_cost_factor(1.0) == 1.0
    assert P.scrump_cost_factor(0.1) < 1.0
    assert P.scrump_cost_factor(0.1) < P.scrump_cost_factor(0.5) <= 1.0


# ── stopping and progress ───────────────────────────────────────────────────

def test_progress_fires_per_profile_and_cancel_stops_between_lengths():
    from Working.execution import RecipeCancelled
    x = _small()
    seen = []
    out = P.pan_matrix_profile(x, FS, min_window_s=20, max_window_s=200, n_lengths=4, null_draws=0,
                               on_progress=lambda d, t, s: seen.append((d, t, s)))
    assert [d for d, _, _ in seen] == [1, 2, 3, 4] and all(t == 4 for _, t, _ in seen)
    seen = []
    P.pan_matrix_profile(x, FS, min_window_s=20, max_window_s=200, n_lengths=4, null_draws=2,
                         on_progress=lambda d, t, s: seen.append((d, t, s)))
    assert len(seen) == 12 and seen[-1][:2] == (12, 12)

    calls = []
    with pytest.raises(RecipeCancelled, match="cancelled"):
        P.pan_matrix_profile(x, FS, min_window_s=20, max_window_s=200, n_lengths=4, null_draws=0,
                             on_progress=lambda d, t, s: calls.append(d),
                             should_cancel=lambda: len(calls) >= 2)
    assert calls == [1, 2]                                    # stopped before the third length
    assert len(out["per_length"]) == 4


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
