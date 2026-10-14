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
* the null is amplitude-adjusted: a lopsided recording with no structure
  (exp of an AR(1)) gets at most 1 suggestion in 10 (W3-C critic F1);
* no structure at the defaults: at most 2 suggestions in 90 two-hour spans
  ({random walk, AR(1) 0.99, pink} x 30 seeds) and none in a 4 h set (F2);
* a stalled logger (a run of one repeated value) is a long gap, not a
  confident repeat (F4); null profiles only for judged lengths (F6); a
  constant span says "no spread to measure" without a warning (F7);
* the band of cleared lengths is reported, and on a dominant 90 s spike the
  suggestion is within one rung of 90 s (F3); there is no approximate mode
  (F5);
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


def _mask(n, starts, length):
    a = np.zeros(n, dtype=bool)
    for s in starts:
        a[s:s + length] = True
    return a


def _touches(mask, m):
    """For every window start c (n - m + 1 of them): does [c, c + m) touch `mask`?"""
    c = np.concatenate([[0], np.cumsum(mask)])
    return (c[m:] - c[:-m]) > 0


def _holds(mask_starts, n, length, m):
    """For every window start c: does [c, c + m) hold a whole motif of `length` starting at one of `mask_starts`?"""
    out = np.zeros(n - m + 1, dtype=bool)
    for s in mask_starts:
        out[max(0, s + length - m):min(s, n - m) + 1] = True
    return out


def test_the_planted_motifs_are_bright_where_they_sit(planted):
    x, short_starts, long_starts, out = planted
    n = len(x)
    img = out["image"]
    any_motif = _mask(n, short_starts, syn.SHORT_M) | _mask(n, long_starts, syn.LONG_M)
    for target, starts, slack in ((syn.SHORT_M, short_starts, 10), (syn.LONG_M, long_starts, 60)):
        r = _row_near(out, target)
        m = out["lengths_samples"][r]
        row = img[r, :n - m + 1]
        background = row[~_touches(any_motif, m)]           # windows touching no motif at all
        top = np.nanpercentile(background, 99)
        # the window starting at (or within a few samples of) a planted instance: typically brighter than 99 % of
        # the background, and every one brighter than 95 % of it
        peaks = [np.nanmax(row[max(0, s - slack):s + slack + 1]) for s in starts if s + m <= n]
        assert len(peaks) == len(starts)
        assert np.median(peaks) > top, (m, np.round(peaks, 3), round(top, 3))
        assert min(peaks) > np.nanpercentile(background, 95), (m, np.round(peaks, 3))


def test_the_short_motif_does_not_light_the_long_rows_away_from_the_long_motif(planted):
    x, short_starts, long_starts, out = planted
    n = len(x)
    img = out["image"]
    long_mask = _mask(n, long_starts, syn.LONG_M)
    short_mask = _mask(n, short_starts, syn.SHORT_M)
    checked = 0
    for r, m in enumerate(out["lengths_samples"]):
        if m < syn.LONG_M:
            continue
        row = img[r, :n - m + 1]
        clear_of_long = ~_touches(long_mask, m)
        holds_short = _holds(short_starts, n, syn.SHORT_M, m) & clear_of_long
        plain = clear_of_long & ~_touches(short_mask, m)
        if holds_short.sum() < 10 or plain.sum() < 10:
            continue
        checked += 1
        # holding a 90 s motif does not make a >= 20 min window look repeated: no brighter than plain background
        assert np.median(row[holds_short]) <= np.percentile(row[plain], 90), (
            m, np.median(row[holds_short]), np.percentile(row[plain], 90))
        # while the long motif itself does light these rows where it sits
        at_long = [np.nanmax(row[max(0, s - 60):s + 61]) for s in long_starts if s + m <= n]
        if at_long:
            assert np.median(at_long) > np.percentile(row[plain], 90)
    assert checked >= 1


# ── no structure: no length stands out ──────────────────────────────────────

def _detrended(x):
    return syn.rolling_mean_removed(x, 7200)          # what the motif_lengths template's detrend leaves


def _suggests(x, fs=FS):
    return P.pan_matrix_profile(_detrended(x), fs)["suggested_window_s"] is not None


def test_no_structure_at_the_defaults_rarely_suggests_a_length_2h():
    """The false-suggestion rate at the defaults, not one chosen seed: {random walk, AR(1) 0.99, pink} x 30
    seeds at 2 h, 1 Hz. At most 2 in 90; at one null draw the rate was 1-7 % (critic F2) and would fail this."""
    hits = [(kind, s) for kind in ("random_walk", "ar99", "pink") for s in range(30)
            if _suggests(syn.no_structure(kind, 2 * 3600, seed=500 + s))]
    assert len(hits) <= 2, hits


def test_no_structure_at_the_defaults_4h():
    hits = [(kind, s) for kind in ("random_walk", "ar99", "pink") for s in range(3)
            if _suggests(syn.no_structure(kind, 4 * 3600, seed=700 + s))]
    assert len(hits) <= 1, hits


def test_a_lopsided_recording_with_no_structure_is_not_a_repeat():
    """exp of an AR(1): skewed values, no structure. Plain phase surrogates Gaussianise the values, so this
    suggested a length 10 times in 10 at 1 and at 20 draws; the amplitude-adjusted null keeps the values."""
    hits = 0
    for s in range(10):
        a = syn.ar1(4 * 3600, 0.97, seed=900 + s)
        hits += _suggests(np.exp((a - a.mean()) / a.std()))
    assert hits <= 1, hits


def test_the_null_is_amplitude_adjusted_by_default_and_phase_is_on_offer():
    x = _small()
    out = P.pan_matrix_profile(x, FS, min_window_s=20, max_window_s=60, n_lengths=2)
    assert out["null"] == "aaft" and out["null_draws"] == 3
    P.pan_matrix_profile(x, FS, min_window_s=20, max_window_s=60, n_lengths=2, null="phase")
    with pytest.raises(ValueError, match="null"):
        P.pan_matrix_profile(x, FS, min_window_s=20, max_window_s=60, n_lengths=2, null="shuffle")
    # an AAFT copy is a permutation of the recording's own values; a phase copy is not
    z = P.null_copy(x, np.zeros(len(x), bool), 0, 0, "aaft")
    np.testing.assert_array_equal(np.sort(z), np.sort(x))
    zp = P.null_copy(x, np.zeros(len(x), bool), 0, 0, "phase")
    assert not np.array_equal(np.sort(zp), np.sort(x))


def test_there_is_no_approximate_mode():
    import inspect
    assert "percentage" not in inspect.signature(P.pan_matrix_profile).parameters
    assert not hasattr(P, "scrump_cost_factor")


def test_a_stalled_logger_is_a_long_gap_not_a_repeat():
    x = syn.no_structure("random_walk", 2 * 3600, seed=3)
    x = _detrended(x)
    x[3000:4200] = x[3000]                                    # 20 min of one held value
    out = P.pan_matrix_profile(x, FS)
    assert out["n_stalled"] == 1200 and out["n_long_gap"] >= 1200
    assert out["suggested_window_s"] is None, out["verdict"]
    for d in out["per_length"]:
        m = d["m"]
        assert np.all(np.isnan(out["image"][d["row"], max(0, 3000 - m + 1):4200]))
    # a few repeated samples (a quantised quiet stretch) are not a stall
    y = _small().copy()
    y[100:104] = y[100]
    assert P.pan_matrix_profile(y, FS, min_window_s=20, max_window_s=40, n_lengths=2, null_draws=0)["n_stalled"] == 0


def test_a_constant_span_says_there_is_no_spread_without_a_warning():
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        out = P.pan_matrix_profile(np.full(4 * 3600, 2.5), FS)
    assert out["suggested_window_s"] is None
    assert out["verdict"].startswith("no spread to measure")
    assert out["reasons"] == {"no_spread": len(out["per_length"])}
    assert all(d["reason_code"] == "no_spread" for d in out["per_length"])


def test_reasons_are_counted_separately():
    out = P.pan_matrix_profile(syn.no_structure("ar97", 4 * 3600, seed=5), FS)
    assert sum(out["reasons"].values()) == len(out["per_length"])
    assert out["reasons"].get("too_long", 0) == sum(1 for d in out["per_length"] if not P.judgeable(4 * 3600, d["m"]))
    assert set(out["reasons"]) <= set(P.REASONS)


def test_null_profiles_are_drawn_only_for_lengths_that_can_be_judged():
    n = 4 * 3600
    seen = []
    out = P.pan_matrix_profile(syn.no_structure("ar97", n, seed=1), FS, null_draws=2,
                               on_progress=lambda d, t, s: seen.append((d, t, s)))
    judged = sum(1 for m in out["lengths_samples"] if P.judgeable(n, m))
    assert judged < len(out["lengths_samples"])
    assert seen[-1][:2] == (len(out["lengths_samples"]) + 2 * judged,) * 2
    assert not any("null" in s for _, _, s in seen if s.startswith("length 3600 s"))
    assert P.profile_units(n, FS, null_draws=2) == len(out["lengths_samples"]) + 2 * judged


# ── what the suggestion means ───────────────────────────────────────────────

LADDER = [m for m in P.window_lengths(4 * 3600, 1.0, 30, 3600, 12)[0]]


def _rung(seconds):
    return int(np.argmin(np.abs(np.log(np.asarray(LADDER) / seconds))))


def test_the_band_of_cleared_lengths_is_reported(planted):
    _, _, _, out = planted
    cs = out["cleared_s"]
    assert cs == sorted(cs) and cs == sorted(d["length_s"] for d in out["per_length"] if d["clears"])
    assert out["suggested_window_s"] in cs
    assert out["verdict"].startswith("clears from" if len(cs) > 1 else "clears at")
    assert "strongest at" in out["verdict"]


def _near(seconds, target):
    """Within one rung of either rung bracketing `target` (90 s sits between 72 and 111)."""
    lo = max(i for i, m in enumerate(LADDER) if m <= target)
    return min(abs(_rung(seconds) - lo), abs(_rung(seconds) - min(lo + 1, len(LADDER) - 1))) <= 1


@pytest.mark.parametrize("seed", range(3))
def test_on_dominant_spikes_the_suggestion_is_within_one_rung_of_their_length(seed):
    """10-20 copies of a 60 s spike at 3 x SD on a random walk (4 h), through the template's detrend: the
    suggestion (the strongest cleared length) lands within one rung of 60 s — 6 of 6 seeds in the fix-round
    sweep (46-111 s)."""
    out = P.pan_matrix_profile(_detrended(syn.spike_train(4 * 3600, seed)), FS)
    s = out["suggested_window_s"]
    assert s is not None, out["verdict"]
    assert _near(s, 60), (s, out["cleared_s"])


@pytest.mark.parametrize("seed", range(2))
def test_a_dominant_motif_clears_a_band_that_holds_its_length(seed):
    """12 copies of a 90 s spike-and-undershoot on AR(1) 0.97 (4 h): the band of cleared lengths brackets 90 s,
    but no single rule names it — pieces of the spike (30 s) repeat as well as the spike, and so do the long
    windows it dominates; the strongest gap fell at 30, 46, 30, 976, 631, 976 s on seeds 0-5 (the critic: 976
    s on 4 of 10). The test pins the band, and that the suggestion is one of its lengths."""
    rng = np.random.default_rng(10_000 + seed)
    x = syn.ar1(4 * 3600, 0.97, seed)
    for p in np.sort(rng.choice(np.arange(300, 4 * 3600 - 300, 400), size=12, replace=False)):
        x[p:p + syn.SHORT_M] += syn.short_motif()
    out = P.pan_matrix_profile(_detrended(x), FS)
    cs = out["cleared_s"]
    assert cs and cs[0] <= 90 <= cs[-1], cs
    assert out["suggested_window_s"] in cs


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
    from Working.config import MP_MIN_WINDOW_SAMPLES
    assert dropped and all(m < MP_MIN_WINDOW_SAMPLES or m > 500 for m in dropped)
    assert all(MP_MIN_WINDOW_SAMPLES <= m <= 500 for m in kept)
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
    judged = sum(1 for m in out["lengths_samples"] if P.judgeable(len(x), m))
    assert len(seen) == 4 + 2 * judged and seen[-1][:2] == (4 + 2 * judged,) * 2

    calls = []
    with pytest.raises(RecipeCancelled, match="cancelled"):
        P.pan_matrix_profile(x, FS, min_window_s=20, max_window_s=200, n_lengths=4, null_draws=0,
                             on_progress=lambda d, t, s: calls.append(d),
                             should_cancel=lambda: len(calls) >= 2)
    assert calls == [1, 2]                                    # stopped before the third length
    assert len(out["per_length"]) == 4


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
