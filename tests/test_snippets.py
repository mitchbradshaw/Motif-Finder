"""
test_snippets.py
=================
The core of `catalogue.snippets` (W2-D): time-series snippets (Imani et al.
2018, matrix profile XIII) in `Working.Detection.matrix_profiling.snippets`.

What is pinned:
* the MPdist profiles equal stumpy 1.14.1's own (`snippets._get_all_profiles`)
  and the greedy selection equals `stumpy.snippets` — the kernel is a rewrite
  for memory and speed, not a different method;
* the sub-length `s = ceil(subseq_frac * m)` is what reaches the profiles
  (stumpy's default `percentage=1.0` would silently make it `m`);
* three regimes with a strong drift: the knee picks k = 3 and the window labels
  follow the regimes (>= 90 %); with `subseq_frac = 1.0` (plain z-normalised
  Euclidean) the same recordings fail — the reason for the 0.35 default;
* no structure (AR(1), random walk, pink noise): the knee says k = 1 in words,
  and at a fixed k = 3 the regime runs are no longer than shuffled labels;
* the exemplar of each label is that label's own window, the snippet itself;
* NaN: short gaps filled and counted, mostly-NaN windows labelled -1 and
  counted, no NaN reaches the kernel; refusals in words.

Synthetic recordings: `tests/_snippets_synthetic.py` (0.1 Hz, 1-hour pieces).
"""

import math
import os
import sys

import numpy as np
import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import stumpy  # noqa: E402
from stumpy.snippets import _get_all_profiles  # noqa: E402

from tests import _snippets_synthetic as syn  # noqa: E402
from Working.Detection.matrix_profiling import snippets as sn  # noqa: E402

M = syn.PIECE


def _run(x, **kw):
    starts = np.arange(len(x) // M) * M
    return sn.find_snippets(x, starts, M, **kw)


# ── the kernel is stumpy's method ──────────────────────────────────────────────

@pytest.mark.parametrize("n,m,frac", [(600, 50, 0.35), (1000, 64, 0.5), (900, 90, 1.0), (1203, 100, 0.35)])
def test_profiles_equal_stumpys_own(n, m, frac):
    rng = np.random.default_rng(n)
    T = np.cumsum(rng.standard_normal(n)) + 100.0
    T[300:420] = T[300]                                   # a constant stretch: stumpy's special case
    s = sn.sub_length(m, frac)
    ref = _get_all_profiles(T, m, s=s)
    got = sn.mpdist_profiles(T, m, s)
    assert got.shape == ref.shape
    np.testing.assert_allclose(got, ref, rtol=0, atol=1e-6)


def test_greedy_selection_equals_stumpy_snippets():
    rng = np.random.default_rng(3)
    T = np.cumsum(rng.standard_normal(1500))
    m, k = 100, 4
    s = sn.sub_length(m, 0.35)
    snip, idx, prof, frac, areas, regimes = stumpy.snippets(T, m, k, s=s)
    D = sn.mpdist_profiles(T, m, s)
    chosen, got_areas = sn.greedy_snippets(D, k)
    assert [c * m for c in chosen] == list(idx)
    np.testing.assert_allclose(got_areas, areas, rtol=1e-9)
    owner = sn.regime_owner(D[chosen])
    np.testing.assert_allclose([np.mean(owner == c) for c in range(k)], frac)


def test_sub_length_rule():
    assert sn.sub_length(3600, 0.35) == 1260
    assert sn.sub_length(200, 0.35) == 70        # the paper's example: 70 of 200
    assert sn.sub_length(360, 1.0) == 360


def test_the_sub_length_reaches_the_profiles(monkeypatch):
    seen = []
    real = sn.mpdist_profiles

    def spy(T, m, s, *a, **kw):
        seen.append((m, s))
        return real(T, m, s, *a, **kw)

    monkeypatch.setattr(sn, "mpdist_profiles", spy)
    x, _ = syn.three_regimes(0)
    out = _run(x, subseq_frac=0.35)
    assert seen == [(M, math.ceil(0.35 * M))]
    assert out["s"] == math.ceil(0.35 * M) and out["subseq_frac"] == 0.35


def test_a_nan_never_reaches_the_kernel():
    x = np.arange(100.0)
    x[10] = np.nan
    with pytest.raises(ValueError, match="finite"):
        sn.mpdist_profiles(x, 20, 7)


# ── three regimes under a strong drift ────────────────────────────────────────

@pytest.mark.parametrize("seed", [0, 1])
def test_three_regimes_under_drift_are_found(seed):
    x, truth = syn.three_regimes(seed, with_drift=True)
    out = _run(x)
    assert out["k"] == 3, (out["change_k"], out["k_reason"])
    assert out["k_chosen_by"] == "knee"
    assert syn.agreement(out["labels"], truth) >= 0.9
    assert abs(sum(out["fractions"]) - 1.0) < 1e-9
    # each regime is 1/3 of the recording, and each snippet covers about that
    assert all(0.2 < f < 0.45 for f in out["fractions"]), out["fractions"]
    # the regimes persist: long runs, far beyond shuffled labels
    assert out["runs"]["mean"] >= 6 and out["runs"]["ratio"] > 3
    # the exemplar override was not needed: every snippet's own window voted for it
    assert out["n_exemplar_relabelled"] == 0


def test_whole_piece_distance_does_measurably_worse():
    """subseq_frac = 1.0 makes MPdist the plain z-normalised Euclidean
    distance between whole pieces: the drifting, jittered regimes are then
    no longer separated — which is why the default is 0.35."""
    for seed in (0, 1):
        x, truth = syn.three_regimes(seed, with_drift=True)
        good = _run(x, subseq_frac=0.35, k=3)
        bad = _run(x, subseq_frac=1.0, k=3)
        a_good = syn.agreement(good["labels"], truth)
        a_bad = syn.agreement(bad["labels"], truth)
        assert a_good >= 0.9
        assert a_bad <= a_good - 0.25, (a_good, a_bad)
        assert _run(x, subseq_frac=1.0)["k"] != 3


# ── no structure ──────────────────────────────────────────────────────────────

NULLS = {
    "ar1_60s": lambda s: syn.ar1_null(s, tau_s=60.0),
    "ar1_600s": lambda s: syn.ar1_null(s, tau_s=600.0),
    "random_walk": syn.random_walk_null,
    "pink": syn.pink_null,
}


@pytest.mark.parametrize("name", sorted(NULLS))
@pytest.mark.parametrize("seed", [0, 1])
def test_no_structure_gives_k1_and_short_runs(name, seed):
    out = _run(NULLS[name](seed))
    assert out["k"] == 1, (out["change_k"], out["k_reason"])
    assert "no knee" in out["k_reason"]
    assert out["knee_ratio"] < sn.KNEE_TAIL_RATIO
    # at a fixed k the labels flicker: no more persistent than shuffled labels
    at3 = out["runs_by_k"]["3"]
    assert at3["ratio"] < 1.6 and at3["mean"] < 2.5, at3


# ── exemplars, labels, runs ───────────────────────────────────────────────────

def test_the_exemplar_of_each_label_is_its_own_window_the_snippet_itself():
    x, _ = syn.three_regimes(0)
    out = _run(x)
    assert sorted(out["exemplar_windows"]) == ["1", "2", "3"]
    starts = np.arange(len(x) // M) * M
    for lab, w in out["exemplar_windows"].items():
        assert out["labels"][w] == int(lab)
        assert starts[w] == out["snippet_starts"][int(lab) - 1]


def test_mostly_one_behaviour_still_names_the_rare_one():
    """Dense stretches are common on real recordings: 40 h of drops and 8 h
    of a slow oscillation."""
    rng = np.random.default_rng(5)
    x = np.concatenate([syn.drops(rng, 20), syn.wave(rng, 8), syn.drops(rng, 20)])
    x = x + syn.drift(len(x))
    truth = np.repeat([0, 2, 0], [20, 8, 20])
    out = _run(x)
    assert out["k"] == 2, (out["change_k"], out["k_reason"])
    assert syn.agreement(out["labels"], truth) >= 0.9


def test_windows_with_gaps_between_them_are_labelled_by_majority():
    x, truth = syn.three_regimes(0)
    starts = np.arange(0, len(x) // M, 2) * M            # every other hour
    out = sn.find_snippets(x, starts, M)
    assert out["contiguous"] is False
    assert out["k"] == 3
    assert syn.agreement(out["labels"], truth[::2]) >= 0.9
    for lab, w in out["exemplar_windows"].items():
        assert out["labels"][w] == int(lab)


def test_change_curve_and_knee_rule():
    ch = sn.change_curve([100.0, 50.0, 25.0, 24.0, 23.5])
    assert ch[2] == pytest.approx(1.0) and ch[3] == pytest.approx(1.0)
    assert ch[4] == pytest.approx(25 / 24 - 1)
    k, why = sn.knee(ch, k_max=4)
    assert k == 3 and "knee at k=3" in why
    flat = sn.change_curve([100.0, 92.0, 86.0, 81.0, 77.0])
    k, why = sn.knee(flat, k_max=4)
    assert k == 1 and "no knee" in why


def test_the_knee_is_judged_against_the_curves_own_tail():
    """Not an absolute floor: change_k must be at least KNEE_TAIL_RATIO times
    the median of change_(k+1) .. change_(k_max+1). The same change_2 = 0.15
    is a knee over a tail of 0.02 and is not over a tail of 0.10."""
    assert sn.KNEE_TAIL_RATIO == 3.0
    low_tail = {2: 0.15, 3: 0.02, 4: 0.02, 5: 0.02}
    k, why = sn.knee(low_tail, k_max=4)
    assert k == 2 and "7.5" in why
    high_tail = {2: 0.15, 3: 0.10, 4: 0.09, 5: 0.08}
    k, why = sn.knee(high_tail, k_max=4)
    assert k == 1 and "no knee" in why and "median" in why


def test_a_constant_signal_says_so():
    out = sn.find_snippets(np.ones(20 * M), np.arange(20) * M, M, k_max=3)
    assert out["k"] == 1
    assert "constant signal: every distance is 0" in out["k_reason"]


# ── the knee at the template's scale (6 h rolling-mean detrend, 1-hour pieces) ──

def _detrended(x):
    from Working.Preprocessing.detrend import make_detrend_filter
    return make_detrend_filter(syn.FS, mode="rolling_mean", window_s=21600.0)(x)


SHORT_NULLS = {
    "random_walk": syn.random_walk_null,
    "ar1_phi0.999": lambda seed, hours: syn.ar1_null(seed, hours=hours, tau_s=1000.0),
    "pink": syn.pink_null,
}


@pytest.mark.parametrize("hours", [12, 24])
@pytest.mark.parametrize("name", sorted(SHORT_NULLS))
def test_short_nulls_give_k1_at_the_templates_scale(name, hours):
    """12 and 24 h of noise (AR(1) with a 1000 s correlation time is φ = 0.999
    at 1 Hz): the absolute floor this replaced called 12 h of random walk two
    kinds of behaviour in half the runs."""
    for seed in range(4):
        x = _detrended(SHORT_NULLS[name](seed, hours=hours))
        out = _run(x)
        assert out["k"] == 1, (seed, out["change_k"], out["k_reason"])


@pytest.mark.parametrize("span,minor", [(72, 8), (120, 12)])
def test_a_brief_minority_regime_in_a_long_span_is_found(span, minor):
    """8-12 h of a slow oscillation inside 72-120 h of drops: the absolute
    floor missed it (change_2 0.14-0.24)."""
    rng = np.random.default_rng(span + minor)
    a = (span - minor) // 2
    x = np.concatenate([syn.drops(rng, a), syn.wave(rng, minor), syn.drops(rng, span - minor - a)])
    x = _detrended(x + syn.drift(len(x)))
    truth = np.repeat([0, 2, 0], [a, minor, span - minor - a])
    out = _run(x)
    assert out["k"] == 2, (out["change_k"], out["k_reason"])
    assert syn.agreement(out["labels"], truth) >= 0.9


def test_expected_limitation_a_regime_that_differs_only_in_amplitude():
    """Quiet AR(1) noise between the drops and the waves: z-normalised MPdist
    has no amplitude, so a stretch that differs from the others only in how
    big it is has no shape of its own and is not separated — it is absorbed by
    the other labels. Pinned so that a change here is noticed."""
    x, _ = syn.three_regimes(0, order=syn.ORDER_QUIET)
    out = _run(x)
    assert out["k"] <= 2


def test_run_lengths_and_the_shuffled_expectation():
    assert sn.run_lengths([1, 1, 2, 2, 2, -1, 1]) == [2, 3, 1]
    r = sn.run_summary([1, 1, 1, 1, 2, 2, 2, 2])
    assert r["mean"] == 4.0 and r["median"] == 4.0
    # 8 windows, two labels at 1/2 each: 1 + 7 * 0.5 = 4.5 runs expected
    assert r["shuffled_mean"] == pytest.approx(8 / 4.5)
    assert r["ratio"] == pytest.approx(4.0 / (8 / 4.5))


# ── NaN ───────────────────────────────────────────────────────────────────────

def test_a_short_gap_is_filled_and_counted():
    x, truth = syn.three_regimes(0)
    x = x.copy()
    x[5 * M + 10:5 * M + 40] = np.nan                     # 5 minutes
    out = _run(x)
    assert out["n_nan_filled"] == 30
    assert out["n_windows_nan"] == 0
    assert out["k"] == 3 and syn.agreement(out["labels"], truth) >= 0.9


def test_mostly_nan_windows_are_labelled_minus_one_and_counted():
    x, truth = syn.three_regimes(0)
    x = x.copy()
    x[20 * M:22 * M] = np.nan                             # two whole hours
    out = _run(x)
    assert out["n_windows_nan"] == 2 and out["n_pieces_excluded_nan"] == 2
    assert list(out["labels"][20:22]) == [-1, -1]
    assert out["k"] == 3
    keep = np.r_[0:20, 22:48]
    assert syn.agreement(out["labels"][keep], truth[keep]) >= 0.9
    assert all(int(w) not in (20, 21) for w in out["exemplar_windows"].values())


# ── refusals, in words ────────────────────────────────────────────────────────

def test_refuses_a_piece_longer_than_half_the_span():
    x = np.random.default_rng(0).standard_normal(1000)
    with pytest.raises(ValueError, match="half"):
        sn.find_snippets(x, np.array([0]), 600)


def test_refuses_too_few_pieces():
    x = np.random.default_rng(0).standard_normal(10 * M)
    with pytest.raises(ValueError, match="too few pieces.*k_max=6.*12"):
        _run(x)


def test_refuses_an_all_nan_span():
    x = np.full(20 * M, np.nan)
    with pytest.raises(ValueError, match="all NaN"):
        _run(x, k_max=3)


def test_the_memory_refusal_counts_the_true_peak(monkeypatch):
    """The peak is the profiles twice over (the profiles plus the first-row dot
    products, the same size, while the kernel runs) plus the kernel's own
    blocks — not the profiles alone."""
    x, _ = syn.three_regimes(0)
    W, P = 48, len(x) - M + 1
    profiles = 8 * W * P
    peak = sn.memory_peak(len(x), M, sn.sub_length(M, 0.35))
    assert peak >= 2 * profiles
    monkeypatch.setattr(sn, "MEMORY_LIMIT", peak - 1)
    with pytest.raises(ValueError, match="peak"):
        _run(x)


def test_refuses_k_above_k_max():
    x, _ = syn.three_regimes(0)
    with pytest.raises(ValueError, match="k_max"):
        _run(x, k=7, k_max=6)
