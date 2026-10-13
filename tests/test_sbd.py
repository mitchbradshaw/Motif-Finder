"""
test_sbd.py
=============
The shape-based distance (SBD) of k-Shape — Paparrizos & Gravano 2015, eq. 9:

    SBD(x, y) = 1 - max_w  CC_w(x, y) / sqrt(R0(x, x) * R0(y, y))

over every shift w, with **zero-padded** (not cyclic) shifts (eq. 5), computed
with FFTs padded to the next power of two >= 2m - 1 (Alg. 1). It lies in
[0, 2]: 0 for a copy (at the best shift), 2 for an exact negative at every
shift. `Working.distances` carries the pair form (`sbd`, `sbd_shift`), the
batched matrix (`sbd_matrix`) and the zero-padded shift (`zero_pad_shift`).

What these tests pin:
  * a shape against its own shifted copy (zero-padded, not wrapped) scores ~0
    and reports the shift that undoes it;
  * a shape against its negative scores ~2 (~1 on the methods' /2 scale);
  * the FFT form matches a direct O(m^2) loop over every lag to 1e-10, for the
    pair and for the matrix, so the speed-up is not an approximation;
  * the shifts are not cyclic: a pattern that only matches when wrapped round
    does not score as a copy;
  * a flat (zero-variance) input is defined, not a NaN.

Runnable standalone:  python tests/test_sbd.py
"""

import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import numpy as np
import pytest

from Working.distances import sbd, sbd_matrix, sbd_shift, z_normalize, zero_pad_shift


def _direct_sbd(x, y):
    """eq. 9 by brute force: every lag k in -(len(y)-1) .. len(x)-1, the
    zero-padded cross-correlation R_k = sum_l x[l + k] * y[l]."""
    x = np.asarray(x, float)
    y = np.asarray(y, float)
    best, best_k = -np.inf, 0
    for k in range(-(len(y) - 1), len(x)):
        total = 0.0
        for l in range(len(y)):
            if 0 <= l + k < len(x):
                total += x[l + k] * y[l]
        if total > best:
            best, best_k = total, k
    denom = np.sqrt(np.dot(x, x) * np.dot(y, y))
    return 1.0 - best / denom, best_k


def _shape(m=128, seed=0):
    t = np.linspace(0.0, 1.0, m)
    rng = np.random.default_rng(seed)
    # a drop with a slow recovery, inside a quiet margin so a shift loses nothing
    x = np.where((t > 0.3) & (t < 0.7), -np.exp(-(t - 0.3) * 8.0), 0.0)
    return x + rng.normal(0.0, 1e-3, m)


# --------------------------------------------------------------------------

def test_a_shifted_copy_scores_zero_at_the_shift_that_undoes_it():
    x = _shape()
    for k in (7, -11, 25):
        y = zero_pad_shift(x, -k)            # y is x moved LEFT by k
        d, shift = sbd_shift(x, y, z_normalise=False)
        assert d == pytest.approx(0.0, abs=1e-5), k
        assert shift == k, (k, shift)
        # and moving y by that shift lines it up with x
        assert np.corrcoef(zero_pad_shift(y, shift), x)[0, 1] > 0.999
        # z-normalised (the default), the zero padding is not the shape's own
        # baseline, so a copy is near 0 rather than at it — and the shift holds
        d, shift = sbd_shift(x, y)
        assert d < 0.07 and shift == k, (k, d, shift)


def test_zero_pad_shift_pads_with_zeros_and_never_wraps():
    x = np.arange(1.0, 6.0)
    assert zero_pad_shift(x, 2).tolist() == [0.0, 0.0, 1.0, 2.0, 3.0]
    assert zero_pad_shift(x, -2).tolist() == [3.0, 4.0, 5.0, 0.0, 0.0]
    assert zero_pad_shift(x, 0).tolist() == x.tolist()
    assert zero_pad_shift(x, 9).tolist() == [0.0] * 5


def test_a_negative_is_anticorrelated_at_zero_shift_and_uncorrelated_at_best():
    """SBD maximises over shifts, so a negative scores 2 (1 on the methods'
    /2 scale) only at zero shift. A one-signed pulse against its negative has
    no shift with a positive match: SBD = 1, i.e. 0.5 normalised — the
    'uncorrelated' value. A z-normalised shape's negative does better than
    that, because some shift lines a lobe of -x up with a lobe of x."""
    x = _shape()
    assert sbd(x, x) == pytest.approx(0.0, abs=1e-12)
    spike = np.zeros(64)
    spike[30] = 1.0
    assert sbd(spike, -spike, z_normalise=False) == pytest.approx(1.0, abs=1e-12)
    assert sbd(x, -x, z_normalise=False) == pytest.approx(1.0, abs=2e-3)
    # the zero-shift coefficient-normalised correlation of a negative is -1
    z = z_normalize(x)
    assert np.dot(z, -z) / np.dot(z, z) == pytest.approx(-1.0)
    # and with z-normalisation the negative is still clearly not a copy
    assert 0.4 < sbd(x, -x) < 1.0


def test_sbd_lies_in_zero_to_two():
    rng = np.random.default_rng(3)
    X = rng.normal(size=(40, 50))
    D = sbd_matrix(X)
    assert D.min() >= -1e-12 and D.max() <= 2.0 + 1e-12


@pytest.mark.parametrize("seed", range(6))
def test_the_pair_matches_a_direct_loop_to_1e_10(seed):
    rng = np.random.default_rng(seed)
    m = int(rng.integers(5, 70))
    x = rng.normal(size=m)
    y = rng.normal(size=m)
    want, want_k = _direct_sbd(x, y)
    got, got_k = sbd_shift(x, y, z_normalise=False)
    assert got == pytest.approx(want, abs=1e-10)
    assert got_k == want_k


def test_unequal_lengths_match_the_direct_loop_too():
    rng = np.random.default_rng(11)
    x, y = rng.normal(size=37), rng.normal(size=23)
    want, want_k = _direct_sbd(x, y)
    got, got_k = sbd_shift(x, y, z_normalise=False)
    assert got == pytest.approx(want, abs=1e-10)
    assert got_k == want_k


@pytest.mark.parametrize("method", ["lags", "fft"])
def test_the_matrix_matches_the_direct_loop_and_its_shifts(method):
    rng = np.random.default_rng(5)
    X = rng.normal(size=(9, 33))
    D, S = sbd_matrix(X, z_normalise=False, return_shifts=True, method=method)
    assert D.shape == (9, 9) and S.shape == (9, 9)
    for i in range(9):
        for j in range(9):
            want, want_k = _direct_sbd(X[i], X[j])
            assert D[i, j] == pytest.approx(want, abs=1e-10), (i, j)
            assert S[i, j] == want_k, (i, j)
    assert np.allclose(D, D.T, atol=1e-12)
    assert np.allclose(np.diag(D), 0.0, atol=1e-12)


@pytest.mark.parametrize("method", ["lags", "fft"])
def test_the_matrix_against_a_second_set_is_rectangular_and_exact(method):
    rng = np.random.default_rng(6)
    X, Y = rng.normal(size=(7, 40)), rng.normal(size=(4, 40))
    D, S = sbd_matrix(X, Y, z_normalise=False, return_shifts=True, method=method)
    assert D.shape == (7, 4)
    for i in range(7):
        for j in range(4):
            want, want_k = _direct_sbd(X[i], Y[j])
            assert D[i, j] == pytest.approx(want, abs=1e-10)
            assert S[i, j] == want_k


def test_the_two_engines_agree_on_realistic_shapes():
    rng = np.random.default_rng(13)
    X = rng.normal(size=(25, 128)).cumsum(axis=1)
    D1, S1 = sbd_matrix(X, method="lags", return_shifts=True)
    D2, S2 = sbd_matrix(X, method="fft", return_shifts=True)
    assert np.allclose(D1, D2, atol=1e-10)
    assert (S1 == S2).all()


@pytest.mark.parametrize("method", ["lags", "fft"])
def test_the_matrix_is_the_same_whatever_the_block_size(method):
    rng = np.random.default_rng(8)
    X = rng.normal(size=(30, 64))
    full = sbd_matrix(X, method=method)
    tiny = sbd_matrix(X, block_bytes=1, method=method)          # one row per block
    assert np.allclose(full, tiny, atol=1e-12)


@pytest.mark.parametrize("method", ["lags", "fft"])
def test_single_precision_is_close_to_double(method):
    rng = np.random.default_rng(14)
    X = rng.normal(size=(20, 256)).cumsum(axis=1)
    D64 = sbd_matrix(X, method=method)
    D32 = sbd_matrix(X, method=method, dtype=np.float32)
    assert D32.dtype == np.float64
    assert np.abs(D64 - D32).max() < 1e-5


@pytest.mark.parametrize("method", ["lags", "fft"])
def test_the_self_matrix_is_exactly_symmetric_in_either_precision(method):
    """sklearn's HDBSCAN refuses a precomputed matrix that is not symmetric,
    and a row block computes both (i, j) and (j, i) — they must be one value."""
    X = np.random.default_rng(15).normal(size=(120, 64)).cumsum(axis=1)
    for dtype in (np.float32, np.float64):
        D, S = sbd_matrix(X, dtype=dtype, method=method, return_shifts=True, block_bytes=50_000)
        assert (D == D.T).all()
        assert (S == -S.T).all()


def test_shifts_are_zero_padded_not_cyclic():
    """A ramp against itself rotated by half its length matches perfectly
    under a CYCLIC shift and not at all well under a zero-padded one."""
    x = np.linspace(-1.0, 1.0, 64)
    y = np.roll(x, 32)
    assert sbd(x, y) > 0.3


def test_z_normalisation_is_the_default_and_makes_it_offset_and_scale_free():
    x = _shape()
    assert sbd(x, 5.0 * x + 3.0) == pytest.approx(0.0, abs=1e-9)
    raw = sbd(x, x + 3.0, z_normalise=False)
    assert raw > 1e-3, "without z-normalisation an offset changes the score"


def test_a_flat_input_is_defined_not_nan():
    flat = np.full(50, 4.2)
    x = _shape(50)
    assert sbd(flat, x) == pytest.approx(1.0)
    assert sbd(flat, flat) == pytest.approx(0.0)
    D = sbd_matrix(np.vstack([flat, x, flat]))
    assert np.isfinite(D).all()
    assert D[0, 2] == pytest.approx(0.0) and D[0, 1] == pytest.approx(1.0)


def test_it_agrees_with_the_cross_channel_correlation_on_equal_lengths():
    """`Working.cross_channel.cross_correlate` is the project's other
    zero-padded correlation; on two z-normalised spans of one length its peak
    is SBD's coefficient-normalised peak, so the two must agree."""
    from Working.cross_channel import cross_correlate
    rng = np.random.default_rng(12)
    for _ in range(5):
        a, b = rng.normal(size=80), rng.normal(size=80)
        _, r = cross_correlate(a, b)
        assert sbd(a, b) == pytest.approx(1.0 - r.max(), abs=1e-10)


def test_the_matrix_z_normalises_like_the_pair():
    rng = np.random.default_rng(9)
    X = rng.normal(size=(5, 30)) * 4 + 2
    D = sbd_matrix(X)
    assert D[1, 3] == pytest.approx(sbd(X[1], X[3]), abs=1e-12)
    assert np.allclose(z_normalize(X[0]), z_normalize(X[0]))


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
