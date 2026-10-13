"""
test_fluss.py
=============
The FLUSS core (`Working.Detection.matrix_profiling.fluss`, Gharghabi et al.
2017, matrix profile VIII): from a matrix-profile INDEX to a regime-change
score, 1 - CAC, one value per sample of the analysed signal.

Mostly on hand-built indices (fast, exact): two halves whose nearest
neighbours stay inside their own half must dip at the seam; uniformly random
neighbours (what z-normalised drift produces) must not. One test runs the
real `stumpy.stump` on the shared synthetic recording.

Runnable standalone:  python tests/test_fluss.py
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

from Working.Detection.matrix_profiling.fluss import (  # noqa: E402
    IAC_KINDS, parabola_iac, regime_change_score,
)


def _two_halves_index(k, seed=0):
    """Every subsequence's nearest neighbour lies in its own half."""
    rng = np.random.default_rng(seed)
    half = k // 2
    i = np.empty(k, dtype=np.int64)
    i[:half] = rng.integers(0, half, size=half)
    i[half:] = rng.integers(half, k, size=k - half)
    return i


def _random_index(k, seed=0):
    """Neighbours anywhere: no regime structure at all."""
    return np.random.default_rng(seed).integers(0, k, size=k).astype(np.int64)


# ── the idealised arc curve ───────────────────────────────────────────────────

def test_the_parabola_is_the_papers_idealised_arc_curve():
    k = 1000
    iac = parabola_iac(k)
    i = np.arange(k)
    np.testing.assert_allclose(iac, 2.0 * i * (k - i) / k)
    assert iac[0] == 0.0
    assert iac[k // 2] == pytest.approx(k / 2)            # height n/2 (fig. 4)
    np.testing.assert_allclose(iac[1:], iac[1:][::-1])    # symmetric


def test_both_iac_kinds_are_offered():
    assert set(IAC_KINDS) == {"parabola", "beta"}


# ── the score ─────────────────────────────────────────────────────────────────

def test_two_regimes_dip_at_the_seam_and_the_score_peaks_there():
    m, k = 10, 4000
    out = regime_change_score(_two_halves_index(k), m=m, excl_factor=5, n_regimes=2)
    score = out["score"]
    assert len(score) == k + m - 1                        # one value per sample of x
    peak = int(np.nanargmax(score))
    assert abs(peak - k // 2) <= 2 * m
    assert out["regime_locs"] and abs(out["regime_locs"][0] - k // 2) <= 2 * m
    assert np.nanmax(score) > 0.8                         # almost no arc crosses the seam
    assert out["cac_min"] == pytest.approx(1.0 - np.nanmax(score))
    assert out["cac_min_idx"] == peak


def test_random_neighbours_give_a_flat_low_score_it_fails_safe():
    m, k = 10, 20000
    out = regime_change_score(_random_index(k), m=m, excl_factor=5, n_regimes=2)
    assert np.nanmax(out["score"]) < 0.2


def test_the_tail_and_the_blanked_edges_are_nan_not_zero():
    m, k, f = 10, 4000, 5
    out = regime_change_score(_two_halves_index(k), m=m, excl_factor=f, n_regimes=2)
    score = out["score"]
    assert np.isnan(score[k:]).all() and len(score[k:]) == m - 1   # no full window starts here
    assert np.isnan(score[:f * m]).all()                           # stumpy blanks 5·L at each end
    assert np.isnan(score[k - f * m:k]).all()
    assert np.isfinite(score[f * m:k - f * m]).all()
    assert out["n_blanked_each_end"] == f * m


def test_beta_and_parabola_both_run_and_nearly_agree():
    m, k = 10, 4000
    i = _two_halves_index(k)
    p = regime_change_score(i, m=m, iac="parabola", n_regimes=2)
    b = regime_change_score(i, m=m, iac="beta", n_regimes=2)
    assert p["iac"] == "parabola" and b["iac"] == "beta"
    assert abs(int(np.nanargmax(b["score"])) - k // 2) <= 2 * m
    assert np.nanmax(np.abs(p["score"] - b["score"])) < 0.1


def test_regime_locations_are_n_regimes_minus_one_with_their_cac():
    m, k = 10, 4000
    out = regime_change_score(_two_halves_index(k), m=m, n_regimes=3)
    assert len(out["regime_locs"]) == 2
    assert len(out["regime_cac"]) == 2
    assert all(0.0 <= c <= 1.0 for c in out["regime_cac"])


def test_a_missing_neighbour_is_counted_and_draws_no_arc():
    m, k = 10, 4000
    i = _two_halves_index(k)
    i[100:110] = -1                                     # stumpy's "no neighbour" (a NaN window)
    out = regime_change_score(i, m=m, n_regimes=2)
    assert out["n_no_neighbour"] == 10
    assert abs(int(np.nanargmax(out["score"])) - k // 2) <= 2 * m


def test_the_input_index_is_not_modified():
    i = _two_halves_index(4000)
    i[5] = -1
    before = i.copy()
    regime_change_score(i, m=10, n_regimes=2)
    np.testing.assert_array_equal(i, before)


# ── refusals ──────────────────────────────────────────────────────────────────

def test_distances_instead_of_the_index_are_refused():
    """stumpy's own docstring examples pass `mp[:, 0]` (distances); FLUSS needs `mp[:, 1]`."""
    d = np.random.default_rng(0).random(4000)
    with pytest.raises(TypeError, match="index"):
        regime_change_score(d, m=10)


def test_a_span_too_short_for_the_edge_blanking_is_refused():
    with pytest.raises(ValueError, match="too short"):
        regime_change_score(_random_index(100), m=10, excl_factor=5)


def test_an_unknown_iac_is_refused():
    with pytest.raises(ValueError, match="iac"):
        regime_change_score(_two_halves_index(4000), m=10, iac="cubic")


# ── on a real matrix profile ─────────────────────────────────────────────────

def test_on_the_synthetic_recording_the_score_peaks_within_two_windows_of_the_boundary():
    import stumpy
    from tests._fluss_synthetic import BOUNDARY, two_regimes
    x = two_regimes()
    m = 60
    mpi = stumpy.stump(x, m)[:, 1].astype(np.int64)
    out = regime_change_score(mpi, m=m, n_regimes=2)
    assert len(out["score"]) == len(x)
    assert abs(int(np.nanargmax(out["score"])) - BOUNDARY) <= 2 * m


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
